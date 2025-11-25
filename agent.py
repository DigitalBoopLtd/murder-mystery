"""LangGraph agent for the game master."""
import os
from typing import Annotated, TypedDict, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import CheckpointTuple
from langgraph.types import RunnableConfig
from game_tools import interrogate_suspect


class AgentState(TypedDict):
    """State for the game master agent."""
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    system_prompt: str


def create_game_master_agent():
    """Create a game master agent with tools."""
    llm = ChatOpenAI(
        model="gpt-5.1",
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Bind tools to the LLM
    tools = [interrogate_suspect]
    llm_with_tools = llm.bind_tools(tools)
    
    # Create tool node
    tool_node = ToolNode(tools)
    
    # Define the agent node
    def agent_node(state: AgentState):
        messages = state["messages"]
        # System prompt should already be in messages, but ensure it's there
        if not any(isinstance(msg, SystemMessage) for msg in messages):
            messages = [SystemMessage(content=state.get("system_prompt", ""))] + messages
        
        # Filter messages to ensure valid sequence for OpenAI API
        # ToolMessages must immediately follow an AIMessage with tool_calls
        filtered_messages = []
        for i, msg in enumerate(messages):
            if isinstance(msg, ToolMessage):
                # ToolMessage must follow an AIMessage with tool_calls
                # Look backwards to find the preceding AIMessage
                preceding_ai = None
                for j in range(i - 1, -1, -1):
                    if isinstance(messages[j], AIMessage):
                        preceding_ai = messages[j]
                        break
                    elif isinstance(messages[j], (HumanMessage, SystemMessage)):
                        # Stop at user/system messages - tool can't be before them
                        break
                
                # Only include ToolMessage if it follows an AIMessage with tool_calls
                if preceding_ai and hasattr(preceding_ai, 'tool_calls') and preceding_ai.tool_calls:
                    # Check if this ToolMessage's tool_call_id matches any tool call
                    tool_call_id = getattr(msg, 'tool_call_id', None)
                    if tool_call_id:
                        # Check if it matches any tool call in the preceding AIMessage
                        for tc in preceding_ai.tool_calls:
                            tc_id = None
                            if isinstance(tc, dict):
                                tc_id = tc.get('id')
                            elif hasattr(tc, 'id'):
                                tc_id = tc.id
                            
                            if tc_id == tool_call_id:
                                filtered_messages.append(msg)
                                break
                # Otherwise skip this ToolMessage - it's orphaned
            else:
                # Include all other message types
                filtered_messages.append(msg)
        
        response = llm_with_tools.invoke(filtered_messages)
        return {"messages": [response]}
    
    # Define routing logic
    def should_continue(state: AgentState):
        messages = state["messages"]
        if not messages:
            return END
        
        last_message = messages[-1]
        
        # If the last message has tool calls, route to tools
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        # Otherwise, we're done
        return END
    
    # Build the graph
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )
    
    # After tools, go back to agent
    workflow.add_edge("tools", "agent")
    
    # Compile with memory that limits context window to 40 messages (like n8n)
    class LimitedMemorySaver(MemorySaver):
        """Memory saver that limits conversation history to 40 messages."""
        
        def get(self, config: RunnableConfig) -> CheckpointTuple | None:
            """Get checkpoint and limit messages to 40 (contextWindowLength from n8n)."""
            checkpoint_tuple = super().get(config)
            if checkpoint_tuple and checkpoint_tuple.checkpoint:
                checkpoint = checkpoint_tuple.checkpoint
                if checkpoint.get("channel_values", {}).get("messages"):
                    messages = checkpoint["channel_values"]["messages"]
                    # Keep system message + last 40 messages (like n8n's contextWindowLength: 40)
                    if len(messages) > 41:  # 1 system + 40 others
                        # Separate system message from others
                        system_msg = None
                        other_messages = []
                        for msg in messages:
                            if isinstance(msg, SystemMessage):
                                system_msg = msg
                            else:
                                other_messages.append(msg)
                        
                        # Keep last 40 non-system messages
                        limited_messages = other_messages[-40:]
                        if system_msg:
                            limited_messages = [system_msg] + limited_messages
                        
                        # Update checkpoint with limited messages
                        checkpoint["channel_values"]["messages"] = limited_messages
                        return CheckpointTuple(
                            checkpoint=checkpoint,
                            metadata=checkpoint_tuple.metadata,
                            parent_checkpoint=checkpoint_tuple.parent_checkpoint
                        )
            return checkpoint_tuple
    
    limited_memory = LimitedMemorySaver()
    app = workflow.compile(checkpointer=limited_memory)
    
    return app


def process_message(
    agent_app,
    user_message: str,
    system_prompt: str,
    session_id: str,
    thread_id: str = "default"
) -> str:
    """Process a user message through the agent."""
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    
    # Get current state
    state = agent_app.get_state(config)
    current_messages = state.values.get("messages", []) if state.values else []
    
    # Don't filter messages here - let agent_node handle it with proper context
    # The agent_node will ensure ToolMessages are properly sequenced
    
    # Update system prompt - replace existing system message or add if missing
    # This ensures suspect profiles are always available when continuing
    system_msg_index = None
    for i, msg in enumerate(current_messages):
        if isinstance(msg, SystemMessage):
            system_msg_index = i
            break
    
    if system_msg_index is not None:
        # Replace existing system message with updated one
        current_messages[system_msg_index] = SystemMessage(content=system_prompt)
    else:
        # Add system message at the beginning
        current_messages = [SystemMessage(content=system_prompt)] + current_messages
    
    # Add user message
    current_messages.append(HumanMessage(content=user_message))
    
    # Update state with new messages
    initial_state = {
        "messages": current_messages,
        "system_prompt": system_prompt
    }
    
    # Invoke the agent and stream until completion
    final_response = ""
    for event in agent_app.stream(initial_state, config, stream_mode="updates"):
        # Process each update
        for _, node_state in event.items():
            if "messages" in node_state:
                messages = node_state["messages"]
                # Get the last message
                if messages:
                    last_msg = messages[-1]
                    if isinstance(last_msg, AIMessage):
                        if last_msg.content:
                            final_response = last_msg.content
    
    # If we didn't get a response, try to extract from final state
    if not final_response:
        final_state = agent_app.get_state(config)
        if final_state.values:
            messages = final_state.values.get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    if hasattr(msg, 'content') and msg.content:
                        final_response = msg.content
                        break
    
    return final_response or "I'm processing your request..."
