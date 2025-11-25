"""LangGraph agent for the game master."""

import os
import logging
from typing import Annotated, TypedDict, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    BaseMessage,
    ToolMessage,
)
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
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
    llm = ChatOpenAI(model="gpt-5.1", api_key=os.getenv("OPENAI_API_KEY"))

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
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                logger.info(f"Executing {len(last_msg.tool_calls)} tool call(s)")
                for i, tc in enumerate(last_msg.tool_calls):
                    tool_name = (
                        tc.get("name", "unknown")
                        if isinstance(tc, dict)
                        else getattr(tc, "name", "unknown")
                    )
                    logger.info(f"  Tool {i+1}: {tool_name}")
        result = base_tool_node.invoke(state)
        logger.info("=== TOOL NODE COMPLETE ===")
        return result

    # Define the agent node
    def agent_node(state: AgentState):
        messages = state["messages"]
        system_prompt = state.get("system_prompt", "")

        logger.info(f"=== AGENT NODE CALLED ===")
        logger.info(f"Number of messages in state: {len(messages)}")

        # Log message types for debugging
        msg_types = [type(m).__name__ for m in messages]
        logger.info(f"Message types: {msg_types}")

        # SPECIAL CASE: If we only have a ToolMessage, LangGraph didn't preserve full history.
        # The ToolMessage contains the suspect's response, so return it directly.
        if len(messages) == 1 and isinstance(messages[0], ToolMessage):
            tool_content = getattr(messages[0], 'content', str(messages[0]))
            logger.warning("Only ToolMessage in state - returning tool result directly as response")
            logger.info(f"Tool result content: {tool_content[:100]}...")
            return {"messages": [AIMessage(content=tool_content)]}

        # Ensure system message is present
        if not any(isinstance(msg, SystemMessage) for msg in messages):
            if system_prompt:
                messages = [SystemMessage(content=system_prompt)] + list(messages)
                logger.info("Added system message from state")

        # Build clean message list for LLM
        # OpenAI requires: SystemMessage, then alternating Human/AI, with ToolMessages after AI tool_calls
        filtered_messages = []

        for i, msg in enumerate(messages):
            if isinstance(msg, ToolMessage):
                # Find the AIMessage this tool result belongs to
                # Look backwards through ALL messages (not just filtered) to find the matching AIMessage
                tool_call_id = getattr(msg, "tool_call_id", None)
                has_matching_ai = False
                matching_ai_msg = None

                # Look backwards through all messages to find the AIMessage with matching tool_call
                for j in range(i - 1, -1, -1):
                    prev_msg = messages[j]
                    if isinstance(prev_msg, AIMessage) and hasattr(prev_msg, "tool_calls") and prev_msg.tool_calls:
                        for tc in prev_msg.tool_calls:
                            tc_id = (
                                tc.get("id")
                                if isinstance(tc, dict)
                                else getattr(tc, "id", None)
                            )
                            if tc_id == tool_call_id:
                                has_matching_ai = True
                                matching_ai_msg = prev_msg
                                break
                    if has_matching_ai:
                        break

                if has_matching_ai:
                    # Make sure the AIMessage is in filtered_messages before adding ToolMessage
                    if matching_ai_msg not in filtered_messages:
                        # Find where to insert it - should be after the last HumanMessage before this ToolMessage
                        insert_idx = len(filtered_messages)
                        for k in range(len(filtered_messages) - 1, -1, -1):
                            if isinstance(filtered_messages[k], HumanMessage):
                                insert_idx = k + 1
                                break
                        filtered_messages.insert(insert_idx, matching_ai_msg)
                        logger.info(f"Inserted matching AIMessage with tool_calls before ToolMessage")
                    filtered_messages.append(msg)
                else:
                    # CRITICAL FIX: If we can't find the matching AIMessage, LangGraph only passed
                    # the ToolMessage without full history. Since we can't create a valid AIMessage
                    # with tool_calls (the structure is complex), we'll convert the ToolMessage
                    # content to a format the LLM can understand - as if the suspect responded directly.
                    logger.warning(
                        f"ToolMessage with id {tool_call_id} has no matching AIMessage - converting to HumanMessage format"
                    )
                    # Extract the tool result content
                    tool_content = getattr(msg, 'content', str(msg))
                    # Convert to a HumanMessage that represents the suspect's response
                    # This allows the LLM to process it without needing the full tool call sequence
                    suspect_response = HumanMessage(
                        content=f"[The suspect responds:] {tool_content}"
                    )
                    filtered_messages.append(suspect_response)
                    logger.info(f"Converted ToolMessage to HumanMessage format: {tool_content[:80]}...")
            else:
                filtered_messages.append(msg)

        logger.info(f"Invoking LLM with {len(filtered_messages)} messages")

        # Log what we're sending
        for i, msg in enumerate(filtered_messages):
            if isinstance(msg, SystemMessage):
                logger.info(f"  [{i}] System: {msg.content[:100]}...")
            elif isinstance(msg, HumanMessage):
                logger.info(f"  [{i}] Human: {msg.content[:100]}...")
            elif isinstance(msg, AIMessage):
                has_tools = hasattr(msg, "tool_calls") and msg.tool_calls
                logger.info(
                    f"  [{i}] AI: {msg.content[:80] if msg.content else '(no content)'} | tools={has_tools}"
                )
            elif isinstance(msg, ToolMessage):
                logger.info(f"  [{i}] Tool: {msg.content[:80]}...")

        response = llm_with_tools.invoke(filtered_messages)

        # Log the response
        if isinstance(response, AIMessage):
            logger.info(
                f"LLM Response: {response.content[:200] if response.content else 'No content'}..."
            )
            if hasattr(response, "tool_calls") and response.tool_calls:
                logger.info(
                    f"  -> LLM wants to call {len(response.tool_calls)} tool(s)"
                )
                for i, tc in enumerate(response.tool_calls):
                    tool_name = (
                        tc.get("name", "unknown")
                        if isinstance(tc, dict)
                        else getattr(tc, "name", "unknown")
                    )
                    logger.info(f"    Tool {i+1}: {tool_name}")
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
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.info(
                f"=== ROUTING: Routing to TOOLS (found {len(last_message.tool_calls)} tool call(s)) ==="
            )
            return "tools"
        # Otherwise, we're done
        logger.info("=== ROUTING: No tool calls, ending ===")
        return END

    # Build the graph
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add conditional edges
    workflow.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", END: END}
    )

    # After tools, go back to agent
    workflow.add_edge("tools", "agent")

    # Compile with memory saver
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


