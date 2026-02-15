"""
Orchestrator Session Runner
===========================

Runs orchestrated sessions where the main agent delegates to specialized agents.
"""

import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from agent import SESSION_CONTINUE, SESSION_ERROR, SessionResult
from artifact_detector import get_artifact_detector
from progress import LINEAR_PROJECT_MARKER


def extract_token_counts(msg: AssistantMessage) -> Tuple[int, int]:
    """
    Extract token counts from Claude SDK AssistantMessage.

    Attempts to extract input_tokens and output_tokens from the message.
    Falls back to sensible defaults if metadata is unavailable.

    Args:
        msg: AssistantMessage from the Claude SDK

    Returns:
        Tuple of (input_tokens, output_tokens)
        Defaults to (500, 1000) if extraction fails
    """
    try:
        # The SDK response includes usage metadata on the message object
        # Check for various possible attributes where usage info might be

        # Try direct usage attribute (standard approach)
        if hasattr(msg, 'usage') and msg.usage:
            usage = msg.usage
            input_tokens = getattr(usage, 'input_tokens', None)
            output_tokens = getattr(usage, 'output_tokens', None)
            if input_tokens is None:
                input_tokens = getattr(usage, 'prompt_tokens', None)
            if output_tokens is None:
                output_tokens = getattr(usage, 'completion_tokens', None)
            if input_tokens is not None and output_tokens is not None:
                return (int(input_tokens), int(output_tokens))

        # Try model attribute (some SDK versions include usage here)
        if hasattr(msg, 'model') and msg.model:
            # Model info might have usage attached
            model_obj = msg.model
            if hasattr(model_obj, 'usage'):
                usage = model_obj.usage
                input_tokens = getattr(usage, 'input_tokens', None)
                output_tokens = getattr(usage, 'output_tokens', None)
                if input_tokens is None:
                    input_tokens = getattr(usage, 'prompt_tokens', None)
                if output_tokens is None:
                    output_tokens = getattr(usage, 'completion_tokens', None)
                if input_tokens is not None and output_tokens is not None:
                    return (int(input_tokens), int(output_tokens))

        # Try metadata attribute
        if hasattr(msg, 'metadata') and msg.metadata:
            metadata = msg.metadata
            if isinstance(metadata, dict):
                input_tokens = metadata.get('input_tokens')
                if input_tokens is None:
                    input_tokens = metadata.get('prompt_tokens')
                output_tokens = metadata.get('output_tokens')
                if output_tokens is None:
                    output_tokens = metadata.get('completion_tokens')
                if input_tokens is not None and output_tokens is not None:
                    return (int(input_tokens), int(output_tokens))
            elif hasattr(metadata, 'input_tokens'):
                input_tokens = getattr(metadata, 'input_tokens', None)
                output_tokens = getattr(metadata, 'output_tokens', None)
                if input_tokens is None:
                    input_tokens = getattr(metadata, 'prompt_tokens', None)
                if output_tokens is None:
                    output_tokens = getattr(metadata, 'completion_tokens', None)
                if input_tokens is not None and output_tokens is not None:
                    return (int(input_tokens), int(output_tokens))

        # Try _usage private attribute (fallback)
        if hasattr(msg, '_usage') and msg._usage:
            usage = msg._usage
            input_tokens = getattr(usage, 'input_tokens', None)
            output_tokens = getattr(usage, 'output_tokens', None)
            if input_tokens is None:
                input_tokens = getattr(usage, 'prompt_tokens', None)
            if output_tokens is None:
                output_tokens = getattr(usage, 'completion_tokens', None)
            if input_tokens is not None and output_tokens is not None:
                return (int(input_tokens), int(output_tokens))

    except (AttributeError, TypeError, ValueError) as e:
        # Log extraction attempt failure but don't crash
        pass

    # Default fallback values based on typical model usage patterns
    # These are conservative estimates for haiku-class models
    return (500, 1000)


