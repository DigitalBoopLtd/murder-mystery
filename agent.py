"""LangGraph agent for the game master."""
import os
import logging
from typing import Annotated, TypedDict, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import CheckpointTuple
from langgraph.types import RunnableConfig
from game_tools import interrogate_suspect

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    
    # Create tool node with logging wrapper
    base_tool_node = ToolNode(tools)
    
    def tool_node(state: AgentState):
        logger.info("=== TOOL NODE CALLED ===")
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                logger.info(f"Executing {len(last_msg.tool_calls)} tool call(s)")
                for i, tc in enumerate(last_msg.tool_calls):
                    tool_name = tc.get('name', 'unknown') if isinstance(tc, dict) else getattr(tc, 'name', 'unknown')
                    logger.info(f"  Tool {i+1}: {tool_name}")
        result = base_tool_node.invoke(state)
        logger.info("=== TOOL NODE COMPLETE ===")
        return result
    
    # Define the agent node
    def agent_node(state: AgentState):
        messages = state["messages"]
        logger.info(f"=== AGENT NODE CALLED ===")
        logger.info(f"Number of messages in state: {len(messages)}")
        
        # CRITICAL: If we only have a ToolMessage, we need to load full history from checkpoint
        # This happens when LangGraph doesn't properly merge checkpoint state
        if len(messages) == 1 and isinstance(messages[0], ToolMessage):
            logger.warning("WARNING: Agent node only has ToolMessage! Loading full state from checkpoint...")
            # Try to get full state from the config if available
            # Actually, we can't access config here, so we need to ensure the state has all messages
            # The real fix is in how we pass state to stream()
            logger.warning("State only contains ToolMessage - this indicates checkpoint merge issue")
        
        # Log ALL messages for full context
        logger.info(f"=== FULL MESSAGE HISTORY ({len(messages)} messages) ===")
        for i, msg in enumerate(messages):
            if isinstance(msg, HumanMessage):
                logger.info(f"Message {i} (Human): {msg.content[:200]}...")
            elif isinstance(msg, AIMessage):
                logger.info(f"Message {i} (AI): {msg.content[:200] if msg.content else 'No content'}...")
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    logger.info(f"  -> Has {len(msg.tool_calls)} tool call(s): {[tc.get('name', 'unknown') if isinstance(tc, dict) else getattr(tc, 'name', 'unknown') for tc in msg.tool_calls]}")
            elif isinstance(msg, SystemMessage):
                logger.info(f"Message {i} (System): {msg.content[:200]}...")
            elif isinstance(msg, ToolMessage):
                logger.info(f"Message {i} (Tool): tool_call_id={getattr(msg, 'tool_call_id', 'N/A')}, content={str(msg.content)[:100]}...")
        logger.info(f"=== END MESSAGE HISTORY ===")
        
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
        
        logger.info(f"Invoking LLM with {len(filtered_messages)} filtered messages")
        response = llm_with_tools.invoke(filtered_messages)
        
        # Log the response
        if isinstance(response, AIMessage):
            logger.info(f"LLM Response: {response.content[:200] if response.content else 'No content'}...")
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"  -> LLM wants to call {len(response.tool_calls)} tool(s)")
                for i, tc in enumerate(response.tool_calls):
                    tool_name = tc.get('name', 'unknown') if isinstance(tc, dict) else getattr(tc, 'name', 'unknown')
                    tool_args = tc.get('args', {}) if isinstance(tc, dict) else getattr(tc, 'args', {})
                    logger.info(f"    Tool {i+1}: {tool_name} with args: {tool_args}")
            else:
                logger.info("  -> LLM did NOT request any tool calls")
        
        return {"messages": [response]}
    
    # Define routing logic
    def should_continue(state: AgentState):
        messages = state["messages"]
        if not messages:
            logger.info("=== ROUTING: No messages, ending ===")
            return END
        
        last_message = messages[-1]
        
        # If the last message has tool calls, route to tools
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            logger.info(f"=== ROUTING: Routing to TOOLS (found {len(last_message.tool_calls)} tool call(s)) ===")
            return "tools"
        # Otherwise, we're done
        logger.info("=== ROUTING: No tool calls, ending ===")
        return END
    
    # Build the graph with explicit reducer for messages (append, not replace)
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    # Explicitly set reducer for messages to append (this is the default, but being explicit)
    # LangGraph should automatically append for List types, but let's ensure it
    
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
    logger.info(f"\n{'='*60}")
    logger.info(f"PROCESSING MESSAGE: {user_message}")
    logger.info(f"Thread ID: {thread_id}")
    logger.info(f"{'='*60}")
    
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    
    # Get current state from checkpoint
    checkpoint_state = agent_app.get_state(config)
    current_messages = checkpoint_state.values.get("messages", []) if checkpoint_state.values else []
    logger.info(f"Current message history length from checkpoint: {len(current_messages)}")
    
    # Log checkpoint messages for debugging
    if current_messages:
        logger.info("Checkpoint messages:")
        for i, msg in enumerate(current_messages[-5:]):  # Last 5 messages
            msg_type = type(msg).__name__
            logger.info(f"  Checkpoint msg {i}: {msg_type}")
    
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
    
    # Pass only the new messages - LangGraph will merge with checkpoint automatically
    # This is the correct way to use checkpoints - pass only what's new
    new_messages = []
    # Only add system message if it's not already in checkpoint
    if not any(isinstance(msg, SystemMessage) for msg in current_messages):
        new_messages.append(SystemMessage(content=system_prompt))
    new_messages.append(HumanMessage(content=user_message))
    
    update_state = {
        "messages": new_messages,  # Only new messages - LangGraph will append to checkpoint
        "system_prompt": system_prompt
    }
    
    logger.info(f"Adding {len(new_messages)} new messages (LangGraph will merge with checkpoint)")
    
    # Invoke the agent and stream until completion
    # Pass only new messages - LangGraph will load checkpoint and merge
    logger.info("Starting agent stream...")
    final_response = ""
    event_count = 0
    for event in agent_app.stream(update_state, config, stream_mode="updates"):
        event_count += 1
        logger.info(f"--- Stream event {event_count} ---")
        # Process each update
        for node_name, node_state in event.items():
            logger.info(f"Node '{node_name}' updated")
            if "messages" in node_state:
                messages = node_state["messages"]
                logger.info(f"  Messages in node state update: {len(messages)}")
                # Get the last message
                if messages:
                    last_msg = messages[-1]
                    if isinstance(last_msg, AIMessage):
                        if last_msg.content:
                            final_response = last_msg.content
                            logger.info(f"  Final response updated: {final_response[:200]}...")
    
    # Always check final state to get the complete response
    # The stream might not capture the final response correctly
    logger.info("Checking final state from checkpoint...")
    final_state = agent_app.get_state(config)
    if final_state.values:
        messages = final_state.values.get("messages", [])
        logger.info(f"Final checkpoint state has {len(messages)} messages")
        # Log last few messages for debugging
        for i, msg in enumerate(messages[-3:], start=max(0, len(messages)-3)):
            msg_type = type(msg).__name__
            if isinstance(msg, AIMessage):
                logger.info(f"  Final msg {i} ({msg_type}): {msg.content[:100] if msg.content else 'No content'}...")
            else:
                logger.info(f"  Final msg {i} ({msg_type})")
        
        # Get the last AIMessage with content as the final response
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                if hasattr(msg, 'content') and msg.content:
                    final_response = msg.content
                    logger.info(f"Extracted final response from checkpoint: {final_response[:200]}...")
                    break
    
    logger.info(f"Returning response: {final_response[:200] if final_response else 'Empty'}...")
    logger.info(f"{'='*60}\n")
    return final_response or "I'm processing your request..."
