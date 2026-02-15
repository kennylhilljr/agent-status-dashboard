"""Simplified tests for orchestrator.py delegation tracking instrumentation.

This test module verifies the orchestrator's delegation tracking logic without
requiring the full claude-agent-sdk to be installed. It tests the core
delegation tracking functionality used by orchestrator.py.
"""

import re
import tempfile
from pathlib import Path

import pytest

from agent_metrics_collector import AgentMetricsCollector


class TestDelegationInstrumentation:
    """Test the orchestrator delegation tracking logic."""

    def test_delegation_tracking_with_simple_task(self):
        """Test that delegation tracking captures agent_name and ticket_key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            # Simulate what orchestrator.py does when it sees a Task tool
            # Lines 85-104 in orchestrator.py
            task_input = {"agent": "coding", "task": "Work on AI-51: Implement feature"}

            # Extract agent name and ticket from tool input (orchestrator.py logic)
            agent_name = task_input.get("agent", "unknown")
            task_description = task_input.get("task", "")

            # Extract ticket key from task description
            ticket_match = re.search(r'\b(AI-\d+)\b', task_description)
            ticket_key = ticket_match.group(1) if ticket_match else "unknown"

            # Track delegation with metrics collector (orchestrator.py lines 127-146)
            model_used = "claude-haiku-4-5"
            with collector.track_agent(
                agent_name=agent_name,
                ticket_key=ticket_key,
                model_used=model_used,
                session_id=session_id
            ) as tracker:
                # Simulated work
                tracker.add_tokens(input_tokens=500, output_tokens=1000)
                tracker.add_artifact(f"delegation:{agent_name}")

            collector.end_session(session_id)

            # Verify delegation was tracked correctly
            state = collector.get_state()
            assert len(state["events"]) == 1

            event = state["events"][0]
            assert event["agent_name"] == "coding"
            assert event["ticket_key"] == "AI-51"
            assert event["model_used"] == "claude-haiku-4-5"
            assert event["status"] == "success"
            assert event["input_tokens"] == 500
            assert event["output_tokens"] == 1000
            assert event["total_tokens"] == 1500

    def test_multiple_delegations_tracked(self):
        """Test that multiple delegations are all tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            # Simulate multiple Task tool delegations
            delegations = [
                ("coding", "Work on AI-51", "AI-51"),
                ("github", "Create PR for AI-51", "AI-51"),
                ("linear", "Update AI-52 status", "AI-52"),
            ]

            for agent, task_desc, expected_ticket in delegations:
                ticket_match = re.search(r'\b(AI-\d+)\b', task_desc)
                ticket_key = ticket_match.group(1) if ticket_match else "unknown"

                with collector.track_agent(
                    agent_name=agent,
                    ticket_key=ticket_key,
                    model_used="claude-haiku-4-5",
                    session_id=session_id
                ) as tracker:
                    tracker.add_tokens(input_tokens=500, output_tokens=1000)

            collector.end_session(session_id)

            # Verify all delegations tracked
            state = collector.get_state()
            assert len(state["events"]) == 3

            # Check each delegation
            assert state["events"][0]["agent_name"] == "coding"
            assert state["events"][0]["ticket_key"] == "AI-51"

            assert state["events"][1]["agent_name"] == "github"
            assert state["events"][1]["ticket_key"] == "AI-51"

            assert state["events"][2]["agent_name"] == "linear"
            assert state["events"][2]["ticket_key"] == "AI-52"

    def test_ticket_key_extraction_patterns(self):
        """Test various ticket key extraction patterns."""
        test_cases = [
            ("Work on AI-51: Implement feature", "AI-51"),
            ("AI-51 needs implementation", "AI-51"),
            ("Implement AI-123", "AI-123"),
            ("Fix bug in AI-999", "AI-999"),
            ("Multiple AI-1 and AI-2 tickets", "AI-1"),  # First match
            ("No ticket here", "unknown"),  # No match
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            for task_desc, expected_ticket in test_cases:
                ticket_match = re.search(r'\b(AI-\d+)\b', task_desc)
                ticket_key = ticket_match.group(1) if ticket_match else "unknown"

                with collector.track_agent(
                    agent_name="coding",
                    ticket_key=ticket_key,
                    model_used="claude-haiku-4-5",
                    session_id=session_id
                ) as tracker:
                    tracker.add_tokens(input_tokens=100, output_tokens=200)

            collector.end_session(session_id)

            # Verify all ticket keys extracted correctly
            state = collector.get_state()
            extracted_tickets = [event["ticket_key"] for event in state["events"]]
            expected_tickets = [ticket for _, ticket in test_cases]

            assert extracted_tickets == expected_tickets

    def test_failed_delegation_recorded_as_error(self):
        """Test that failed delegations are recorded with error status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            # Simulate failed delegation
            with collector.track_agent(
                agent_name="coding",
                ticket_key="AI-51",
                model_used="claude-haiku-4-5",
                session_id=session_id
            ) as tracker:
                tracker.add_tokens(input_tokens=500, output_tokens=1000)
                tracker.set_error("Error: Failed to compile")

            collector.end_session(session_id)

            # Verify error status recorded
            state = collector.get_state()
            event = state["events"][0]

            assert event["status"] == "error"
            assert event["error_message"] == "Error: Failed to compile"

    def test_delegation_cost_calculation(self):
        """Test that costs are calculated correctly for delegations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            # Track delegation with specific token counts
            with collector.track_agent(
                agent_name="coding",
                ticket_key="AI-51",
                model_used="claude-haiku-4-5",
                session_id=session_id
            ) as tracker:
                # Haiku pricing: $0.0008/1K input, $0.004/1K output
                # 1000 input tokens = $0.0008
                # 2000 output tokens = $0.008
                # Total = $0.0088
                tracker.add_tokens(input_tokens=1000, output_tokens=2000)

            collector.end_session(session_id)

            state = collector.get_state()
            event = state["events"][0]

            # Verify cost calculation
            expected_cost = (1000 / 1000.0) * 0.0008 + (2000 / 1000.0) * 0.004
            assert abs(event["estimated_cost_usd"] - expected_cost) < 0.0001

    def test_session_aggregates_delegation_metrics(self):
        """Test that session totals include all delegation metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            # Multiple delegations
            for i in range(3):
                with collector.track_agent(
                    agent_name="coding",
                    ticket_key=f"AI-{50+i}",
                    model_used="claude-haiku-4-5",
                    session_id=session_id
                ) as tracker:
                    tracker.add_tokens(input_tokens=500, output_tokens=1000)

            collector.end_session(session_id)

            # Verify session aggregates
            state = collector.get_state()
            session = state["sessions"][0]

            # 3 delegations × 1500 tokens each = 4500 total
            assert session["total_tokens"] == 4500
            assert session["agents_invoked"] == ["coding"]  # Unique agents
            assert len(session["tickets_worked"]) == 3  # 3 different tickets

    def test_agent_profile_updated_from_delegation(self):
        """Test that agent profiles are updated from delegations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            # Track successful delegation
            with collector.track_agent(
                agent_name="coding",
                ticket_key="AI-51",
                model_used="claude-haiku-4-5",
                session_id=session_id
            ) as tracker:
                tracker.add_tokens(input_tokens=500, output_tokens=1000)
                tracker.add_artifact("file:test.py")

            collector.end_session(session_id)

            # Verify agent profile created and updated
            state = collector.get_state()
            assert "coding" in state["agents"]

            coding_profile = state["agents"]["coding"]
            assert coding_profile["total_invocations"] == 1
            assert coding_profile["successful_invocations"] == 1
            assert coding_profile["failed_invocations"] == 0
            assert coding_profile["total_tokens"] == 1500
            assert coding_profile["success_rate"] == 1.0

    def test_malformed_task_input_defaults_to_unknown(self):
        """Test that malformed Task input uses 'unknown' defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            # Simulate malformed Task tool input (orchestrator.py handles gracefully)
            task_input = {}  # Missing agent and task fields
            agent_name = task_input.get("agent", "unknown")
            task_description = task_input.get("task", "")

            ticket_match = re.search(r'\b(AI-\d+)\b', task_description)
            ticket_key = ticket_match.group(1) if ticket_match else "unknown"

            # Should still track with defaults
            with collector.track_agent(
                agent_name=agent_name,
                ticket_key=ticket_key,
                model_used="claude-haiku-4-5",
                session_id=session_id
            ) as tracker:
                tracker.add_tokens(input_tokens=500, output_tokens=1000)

            collector.end_session(session_id)

            # Verify delegation tracked with "unknown" values
            state = collector.get_state()
            event = state["events"][0]
            assert event["agent_name"] == "unknown"
            assert event["ticket_key"] == "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
