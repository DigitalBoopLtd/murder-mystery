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
    # max_tokens=80 keeps responses to ~50-60 words → 10-20 seconds of speech
    llm = ChatOpenAI(model="gpt-5.1", max_tokens=80, api_key=os.getenv("OPENAI_API_KEY"))

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
) -> tuple[str, str | None]:
    """Process a user message through the agent.
    
    Returns:
        Tuple of (response, speaker_name) where speaker_name is:
        - Suspect name if response is from a suspect
        - None if response is from Game Master
    """
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

    # Store a reference to the checkpoint state before streaming
    # This allows us to look up the original AIMessage with tool_calls
    # even after the agent node processes the ToolMessage
    pre_stream_checkpoint = agent_app.get_state(config)

    # Stream through the graph
    logger.info("Starting agent stream with FULL state...")
    final_response = ""
    suspect_name = None
    tool_message_content = None

    for event in agent_app.stream(full_state, config, stream_mode="values"):
        # In "values" mode, we get the full state after each node
        if "messages" in event:
            messages = event["messages"]
            if messages:
                last_msg = messages[-1]
                
                # Check for AIMessage with tool_calls (before tool node executes)
                # This is when we can extract the suspect name
                if isinstance(last_msg, AIMessage):
                    has_tool_calls = hasattr(last_msg, "tool_calls") and last_msg.tool_calls
                    if has_tool_calls:
                        logger.info(f"Got AIMessage with {len(last_msg.tool_calls)} tool call(s)")
                        for tc in last_msg.tool_calls:
                            tool_name = (
                                tc.get("name", "")
                                if isinstance(tc, dict)
                                else getattr(tc, "name", "")
                            )
                            if tool_name == "interrogate_suspect":
                                args = (
                                    tc.get("args", {})
                                    if isinstance(tc, dict)
                                    else getattr(tc, "args", {})
                                )
                                if isinstance(args, dict):
                                    suspect_name = args.get("suspect_name")
                                    logger.info(f"Extracted suspect name from AIMessage with tool_calls: {suspect_name}")
                                    break
                    elif last_msg.content:
                        # AIMessage with content but no tool_calls - this is a final response
                        final_response = last_msg.content
                        logger.info(f"Got AI response: {final_response[:100]}...")
                elif isinstance(last_msg, ToolMessage):
                    # Store tool message content and extract suspect name
                    tool_message_content = getattr(last_msg, 'content', str(last_msg))
                    tool_call_id = getattr(last_msg, "tool_call_id", None)
                    logger.info(f"Got ToolMessage: {tool_message_content[:100]}...")
                    logger.info(f"ToolMessage has tool_call_id: {tool_call_id}")
                    logger.info(f"Event messages array has {len(messages)} messages")
                    
                    # Look backwards in current event messages
                    for i, msg in enumerate(reversed(messages)):
                        msg_type = type(msg).__name__
                        logger.info(f"  Checking message {len(messages)-i-1}: {msg_type}")
                        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                            logger.info(f"  Found AIMessage with {len(msg.tool_calls)} tool call(s)")
                            for tc in msg.tool_calls:
                                tool_name = (
                                    tc.get("name", "")
                                    if isinstance(tc, dict)
                                    else getattr(tc, "name", "")
                                )
                                tc_id = (
                                    tc.get("id")
                                    if isinstance(tc, dict)
                                    else getattr(tc, "id", None)
                                )
                                logger.info(f"    Tool: {tool_name}, ID: {tc_id}")
                                if tool_name == "interrogate_suspect":
                                    # Extract suspect_name from tool call arguments
                                    args = (
                                        tc.get("args", {})
                                        if isinstance(tc, dict)
                                        else getattr(tc, "args", {})
                                    )
                                    if isinstance(args, dict):
                                        suspect_name = args.get("suspect_name")
                                        logger.info(f"Found suspect response from: {suspect_name}")
                                    break
                            if suspect_name:
                                break
                    
                    # If we didn't find it in the event messages, check the checkpoint state right now
                    # This handles the case where LangGraph only passed the ToolMessage
                    # The checkpoint state right after tool execution should have the full history
                    if not suspect_name:
                        logger.info(f"Suspect name not found in event messages, checking checkpoint state after tool execution...")
                        logger.info(f"Looking for tool_call_id: {tool_call_id}")
                        # Get the checkpoint state right after tool node executed (before agent node processes it)
                        post_tool_checkpoint = agent_app.get_state(config)
                        if post_tool_checkpoint.values:
                            checkpoint_messages = post_tool_checkpoint.values.get("messages", [])
                            logger.info(f"Checking {len(checkpoint_messages)} messages in post-tool checkpoint")
                            # Log all message types for debugging
                            msg_types = [type(m).__name__ for m in checkpoint_messages]
                            logger.info(f"Message types in checkpoint: {msg_types}")
                            
                            # Look for AIMessage with tool_calls that matches this ToolMessage
                            for i, msg in enumerate(reversed(checkpoint_messages)):
                                if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                                    logger.info(f"Found AIMessage at index {len(checkpoint_messages)-i-1} with {len(msg.tool_calls)} tool call(s)")
                                    for j, tc in enumerate(msg.tool_calls):
                                        tc_id = (
                                            tc.get("id")
                                            if isinstance(tc, dict)
                                            else getattr(tc, "id", None)
                                        )
                                        tool_name = (
                                            tc.get("name", "")
                                            if isinstance(tc, dict)
                                            else getattr(tc, "name", "")
                                        )
                                        logger.info(f"  Tool call {j}: {tool_name}, ID: {tc_id}")
                                        
                                        # Match by tool_call_id if available, otherwise check tool name
                                        if tool_call_id:
                                            if tc_id == tool_call_id:
                                                logger.info(f"  Matched tool_call_id!")
                                                if tool_name == "interrogate_suspect":
                                                    args = (
                                                        tc.get("args", {})
                                                        if isinstance(tc, dict)
                                                        else getattr(tc, "args", {})
                                                    )
                                                    if isinstance(args, dict):
                                                        suspect_name = args.get("suspect_name")
                                                        logger.info(f"Found suspect name in checkpoint: {suspect_name}")
                                                        break
                                        elif tool_name == "interrogate_suspect":
                                            # If no tool_call_id, just check tool name
                                            args = (
                                                tc.get("args", {})
                                                if isinstance(tc, dict)
                                                else getattr(tc, "args", {})
                                            )
                                            if isinstance(args, dict):
                                                suspect_name = args.get("suspect_name")
                                                logger.info(f"Found suspect name in checkpoint (no tool_call_id match): {suspect_name}")
                                                break
                                    if suspect_name:
                                        break

    # Double-check by getting final state (for response and/or suspect name)
    if not final_response or not suspect_name:
        logger.info("Checking final state for response and/or suspect name...")
        final_state = agent_app.get_state(config)
        if final_state.values:
            messages = final_state.values.get("messages", [])
            # Look for suspect name in tool calls and ToolMessage
            for msg in reversed(messages):
                if isinstance(msg, ToolMessage):
                    if not tool_message_content:
                        tool_message_content = getattr(msg, 'content', str(msg))
                    # Extract suspect name from preceding AIMessage with tool_calls
                    tool_call_id = getattr(msg, "tool_call_id", None)
                    for prev_msg in reversed(messages[:messages.index(msg)]):
                        if isinstance(prev_msg, AIMessage) and hasattr(prev_msg, "tool_calls") and prev_msg.tool_calls:
                            for tc in prev_msg.tool_calls:
                                # Match by tool_call_id if available
                                if tool_call_id:
                                    tc_id = (
                                        tc.get("id")
                                        if isinstance(tc, dict)
                                        else getattr(tc, "id", None)
                                    )
                                    if tc_id != tool_call_id:
                                        continue
                                
                                tool_name = (
                                    tc.get("name", "")
                                    if isinstance(tc, dict)
                                    else getattr(tc, "name", "")
                                )
                                if tool_name == "interrogate_suspect":
                                    args = (
                                        tc.get("args", {})
                                        if isinstance(tc, dict)
                                        else getattr(tc, "args", {})
                                    )
                                    if isinstance(args, dict):
                                        suspect_name = args.get("suspect_name")
                                        logger.info(f"Found suspect name in final state: {suspect_name}")
                                    break
                            if suspect_name:
                                break
                if isinstance(msg, AIMessage) and msg.content and not final_response:
                    final_response = msg.content
                    logger.info(
                        f"Got response from final state: {final_response[:100]}..."
                    )
            
            # Also check for ToolMessage in final state if we still don't have a response
            if not final_response:
                for msg in reversed(messages):
                    if isinstance(msg, ToolMessage):
                        tool_content = getattr(msg, 'content', str(msg))
                        final_response = tool_content
                        logger.info(f"Using ToolMessage from final state: {tool_content[:100]}...")
                        break

    # Determine if the response is directly from the suspect
    # If we detected a suspect tool call, check if the final response is the tool result
    # or if it's been wrapped/transformed by the Game Master
    if tool_message_content and suspect_name:
        # Check if final response matches or contains the tool message content
        tool_content_clean = tool_message_content.strip()
        final_response_clean = final_response.strip()
        
        if final_response_clean == tool_content_clean:
            # Direct suspect response - use it as-is
            logger.info("Final response matches tool message - direct suspect response")
            final_response = tool_content_clean  # Use the tool message directly
        elif tool_content_clean in final_response_clean:
            # Tool message is embedded - likely Game Master is narrating, but suspect spoke
            # We'll still attribute to suspect if the tool content is a significant part
            logger.info("Tool message embedded in final response - suspect spoke, Game Master narrating")
            # Keep suspect_name to show suspect is speaking
        else:
            # Final response is completely different - Game Master is narrating
            logger.info("Final response differs from tool message - Game Master narration")
            suspect_name = None
    elif not suspect_name:
        # No tool call found - this is Game Master narration
        logger.info("No suspect tool call found - Game Master response")

    logger.info(f"Returning: {final_response[:200] if final_response else 'Empty'}...")
    logger.info(f"Speaker: {suspect_name or 'Game Master'}")
    logger.info(f"{'='*60}\n")

    return (final_response or "I'm processing your request...", suspect_name)