async def run_orchestrated_session(
    client: ClaudeSDKClient,
    project_dir: Path,
    session_id: Optional[str] = None,
    metrics_collector: Optional[object] = None,
) -> SessionResult:
    """
    Run an orchestrated session with an initial task prompt.

    Args:
        client: Claude SDK client (must already be configured with orchestrator
            prompt and agent definitions)
        project_dir: Project directory path, included in the initial message to
            tell the orchestrator where to work
        session_id: Optional session ID for metrics tracking
        metrics_collector: Optional AgentMetricsCollector instance for tracking delegations

    Returns:
        SessionResult with status and response text:
        - status="continue": Normal completion, agent can continue
        - status="error": Exception occurred during orchestration

    The orchestrator will use the Task tool to delegate to specialized agents
    (linear, coding, github, slack) based on the work needed.
    """
    initial_message = f"""
    Start a new session. Your working directory is: {project_dir}

    Issue tracker: Linear (use the `linear` agent for all issue operations)

    Begin by:
    1. Reading {LINEAR_PROJECT_MARKER} to understand project state
    2. Checking Linear for current issue status via the `linear` agent
    3. Deciding what to work on next
    4. Delegating to appropriate agents
    """

    print("Starting orchestrated session...\n")

    try:
        await client.query(initial_message)

        response_text: str = ""

        # Track Task tool delegations
        # Map of tool_use_id -> (agent_name, ticket_key)
        active_delegations: dict[str, tuple[str, str]] = {}

        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                # Extract token counts from SDK response metadata (AI-52)
                input_tokens, output_tokens = extract_token_counts(msg)

                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
                        print(block.text, end="", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        print(f"\n[Tool: {block.name}]", flush=True)

                        # Detect Task tool delegation
                        if block.name == "Task" and metrics_collector and session_id:
                            try:
                                # Extract agent name and task from tool input
                                task_input = block.input if hasattr(block, 'input') else {}
                                agent_name = task_input.get("agent", "unknown")
                                task_description = task_input.get("task", "")

                                # Try to extract ticket key from task description
                                # Common patterns: "AI-51", "Work on AI-51", etc.
                                ticket_match = re.search(r'\b(AI-\d+)\b', task_description)
                                ticket_key = ticket_match.group(1) if ticket_match else "unknown"

                                # Store delegation info for matching with result
                                # Include extracted token counts (AI-52: actual from SDK response)
                                # Note: We only store (agent_name, ticket_key, input_tokens, output_tokens)
                                # timing is handled automatically by metrics_collector.track_agent()
                                active_delegations[block.id] = (agent_name, ticket_key, input_tokens, output_tokens)

                                print(f"   [Delegation tracked: {agent_name} on {ticket_key}]", flush=True)
                            except Exception as e:
                                print(f"   [Warning: Failed to track delegation: {e}]", flush=True)

            elif isinstance(msg, UserMessage):
                # Process tool results to capture delegation completion
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        # Check if this is a Task tool result
                        if hasattr(block, 'tool_use_id') and block.tool_use_id in active_delegations:
                            try:
                                # Unpack stored delegation info including token counts (AI-52)
                                agent_name, ticket_key, input_tokens, output_tokens = active_delegations[block.tool_use_id]

                                # Determine if delegation succeeded or failed
                                is_error = bool(block.is_error) if hasattr(block, 'is_error') and block.is_error else False
                                status = "error" if is_error else "success"

                                # Track the delegation event
                                # TODO(AI-51): Get model name from SDK response metadata
                                # Currently defaulting to claude-haiku-4-5, but should detect
                                # the actual model used by each agent from the SDK response.
                                # Check if response includes model info in metadata/usage fields.
                                model_used = "claude-haiku-4-5"  # Default for most agents

                                # Create a tracker context for this completed delegation
                                with metrics_collector.track_agent(
                                    agent_name=agent_name,
                                    ticket_key=ticket_key,
                                    model_used=model_used,
                                    session_id=session_id
                                ) as tracker:
                                    # AI-52: Extract real token counts from SDK metadata
                                    # These are actual token counts extracted from SDK response,
                                    # not just estimates. The extract_token_counts() function
                                    # pulls from response.usage or metadata fields.
                                    tracker.add_tokens(input_tokens=input_tokens, output_tokens=output_tokens)

                                    if is_error:
                                        error_msg = str(block.content) if hasattr(block, 'content') else "Unknown error"
                                        tracker.set_error(error_msg)
                                    else:
                                        # AI-53: Extract artifacts from successful completion using artifact detector
                                        result_content = str(block.content) if hasattr(block, 'content') else ""

                                        # Get artifact detector instance
                                        artifact_detector = get_artifact_detector()

                                        # Detect artifacts from the delegation result
                                        detected_artifacts = artifact_detector.detect_artifacts(
                                            agent_name=agent_name,
                                            tool_results=result_content,
                                            additional_context=task_description
                                        )

                                        # Add all detected artifacts to the tracker
                                        for artifact in detected_artifacts:
                                            tracker.add_artifact(artifact)

                                # Remove from active delegations
                                del active_delegations[block.tool_use_id]

                                print(f"   [Delegation completed: {agent_name} - {status}]", flush=True)
                            except Exception as e:
                                print(f"   [Warning: Failed to record delegation: {e}]", flush=True)

        print("\n" + "-" * 70 + "\n")
        return SessionResult(status=SESSION_CONTINUE, response=response_text)

    except ConnectionError as e:
        print(f"\nNetwork error in orchestrated session: {e}")
        print("Check your internet connection and Arcade MCP gateway availability.")
        traceback.print_exc()
        return SessionResult(status=SESSION_ERROR, response=str(e))

    except TimeoutError as e:
        print(f"\nTimeout in orchestrated session: {e}")
        print("The orchestration timed out. This may be due to slow MCP responses.")
        traceback.print_exc()
        return SessionResult(status=SESSION_ERROR, response=str(e))

    except Exception as e:
        error_type: str = type(e).__name__
        error_msg: str = str(e)

        print(f"\nError in orchestrated session ({error_type}): {error_msg}")
        print("\nFull traceback:")
        traceback.print_exc()

        # Provide actionable guidance based on error type
        error_lower = error_msg.lower()
        if "arcade" in error_lower or "mcp" in error_lower:
            print("\nThis appears to be an Arcade MCP Gateway error.")
            print("Check your ARCADE_API_KEY and ARCADE_GATEWAY_SLUG configuration.")
        elif "agent" in error_lower or "delegation" in error_lower:
            print("\nThis appears to be an agent delegation error.")
            print("Check the agent definitions and ensure all required tools are authorized.")
        elif "auth" in error_lower or "token" in error_lower:
            print("\nThis appears to be an authentication error.")
            print("Check your CLAUDE_CODE_OAUTH_TOKEN environment variable.")
        else:
            # Unexpected error type - make this visible
            print(f"\nUnexpected error type: {error_type}")
            print("This may indicate a bug or an unhandled edge case.")
            print("The orchestrator will retry, but please report this if it persists.")

        return SessionResult(status=SESSION_ERROR, response=error_msg)