def process_message(
    agent_app,
    user_message: str,
    system_prompt: str,
    session_id: str,
    thread_id: str = "default",
) -> str:
    """Process a user message through the agent."""
    logger.info(f"\n{'='*60}")
    logger.info(f"PROCESSING MESSAGE: {user_message}")
    logger.info(f"Thread ID: {thread_id}")
    logger.info(f"{'='*60}")

    config = {"configurable": {"thread_id": thread_id}}

    # Get current state from checkpoint
    checkpoint_state = agent_app.get_state(config)
    current_messages = (
        list(checkpoint_state.values.get("messages", []))
        if checkpoint_state.values
        else []
    )
    logger.info(f"Loaded {len(current_messages)} messages from checkpoint")

    # Update or add system message
    system_msg_index = None
    for i, msg in enumerate(current_messages):
        if isinstance(msg, SystemMessage):
            system_msg_index = i
            break

    if system_msg_index is not None:
        current_messages[system_msg_index] = SystemMessage(content=system_prompt)
        logger.info("Updated existing system message")
    else:
        current_messages.insert(0, SystemMessage(content=system_prompt))
        logger.info("Added new system message")

    # Add user message
    current_messages.append(HumanMessage(content=user_message))
    logger.info(f"Added user message. Total messages: {len(current_messages)}")

    # IMPORTANT: Pass the FULL message history, not just new messages
    # This ensures the agent always has complete context
    full_state = {"messages": current_messages, "system_prompt": system_prompt}

    # Stream through the graph
    logger.info("Starting agent stream with FULL state...")
    final_response = ""

    for event in agent_app.stream(full_state, config, stream_mode="values"):
        # In "values" mode, we get the full state after each node
        if "messages" in event:
            messages = event["messages"]
            if messages:
                last_msg = messages[-1]
                if isinstance(last_msg, AIMessage) and last_msg.content:
                    final_response = last_msg.content
                    logger.info(f"Got AI response: {final_response[:100]}...")

    # Double-check by getting final state
    if not final_response:
        logger.info("No response from stream, checking final state...")
        final_state = agent_app.get_state(config)
        if final_state.values:
            messages = final_state.values.get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    final_response = msg.content
                    logger.info(
                        f"Got response from final state: {final_response[:100]}..."
                    )
                    break

    logger.info(f"Returning: {final_response[:200] if final_response else 'Empty'}...")
    logger.info(f"{'='*60}\n")

    return final_response or "I'm processing your request..."
