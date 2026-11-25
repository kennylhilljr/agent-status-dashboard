"""Regression tests for orchestrator delegation events (issue #33).

- Ticket keys are extracted for any project prefix, not just AI-*.
- started_at / duration_seconds describe the delegation, from the Task
  ToolUseBlock to its ToolResultBlock, not the result handling.
- Artifact rule keywords match the status field exactly, never a substring.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from agent_metrics_collector import AgentMetricsCollector
from agents.orchestrator import run_orchestrated_session
from ticket_keys import extract_ticket_key


@pytest.fixture
def collector(tmp_path: Path) -> AgentMetricsCollector:
    return AgentMetricsCollector(project_name="test-project", metrics_dir=tmp_path)


async def _run_one_delegation(
    collector: AgentMetricsCollector,
    project_dir: Path,
    task_text: str,
    pause_seconds: float = 0.0,
) -> list[dict]:
    """Drive run_orchestrated_session through one Task delegation."""
    session_id = collector.start_session(session_type="continuation")
    client = MagicMock()
    client.query = AsyncMock()

    async def receive():
        yield AssistantMessage(
            model="claude-sonnet-4-5",
            content=[
                ToolUseBlock(
                    id="task_1",
                    name="Task",
                    input={"agent": "coding", "task": task_text},
                )
            ],
        )
        if pause_seconds:
            await asyncio.sleep(pause_seconds)
        yield UserMessage(
            content=[ToolResultBlock(tool_use_id="task_1", content="Done", is_error=False)]
        )

    client.receive_response = receive
    await run_orchestrated_session(
        client=client,
        project_dir=project_dir,
        session_id=session_id,
        metrics_collector=collector,
    )
    collector.end_session(session_id, status="complete")
    return collector.get_state()["events"]


# --- ticket keys -----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Work on AI-51: Implement feature", "AI-51"),
        ("Fix HS-12 login", "HS-12"),
        ("CTX-7", "CTX-7"),
        ("OPS2-40 deploy", "OPS2-40"),
        ("Decode as UTF-8 then fix OPS-3", "OPS-3"),
        ("Use SHA-256", "unknown"),
        ("Compare with GPT-4 output", "unknown"),
        ("No ticket here", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
        ("claude-sonnet-4-5", "unknown"),
        ("A-1", "unknown"),
    ],
)
def test_extract_ticket_key(text, expected):
    assert extract_ticket_key(text) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("task_text", "expected"),
    [("Fix HS-12 login", "HS-12"), ("Work on AI-51", "AI-51"), ("Tidy up", "unknown")],
)
async def test_orchestrator_records_ticket_key(collector, tmp_path, task_text, expected):
    events = await _run_one_delegation(collector, tmp_path, task_text)
    assert len(events) == 1
    assert events[0]["ticket_key"] == expected


# --- delegation start time -------------------------------------------------


def test_track_agent_explicit_start_time(collector):
    start = datetime(2026, 2, 14, 2, 30, tzinfo=UTC).timestamp()
    with collector.track_agent("coding", "AI-1", "claude-sonnet-4-5", start_time=start):
        pass
    state = collector.get_state()
    event = state["events"][0]
    assert event["started_at"] == "2026-02-14T02:30:00Z"
    assert event["duration_seconds"] > 3600


def test_track_agent_default_start_time(collector):
    with collector.track_agent("coding", "AI-1", "claude-sonnet-4-5"):
        pass
    event = collector.get_state()["events"][0]
    assert 0 <= event["duration_seconds"] < 5
    assert event["started_at"].endswith("Z")


@pytest.mark.asyncio
async def test_orchestrator_duration_starts_at_tool_use(collector, tmp_path):
    events = await _run_one_delegation(collector, tmp_path, "Work on AI-51", pause_seconds=0.3)
    assert len(events) == 1
    event = events[0]
    assert event["duration_seconds"] >= 0.25
    started = datetime.fromisoformat(event["started_at"].rstrip("Z"))
    ended = datetime.fromisoformat(event["ended_at"].rstrip("Z"))
    assert ended - started >= timedelta(seconds=0.25)


# --- artifact status field -------------------------------------------------


def _counters_after(collector, artifact: str) -> dict:
    with collector.track_agent("coding", "AI-1", "claude-sonnet-4-5") as tracker:
        tracker.add_artifact(artifact)
    return collector.get_state()["agents"]["coding"]


@pytest.mark.parametrize(
    ("artifact", "expected"),
    [
        ("pr:#7:merged", {"prs_merged": 1, "prs_created": 0}),
        ("pr:created-by-bot:merged", {"prs_merged": 1, "prs_created": 0}),
        ("pr:merged-fix:created", {"prs_created": 1, "prs_merged": 0}),
        ("pr:#7:created-extra", {"prs_created": 0, "prs_merged": 0}),
        ("issue:AI-5:completed", {"issues_completed": 1, "issues_created": 0}),
        ("issue:AI-5:not-completed", {"issues_completed": 0}),
        ("issue:created-AI-5:updated", {"issues_created": 0, "issues_completed": 0}),
        ("issue:completed", {"issues_completed": 0}),
        ("pr:created:#50", {"prs_created": 1, "prs_merged": 0}),
        ("issue:completed:AI-7", {"issues_completed": 1, "issues_created": 0}),
        ("issue:created:merged-AI-7", {"issues_created": 1}),
        ("commit:abc123", {"commits_made": 1}),
        ("file:tests/created/x.py:modified", {"files_modified": 1, "files_created": 0}),
    ],
)
def test_artifact_rules_match_status_field(collector, artifact, expected):
    profile = _counters_after(collector, artifact)
    for counter, value in expected.items():
        assert profile[counter] == value, counter
