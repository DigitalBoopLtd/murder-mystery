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
from game.tools import interrogate_suspect

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the game master agent."""

    messages: Annotated[List[BaseMessage], "The conversation messages"]
    system_prompt: str


def create_game_master_agent():
    """Create a game master agent with tools."""
    # max_tokens=600 allows for richer narrative responses when searching locations
    # while still keeping responses reasonably short for voice narration
    llm = ChatOpenAI(
        model="gpt-5.1", max_tokens=600, api_key=os.getenv("OPENAI_API_KEY")
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
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                logger.info("Executing %d tool call(s)", len(last_msg.tool_calls))
                for i, tc in enumerate(last_msg.tool_calls):
                    tool_name = (
                        tc.get("name", "unknown")
                        if isinstance(tc, dict)
                        else getattr(tc, "name", "unknown")
                    )
                    logger.info("  Tool %d: %s", i + 1, tool_name)
        result = base_tool_node.invoke(state)
        logger.info("=== TOOL NODE COMPLETE ===")
        return result

    # Define the agent node
    def agent_node(state: AgentState):
        messages = state["messages"]
        system_prompt = state.get("system_prompt", "")

        logger.info("=== AGENT NODE CALLED ===")
        logger.info("Number of messages in state: %d", len(messages))

        # Log message types for debugging
        msg_types = [type(m).__name__ for m in messages]
        logger.info("Message types: %s", msg_types)

        # SPECIAL CASE: If we only have a ToolMessage, LangGraph didn't preserve full history.
        # The ToolMessage contains the suspect's response, so return it directly.
        if len(messages) == 1 and isinstance(messages[0], ToolMessage):
            tool_content = getattr(messages[0], "content", str(messages[0]))
            logger.warning(
                "Only ToolMessage in state - returning tool result directly as response"
            )
            logger.info("Tool result content: %s...", tool_content[:100])
            return {"messages": [AIMessage(content=tool_content)]}

        # Ensure system message is present
        if not any(isinstance(msg, SystemMessage) for msg in messages):
            if system_prompt:
                messages = [SystemMessage(content=system_prompt)] + list(messages)
                logger.info("Added system message from state")

        # Build clean message list for LLM
        # OpenAI requires: SystemMessage, then alternating Human/AI,
        # with ToolMessages after AI tool_calls
        filtered_messages = []

        for i, msg in enumerate(messages):
            if isinstance(msg, ToolMessage):
                # Find the AIMessage this tool result belongs to
                # Look backwards through ALL messages (not just filtered) to find the matching AIMessage
                tool_call_id = getattr(msg, "tool_call_id", None)
                has_matching_ai = False
                matching_ai_msg = None

                # Look backwards to find the AIMessage with matching tool_call
                for j in range(i - 1, -1, -1):
                    prev_msg = messages[j]
                    if (
                        isinstance(prev_msg, AIMessage)
                        and hasattr(prev_msg, "tool_calls")
                        and prev_msg.tool_calls
                    ):
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
                        # Insert after the last HumanMessage before this ToolMessage
                        insert_idx = len(filtered_messages)
                        for k in range(len(filtered_messages) - 1, -1, -1):
                            if isinstance(filtered_messages[k], HumanMessage):
                                insert_idx = k + 1
                                break
                        filtered_messages.insert(insert_idx, matching_ai_msg)
                        logger.info(
                            "Inserted matching AIMessage with tool_calls before ToolMessage"
                        )
                    filtered_messages.append(msg)
                else:
                    # CRITICAL FIX: If we can't find the matching AIMessage, LangGraph
                    # only passed the ToolMessage without full history. Convert it to
                    # a HumanMessage format the LLM can understand.
                    logger.warning(
                        "ToolMessage id %s has no matching AIMessage - converting",
                        tool_call_id,
                    )
                    # Extract the tool result content
                    tool_content = getattr(msg, "content", str(msg))
                    # Convert to a HumanMessage that represents the suspect's response
                    # This allows the LLM to process it without needing the full tool call sequence
                    suspect_response = HumanMessage(
                        content=f"[The suspect responds:] {tool_content}"
                    )
                    filtered_messages.append(suspect_response)
                    logger.info(
                        "Converted ToolMessage to HumanMessage format: %s...",
                        tool_content[:80],
                    )
            else:
                filtered_messages.append(msg)

        logger.info("Invoking LLM with %d messages", len(filtered_messages))

        # Log what we're sending
        for i, msg in enumerate(filtered_messages):
            if isinstance(msg, SystemMessage):
                logger.info("  [%d] System: %s...", i, msg.content[:100])
            elif isinstance(msg, HumanMessage):
                logger.info("  [%d] Human: %s...", i, msg.content[:100])
            elif isinstance(msg, AIMessage):
                has_tools = hasattr(msg, "tool_calls") and msg.tool_calls
                logger.info(
                    "  [%d] AI: %s | tools=%s",
                    i,
                    msg.content[:80] if msg.content else "(no content)",
                    has_tools,
                )
            elif isinstance(msg, ToolMessage):
                logger.info("  [%d] Tool: %s...", i, msg.content[:80])

        response = llm_with_tools.invoke(filtered_messages)

        # Log the response
        if isinstance(response, AIMessage):
            logger.info(
                "LLM Response: %s...",
                response.content[:200] if response.content else "No content",
            )
            if hasattr(response, "tool_calls") and response.tool_calls:
                logger.info(
                    "  -> LLM wants to call %d tool(s)", len(response.tool_calls)
                )
                for i, tc in enumerate(response.tool_calls):
                    tool_name = (
                        tc.get("name", "unknown")
                        if isinstance(tc, dict)
                        else getattr(tc, "name", "unknown")
                    )
                    logger.info("    Tool %d: %s", i + 1, tool_name)
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
                "=== ROUTING: Routing to TOOLS (found %d tool call(s)) ===",
                len(last_message.tool_calls),
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
    _session_id: str,
    thread_id: str = "default",
) -> tuple[str, str | None]:
    """Process a user message through the agent.

    Returns:
        Tuple of (response, speaker_name) where speaker_name is:
        - Suspect name if response is from a suspect
        - None if response is from Game Master
    """
    logger.info("\n%s", "=" * 60)
    logger.info("PROCESSING MESSAGE: %s", user_message)
    logger.info("Thread ID: %s", thread_id)
    logger.info("%s", "=" * 60)

    config = {"configurable": {"thread_id": thread_id}}

    # Get current state from checkpoint
    checkpoint_state = agent_app.get_state(config)
    current_messages = (
        list(checkpoint_state.values.get("messages", []))
        if checkpoint_state.values
        else []
    )
    logger.info("Loaded %d messages from checkpoint", len(current_messages))

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
    logger.info("Added user message. Total messages: %d", len(current_messages))

    # IMPORTANT: Pass the FULL message history, not just new messages
    # This ensures the agent always has complete context
    full_state = {"messages": current_messages, "system_prompt": system_prompt}

    # Store a reference to the checkpoint state before streaming
    # This allows us to look up the original AIMessage with tool_calls
    # even after the agent node processes the ToolMessage
    _ = agent_app.get_state(config)  # Reference for potential future use

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
                    has_tool_calls = (
                        hasattr(last_msg, "tool_calls") and last_msg.tool_calls
                    )
                    if has_tool_calls:
                        logger.info(
                            "Got AIMessage with %d tool call(s)",
                            len(last_msg.tool_calls),
                        )
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
                                    logger.info(
                                        "Extracted suspect name from AIMessage with tool_calls: %s",
                                        suspect_name,
                                    )
                                    break
                    elif last_msg.content:
                        # AIMessage with content but no tool_calls - this is a final response
                        final_response = last_msg.content
                        logger.info("Got AI response: %s...", final_response[:100])
                elif isinstance(last_msg, ToolMessage):
                    # Store tool message content and extract suspect name
                    tool_message_content = getattr(last_msg, "content", str(last_msg))
                    tool_call_id = getattr(last_msg, "tool_call_id", None)
                    logger.info("Got ToolMessage: %s...", tool_message_content[:100])
                    logger.info("ToolMessage has tool_call_id: %s", tool_call_id)
                    logger.info("Event messages array has %d messages", len(messages))

                    # Look backwards in current event messages
                    for i, msg in enumerate(reversed(messages)):
                        msg_type = type(msg).__name__
                        logger.info(
                            "  Checking message %d: %s", len(messages) - i - 1, msg_type
                        )
                        if (
                            isinstance(msg, AIMessage)
                            and hasattr(msg, "tool_calls")
                            and msg.tool_calls
                        ):
                            logger.info(
                                "  Found AIMessage with %d tool call(s)",
                                len(msg.tool_calls),
                            )
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
                                logger.info("    Tool: %s, ID: %s", tool_name, tc_id)
                                if tool_name == "interrogate_suspect":
                                    # Extract suspect_name from tool call arguments
                                    args = (
                                        tc.get("args", {})
                                        if isinstance(tc, dict)
                                        else getattr(tc, "args", {})
                                    )
                                    if isinstance(args, dict):
                                        suspect_name = args.get("suspect_name")
                                        logger.info(
                                            "Found suspect response from: %s",
                                            suspect_name,
                                        )
                                    break
                            if suspect_name:
                                break

                    # If not found in event messages, check checkpoint state
                    # This handles the case where LangGraph only passed the ToolMessage
                    if not suspect_name:
                        logger.info(
                            "Suspect name not found, checking checkpoint state..."
                        )
                        logger.info("Looking for tool_call_id: %s", tool_call_id)
                        # Get checkpoint state after tool node executed
                        post_tool_checkpoint = agent_app.get_state(config)
                        if post_tool_checkpoint.values:
                            checkpoint_messages = post_tool_checkpoint.values.get(
                                "messages", []
                            )
                            logger.info(
                                "Checking %d messages in post-tool checkpoint",
                                len(checkpoint_messages),
                            )
                            # Log all message types for debugging
                            msg_types = [type(m).__name__ for m in checkpoint_messages]
                            logger.info("Message types in checkpoint: %s", msg_types)

                            # Look for AIMessage with tool_calls that matches this ToolMessage
                            for i, msg in enumerate(reversed(checkpoint_messages)):
                                if (
                                    isinstance(msg, AIMessage)
                                    and hasattr(msg, "tool_calls")
                                    and msg.tool_calls
                                ):
                                    logger.info(
                                        "Found AIMessage at index %d with %d tool call(s)",
                                        len(checkpoint_messages) - i - 1,
                                        len(msg.tool_calls),
                                    )
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
                                        logger.info(
                                            "  Tool call %d: %s, ID: %s",
                                            j,
                                            tool_name,
                                            tc_id,
                                        )

                                        # Match by tool_call_id if available
                                        if tool_call_id:
                                            if tc_id == tool_call_id:
                                                logger.info("  Matched tool_call_id!")
                                                if tool_name == "interrogate_suspect":
                                                    args = (
                                                        tc.get("args", {})
                                                        if isinstance(tc, dict)
                                                        else getattr(tc, "args", {})
                                                    )
                                                    if isinstance(args, dict):
                                                        suspect_name = args.get(
                                                            "suspect_name"
                                                        )
                                                        logger.info(
                                                            "Found suspect name in checkpoint: %s",
                                                            suspect_name,
                                                        )
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
                                                logger.info(
                                                    "Found suspect in checkpoint: %s",
                                                    suspect_name,
                                                )
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
                        tool_message_content = getattr(msg, "content", str(msg))
                    # Extract suspect name from preceding AIMessage with tool_calls
                    tool_call_id = getattr(msg, "tool_call_id", None)
                    for prev_msg in reversed(messages[: messages.index(msg)]):
                        if (
                            isinstance(prev_msg, AIMessage)
                            and hasattr(prev_msg, "tool_calls")
                            and prev_msg.tool_calls
                        ):
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
                                    logger.info(
                                        "Found suspect name in final state: %s",
                                        suspect_name,
                                    )
                                break
                            if suspect_name:
                                break
                if isinstance(msg, AIMessage) and msg.content and not final_response:
                    final_response = msg.content
                    logger.info(
                        "Got response from final state: %s...", final_response[:100]
                    )

            # Also check for ToolMessage in final state if we still don't have a response
            if not final_response:
                for msg in reversed(messages):
                    if isinstance(msg, ToolMessage):
                        tool_content = getattr(msg, "content", str(msg))
                        final_response = tool_content
                        logger.info(
                            "Using ToolMessage from final state: %s...",
                            tool_content[:100],
                        )
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
            logger.info(
                "Tool message embedded in final response - suspect spoke, Game Master narrating"
            )
            # Keep suspect_name to show suspect is speaking
        else:
            # Final response is completely different - Game Master is narrating
            logger.info(
                "Final response differs from tool message - Game Master narration"
            )
            suspect_name = None
    elif not suspect_name:
        # No tool call found - this is Game Master narration
        logger.info("No suspect tool call found - Game Master response")

    logger.info("Returning: %s...", final_response[:200] if final_response else "Empty")
    logger.info("Speaker: %s", suspect_name or "Game Master")
    logger.info("%s\n", "=" * 60)

    return (final_response or "I'm processing your request...", suspect_name)
