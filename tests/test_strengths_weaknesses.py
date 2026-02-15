#!/usr/bin/env python3
"""Comprehensive tests for strengths and weaknesses detection system.

Tests all aspects of the strengths/weaknesses detection including:
- Rolling window statistics calculation
- Percentile calculations for comparative metrics
- Strength detection logic
- Weakness detection logic
- Edge cases: empty data, single agent, all equal, outliers
- Full integration with dashboard state updates

This test suite provides robust coverage of the detection system to ensure
reliable and accurate performance profiling across all agents.
"""

import pytest
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from metrics import AgentEvent, AgentProfile, DashboardState
from strengths_weaknesses import (
    calculate_rolling_window_stats,
    calculate_agent_percentiles,
    detect_strengths,
    detect_weaknesses,
    update_agent_strengths_weaknesses,
    get_strength_description,
    get_weakness_description,
)


class TestRollingWindowStats:
    """Test suite for rolling window statistics calculation."""

    @pytest.fixture
    def sample_events(self) -> List[AgentEvent]:
        """Create sample agent events for testing."""
        events = []
        for i in range(30):
            events.append({
                "event_id": f"evt-{i}",
                "agent_name": "coding",
                "session_id": "sess-1",
                "ticket_key": "AI-100",
                "started_at": f"2026-02-14T{10 + (i // 60):02d}:{(i % 60):02d}:00Z",
                "ended_at": f"2026-02-14T{10 + (i // 60):02d}:{(i % 60):05d}Z",
                "duration_seconds": 100.0 + i * 2,
                "status": "success" if i % 10 != 0 else "error",
                "input_tokens": 1000,
                "output_tokens": 2000,
                "total_tokens": 3000,
                "estimated_cost_usd": 0.03,
                "artifacts": ["file:test.py"],
                "error_message": "" if i % 10 != 0 else "Test error",
                "model_used": "claude-sonnet-4-5",
            })
        return events

    def test_rolling_window_stats_basic(self, sample_events):
        """Test basic rolling window statistics calculation."""
        stats = calculate_rolling_window_stats(sample_events, "coding", window_size=10)

        assert stats["event_count"] == 10
        assert stats["success_rate"] >= 0.0
        assert stats["success_rate"] <= 1.0
        assert stats["avg_duration"] > 0.0
        assert stats["avg_cost"] > 0.0
        assert stats["avg_tokens"] > 0.0
        assert stats["duration_variance"] >= 0.0
        assert stats["artifact_count"] >= 0

    def test_rolling_window_full_window(self, sample_events):
        """Test when there are more events than window size."""
        stats = calculate_rolling_window_stats(sample_events, "coding", window_size=20)

        assert stats["event_count"] == 20
        # Should only look at last 20 events
        last_20_durations = [e["duration_seconds"] for e in sample_events[-20:]]
        assert abs(stats["avg_duration"] - sum(last_20_durations) / 20) < 0.01

    def test_rolling_window_partial_window(self, sample_events):
        """Test when there are fewer events than window size."""
        stats = calculate_rolling_window_stats(sample_events, "coding", window_size=100)

        # Should only have 30 events
        assert stats["event_count"] == 30

    def test_rolling_window_empty_data(self):
        """Test rolling window with empty event list."""
        stats = calculate_rolling_window_stats([], "coding", window_size=10)

        assert stats["event_count"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["avg_duration"] == 0.0
        assert stats["avg_cost"] == 0.0
        assert stats["avg_tokens"] == 0.0
        assert stats["duration_variance"] == 0.0
        assert stats["artifact_count"] == 0

    def test_rolling_window_nonexistent_agent(self, sample_events):
        """Test rolling window with agent that has no events."""
        stats = calculate_rolling_window_stats(sample_events, "nonexistent", window_size=10)

        assert stats["event_count"] == 0
        assert stats["success_rate"] == 0.0

    def test_rolling_window_success_rate_calculation(self):
        """Test success rate calculation in rolling window."""
        events: List[AgentEvent] = []
        for i in range(10):
            events.append({
                "event_id": f"evt-{i}",
                "agent_name": "test_agent",
                "session_id": "sess-1",
                "ticket_key": "AI-100",
                "started_at": "2026-02-14T10:00:00Z",
                "ended_at": "2026-02-14T10:01:00Z",
                "duration_seconds": 60.0,
                "status": "success" if i < 7 else "error",
                "input_tokens": 1000,
                "output_tokens": 2000,
                "total_tokens": 3000,
                "estimated_cost_usd": 0.03,
                "artifacts": [],
                "error_message": "" if i < 7 else "Error",
                "model_used": "claude-sonnet-4-5",
            })

        stats = calculate_rolling_window_stats(events, "test_agent", window_size=10)

        # 7 successes out of 10
        assert abs(stats["success_rate"] - 0.7) < 0.01

    def test_rolling_window_duration_variance(self):
        """Test duration variance calculation."""
        events: List[AgentEvent] = []
        # Create events with varying durations
        durations = [10.0, 20.0, 30.0, 40.0, 50.0]
        for i, duration in enumerate(durations):
            events.append({
                "event_id": f"evt-{i}",
                "agent_name": "test_agent",
                "session_id": "sess-1",
                "ticket_key": "AI-100",
                "started_at": "2026-02-14T10:00:00Z",
                "ended_at": "2026-02-14T10:01:00Z",
                "duration_seconds": duration,
                "status": "success",
                "input_tokens": 1000,
                "output_tokens": 2000,
                "total_tokens": 3000,
                "estimated_cost_usd": 0.03,
                "artifacts": [],
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
            })

        stats = calculate_rolling_window_stats(events, "test_agent", window_size=10)

        # Variance should be calculated
        assert stats["duration_variance"] > 0

    def test_rolling_window_artifact_counting(self):
        """Test artifact counting in rolling window."""
        events: List[AgentEvent] = []
        for i in range(5):
            artifacts = [f"file:test-{j}.py" for j in range(i + 1)]
            events.append({
                "event_id": f"evt-{i}",
                "agent_name": "test_agent",
                "session_id": "sess-1",
                "ticket_key": "AI-100",
                "started_at": "2026-02-14T10:00:00Z",
                "ended_at": "2026-02-14T10:01:00Z",
                "duration_seconds": 60.0,
                "status": "success",
                "input_tokens": 1000,
                "output_tokens": 2000,
                "total_tokens": 3000,
                "estimated_cost_usd": 0.03,
                "artifacts": artifacts,
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
            })

        stats = calculate_rolling_window_stats(events, "test_agent", window_size=10)

        # Total artifacts: 1 + 2 + 3 + 4 + 5 = 15
        assert stats["artifact_count"] == 15

    def test_rolling_window_single_event(self):
        """Test rolling window with only one event."""
        event: AgentEvent = {
            "event_id": "evt-1",
            "agent_name": "test_agent",
            "session_id": "sess-1",
            "ticket_key": "AI-100",
            "started_at": "2026-02-14T10:00:00Z",
            "ended_at": "2026-02-14T10:01:00Z",
            "duration_seconds": 60.0,
            "status": "success",
            "input_tokens": 1000,
            "output_tokens": 2000,
            "total_tokens": 3000,
            "estimated_cost_usd": 0.03,
            "artifacts": [],
            "error_message": "",
            "model_used": "claude-sonnet-4-5",
        }

        stats = calculate_rolling_window_stats([event], "test_agent", window_size=10)

        assert stats["event_count"] == 1
        assert stats["success_rate"] == 1.0
        assert stats["avg_duration"] == 60.0
        assert stats["duration_variance"] == 0.0  # Single event has no variance


class TestPercentileCalculations:
    """Test suite for percentile calculations across agents."""

    @pytest.fixture
    def multi_agent_state(self) -> DashboardState:
        """Create a dashboard state with multiple agents."""
        # Create events for three agents
        events: List[AgentEvent] = []

        # Fast agent (coding)
        for i in range(10):
            events.append({
                "event_id": f"evt-coding-{i}",
                "agent_name": "coding",
                "session_id": "sess-1",
                "ticket_key": "AI-100",
                "started_at": "2026-02-14T10:00:00Z",
                "ended_at": "2026-02-14T10:01:00Z",
                "duration_seconds": 30.0,  # Fast
                "status": "success",
                "input_tokens": 1000,
                "output_tokens": 2000,
                "total_tokens": 3000,
                "estimated_cost_usd": 0.01,  # Cheap
                "artifacts": ["file:test.py"],
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
            })

        # Medium agent (github)
        for i in range(10):
            events.append({
                "event_id": f"evt-github-{i}",
                "agent_name": "github",
                "session_id": "sess-1",
                "ticket_key": "AI-100",
                "started_at": "2026-02-14T10:00:00Z",
                "ended_at": "2026-02-14T10:01:00Z",
                "duration_seconds": 60.0,  # Medium
                "status": "success",
                "input_tokens": 1000,
                "output_tokens": 2000,
                "total_tokens": 3000,
                "estimated_cost_usd": 0.03,  # Medium
                "artifacts": ["pr:#42"],
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
            })

        # Slow agent (linear)
        for i in range(10):
            events.append({
                "event_id": f"evt-linear-{i}",
                "agent_name": "linear",
                "session_id": "sess-1",
                "ticket_key": "AI-100",
                "started_at": "2026-02-14T10:00:00Z",
                "ended_at": "2026-02-14T10:01:00Z",
                "duration_seconds": 120.0,  # Slow
                "status": "success" if i < 7 else "error",  # Lower success
                "input_tokens": 1000,
                "output_tokens": 2000,
                "total_tokens": 3000,
                "estimated_cost_usd": 0.05,  # Expensive
                "artifacts": ["issue:AI-100"],
                "error_message": "" if i < 7 else "Error",
                "model_used": "claude-sonnet-4-5",
            })

        agents: Dict[str, AgentProfile] = {
            "coding": {
                "agent_name": "coding",
                "total_invocations": 10,
                "successful_invocations": 10,
                "failed_invocations": 0,
                "total_tokens": 30000,
                "total_cost_usd": 0.1,
                "total_duration_seconds": 300.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 10,
                "files_modified": 20,
                "lines_added": 500,
                "lines_removed": 100,
                "tests_written": 5,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "strengths": [],
                "weaknesses": [],
                "xp_earned": 1000,
                "level": 5,
                "last_seen": "2026-02-14T10:00:00Z",
            },
            "github": {
                "agent_name": "github",
                "total_invocations": 10,
                "successful_invocations": 10,
                "failed_invocations": 0,
                "total_tokens": 30000,
                "total_cost_usd": 0.3,
                "total_duration_seconds": 600.0,
                "commits_made": 20,
                "prs_created": 5,
                "prs_merged": 4,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "strengths": [],
                "weaknesses": [],
                "xp_earned": 800,
                "level": 4,
                "last_seen": "2026-02-14T10:00:00Z",
            },
            "linear": {
                "agent_name": "linear",
                "total_invocations": 10,
                "successful_invocations": 7,
                "failed_invocations": 3,
                "total_tokens": 30000,
                "total_cost_usd": 0.5,
                "total_duration_seconds": 1200.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 20,
                "issues_completed": 15,
                "messages_sent": 0,
                "reviews_completed": 0,
                "strengths": [],
                "weaknesses": [],
                "xp_earned": 600,
                "level": 3,
                "last_seen": "2026-02-14T10:00:00Z",
            },
        }

        return {
            "agents": agents,
            "events": events,
        }

    def test_percentiles_basic(self, multi_agent_state):
        """Test basic percentile calculation."""
        percentiles = calculate_agent_percentiles(multi_agent_state, window_size=20)

        assert "coding" in percentiles
        assert "github" in percentiles
        assert "linear" in percentiles

        # Each agent should have all percentile metrics
        for agent_name, pct in percentiles.items():
            assert "duration_percentile" in pct
            assert "cost_percentile" in pct
            assert "success_percentile" in pct
            assert "consistency_percentile" in pct

    def test_percentiles_values_range(self, multi_agent_state):
        """Test that percentile values are in valid range."""
        percentiles = calculate_agent_percentiles(multi_agent_state, window_size=20)

        for agent_name, pct in percentiles.items():
            assert 0.0 <= pct["duration_percentile"] <= 1.0
            assert 0.0 <= pct["cost_percentile"] <= 1.0
            assert 0.0 <= pct["success_percentile"] <= 1.0
            assert 0.0 <= pct["consistency_percentile"] <= 1.0

    def test_percentiles_duration_ordering(self, multi_agent_state):
        """Test that duration percentiles are ordered correctly."""
        percentiles = calculate_agent_percentiles(multi_agent_state, window_size=20)

        # coding is fastest (30s), should have highest duration percentile
        # linear is slowest (120s), should have lowest duration percentile
        assert percentiles["coding"]["duration_percentile"] > percentiles["github"]["duration_percentile"]
        assert percentiles["github"]["duration_percentile"] > percentiles["linear"]["duration_percentile"]

    def test_percentiles_cost_ordering(self, multi_agent_state):
        """Test that cost percentiles are ordered correctly."""
        percentiles = calculate_agent_percentiles(multi_agent_state, window_size=20)

        # coding is cheapest (0.01), linear is most expensive (0.05)
        assert percentiles["coding"]["cost_percentile"] > percentiles["linear"]["cost_percentile"]

    def test_percentiles_success_ordering(self, multi_agent_state):
        """Test that success percentiles reflect success rates."""
        percentiles = calculate_agent_percentiles(multi_agent_state, window_size=20)

        # coding and github have 100% success, linear has ~70%
        assert percentiles["coding"]["success_percentile"] >= percentiles["linear"]["success_percentile"]
        assert percentiles["github"]["success_percentile"] >= percentiles["linear"]["success_percentile"]

    def test_percentiles_empty_state(self):
        """Test percentiles with no agents."""
        state: DashboardState = {"agents": {}, "events": []}
        percentiles = calculate_agent_percentiles(state, window_size=20)

        assert percentiles == {}

    def test_percentiles_no_events(self):
        """Test percentiles when agents have no events."""
        agents: Dict[str, AgentProfile] = {
            "coding": {
                "agent_name": "coding",
                "total_invocations": 0,
                "successful_invocations": 0,
                "failed_invocations": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "total_duration_seconds": 0.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "strengths": [],
                "weaknesses": [],
                "xp_earned": 0,
                "level": 0,
                "last_seen": "2026-02-14T10:00:00Z",
            }
        }

        state: DashboardState = {"agents": agents, "events": []}
        percentiles = calculate_agent_percentiles(state, window_size=20)

        assert percentiles == {}

    def test_percentiles_single_agent(self):
        """Test percentiles with only one agent."""
        event: AgentEvent = {
            "event_id": "evt-1",
            "agent_name": "coding",
            "session_id": "sess-1",
            "ticket_key": "AI-100",
            "started_at": "2026-02-14T10:00:00Z",
            "ended_at": "2026-02-14T10:01:00Z",
            "duration_seconds": 60.0,
            "status": "success",
            "input_tokens": 1000,
            "output_tokens": 2000,
            "total_tokens": 3000,
            "estimated_cost_usd": 0.03,
            "artifacts": [],
            "error_message": "",
            "model_used": "claude-sonnet-4-5",
        }

        agents: Dict[str, AgentProfile] = {
            "coding": {
                "agent_name": "coding",
                "total_invocations": 1,
                "successful_invocations": 1,
                "failed_invocations": 0,
                "total_tokens": 3000,
                "total_cost_usd": 0.03,
                "total_duration_seconds": 60.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "strengths": [],
                "weaknesses": [],
                "xp_earned": 100,
                "level": 1,
                "last_seen": "2026-02-14T10:00:00Z",
            }
        }

        state: DashboardState = {"agents": agents, "events": [event]}
        percentiles = calculate_agent_percentiles(state, window_size=10)

        # Single agent should get 0.5 percentile
        assert percentiles["coding"]["duration_percentile"] == 0.5
        assert percentiles["coding"]["cost_percentile"] == 0.5
        assert percentiles["coding"]["success_percentile"] == 0.5
        assert percentiles["coding"]["consistency_percentile"] == 0.5

    def test_percentiles_all_equal(self):
        """Test percentiles when all agents have equal metrics."""
        events: List[AgentEvent] = []

        # Create identical events for all agents
        for agent in ["coding", "github", "linear"]:
            for i in range(10):
                events.append({
                    "event_id": f"evt-{agent}-{i}",
                    "agent_name": agent,
                    "session_id": "sess-1",
                    "ticket_key": "AI-100",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:01:00Z",
                    "duration_seconds": 60.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": [],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                })

        agents: Dict[str, AgentProfile] = {}
        for agent in ["coding", "github", "linear"]:
            agents[agent] = {
                "agent_name": agent,
                "total_invocations": 10,
                "successful_invocations": 10,
                "failed_invocations": 0,
                "total_tokens": 30000,
                "total_cost_usd": 0.3,
                "total_duration_seconds": 600.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "strengths": [],
                "weaknesses": [],
                "xp_earned": 100,
                "level": 1,
                "last_seen": "2026-02-14T10:00:00Z",
            }

        state: DashboardState = {"agents": agents, "events": events}
        percentiles = calculate_agent_percentiles(state, window_size=20)

        # When there are multiple equal agents, they get ranked with lowest first
        # For three equal values, indices are 0, 1, 2
        # percentile = rank / (count - 1) = 0, 1, 2 / 2 = 0.0, 0.5, 1.0
        # All should be in valid range
        for agent_name, pct in percentiles.items():
            assert 0.0 <= pct["duration_percentile"] <= 1.0
            assert 0.0 <= pct["cost_percentile"] <= 1.0
            assert 0.0 <= pct["consistency_percentile"] <= 1.0


class TestStrengthDetection:
    """Test suite for strength detection logic."""

    def test_detect_fast_execution_strength(self):
        """Test detection of fast_execution strength."""
        stats = {
            "event_count": 10,
            "success_rate": 1.0,
            "avg_duration": 30.0,
            "avg_cost": 0.01,
            "avg_tokens": 3000,
            "duration_variance": 100.0,
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.8,  # Top 20% fastest
                "cost_percentile": 0.5,
                "success_percentile": 1.0,
                "consistency_percentile": 0.5,
            }
        }

        strengths = detect_strengths("test_agent", stats, percentiles)
        assert "fast_execution" in strengths

    def test_detect_high_success_rate_strength(self):
        """Test detection of high_success_rate strength."""
        stats = {
            "event_count": 10,
            "success_rate": 0.95,  # 95% success
            "avg_duration": 60.0,
            "avg_cost": 0.03,
            "avg_tokens": 3000,
            "duration_variance": 100.0,
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.5,
                "cost_percentile": 0.5,
                "success_percentile": 1.0,
                "consistency_percentile": 0.5,
            }
        }

        strengths = detect_strengths("test_agent", stats, percentiles)
        assert "high_success_rate" in strengths

    def test_detect_low_cost_strength(self):
        """Test detection of low_cost strength."""
        stats = {
            "event_count": 10,
            "success_rate": 1.0,
            "avg_duration": 60.0,
            "avg_cost": 0.01,
            "avg_tokens": 3000,
            "duration_variance": 100.0,
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.5,
                "cost_percentile": 0.8,  # Top 20% cheapest
                "success_percentile": 1.0,
                "consistency_percentile": 0.5,
            }
        }

        strengths = detect_strengths("test_agent", stats, percentiles)
        assert "low_cost" in strengths

    def test_detect_consistent_strength(self):
        """Test detection of consistent strength."""
        stats = {
            "event_count": 10,
            "success_rate": 1.0,
            "avg_duration": 60.0,
            "avg_cost": 0.03,
            "avg_tokens": 3000,
            "duration_variance": 10.0,  # Low variance
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.5,
                "cost_percentile": 0.5,
                "success_percentile": 1.0,
                "consistency_percentile": 0.8,  # Top 20% most consistent
            }
        }

        strengths = detect_strengths("test_agent", stats, percentiles)
        assert "consistent" in strengths

    def test_detect_prolific_strength(self):
        """Test detection of prolific strength."""
        stats = {
            "event_count": 5,
            "success_rate": 1.0,
            "avg_duration": 60.0,
            "avg_cost": 0.03,
            "avg_tokens": 3000,
            "duration_variance": 100.0,
            "artifact_count": 25,  # 5 artifacts per event (>= 2.0 threshold)
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.5,
                "cost_percentile": 0.5,
                "success_percentile": 1.0,
                "consistency_percentile": 0.5,
            }
        }

        strengths = detect_strengths("test_agent", stats, percentiles)
        assert "prolific" in strengths

    def test_detect_multiple_strengths(self):
        """Test detection of multiple strengths."""
        stats = {
            "event_count": 10,
            "success_rate": 0.98,
            "avg_duration": 30.0,
            "avg_cost": 0.01,
            "avg_tokens": 3000,
            "duration_variance": 10.0,
            "artifact_count": 25,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.9,
                "cost_percentile": 0.9,
                "success_percentile": 1.0,
                "consistency_percentile": 0.9,
            }
        }

        strengths = detect_strengths("test_agent", stats, percentiles)

        # Should have multiple strengths
        assert len(strengths) >= 2
        assert "fast_execution" in strengths
        assert "low_cost" in strengths

    def test_detect_insufficient_events_minimum(self):
        """Test that strengths aren't detected with insufficient events."""
        stats = {
            "event_count": 3,  # Below minimum of 5
            "success_rate": 0.99,
            "avg_duration": 30.0,
            "avg_cost": 0.01,
            "avg_tokens": 3000,
            "duration_variance": 10.0,
            "artifact_count": 25,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.9,
                "cost_percentile": 0.9,
                "success_percentile": 1.0,
                "consistency_percentile": 0.9,
            }
        }

        strengths = detect_strengths("test_agent", stats, percentiles, min_events=5)
        assert len(strengths) == 0

    def test_detect_no_strengths(self):
        """Test agent with no detected strengths."""
        stats = {
            "event_count": 10,
            "success_rate": 0.8,
            "avg_duration": 60.0,
            "avg_cost": 0.03,
            "avg_tokens": 3000,
            "duration_variance": 100.0,
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.5,
                "cost_percentile": 0.5,
                "success_percentile": 0.5,
                "consistency_percentile": 0.5,
            }
        }

        strengths = detect_strengths("test_agent", stats, percentiles)
        assert len(strengths) == 0


class TestWeaknessDetection:
    """Test suite for weakness detection logic."""

    def test_detect_high_error_rate_weakness(self):
        """Test detection of high_error_rate weakness."""
        stats = {
            "event_count": 10,
            "success_rate": 0.6,  # < 70%
            "avg_duration": 60.0,
            "avg_cost": 0.03,
            "avg_tokens": 3000,
            "duration_variance": 100.0,
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.5,
                "cost_percentile": 0.5,
                "success_percentile": 0.2,
                "consistency_percentile": 0.5,
            }
        }

        weaknesses = detect_weaknesses("test_agent", stats, percentiles)
        assert "high_error_rate" in weaknesses

    def test_detect_slow_weakness(self):
        """Test detection of slow weakness."""
        stats = {
            "event_count": 10,
            "success_rate": 0.9,
            "avg_duration": 120.0,
            "avg_cost": 0.03,
            "avg_tokens": 3000,
            "duration_variance": 100.0,
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.2,  # Bottom 20% slowest
                "cost_percentile": 0.5,
                "success_percentile": 0.8,
                "consistency_percentile": 0.5,
            }
        }

        weaknesses = detect_weaknesses("test_agent", stats, percentiles)
        assert "slow" in weaknesses

    def test_detect_expensive_weakness(self):
        """Test detection of expensive weakness."""
        stats = {
            "event_count": 10,
            "success_rate": 0.9,
            "avg_duration": 60.0,
            "avg_cost": 0.1,
            "avg_tokens": 3000,
            "duration_variance": 100.0,
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.5,
                "cost_percentile": 0.1,  # Bottom 20% most expensive
                "success_percentile": 0.8,
                "consistency_percentile": 0.5,
            }
        }

        weaknesses = detect_weaknesses("test_agent", stats, percentiles)
        assert "expensive" in weaknesses

    def test_detect_inconsistent_weakness(self):
        """Test detection of inconsistent weakness."""
        stats = {
            "event_count": 10,
            "success_rate": 0.9,
            "avg_duration": 60.0,
            "avg_cost": 0.03,
            "avg_tokens": 3000,
            "duration_variance": 500.0,  # High variance
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.5,
                "cost_percentile": 0.5,
                "success_percentile": 0.8,
                "consistency_percentile": 0.1,  # Bottom 20% most inconsistent
            }
        }

        weaknesses = detect_weaknesses("test_agent", stats, percentiles)
        assert "inconsistent" in weaknesses

    def test_detect_multiple_weaknesses(self):
        """Test detection of multiple weaknesses."""
        stats = {
            "event_count": 10,
            "success_rate": 0.6,
            "avg_duration": 120.0,
            "avg_cost": 0.1,
            "avg_tokens": 3000,
            "duration_variance": 500.0,
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.1,
                "cost_percentile": 0.1,
                "success_percentile": 0.2,
                "consistency_percentile": 0.1,
            }
        }

        weaknesses = detect_weaknesses("test_agent", stats, percentiles)

        # Should have multiple weaknesses
        assert len(weaknesses) >= 2

    def test_detect_insufficient_events_minimum_weakness(self):
        """Test that weaknesses aren't detected with insufficient events."""
        stats = {
            "event_count": 3,  # Below minimum of 5
            "success_rate": 0.5,
            "avg_duration": 120.0,
            "avg_cost": 0.1,
            "avg_tokens": 3000,
            "duration_variance": 500.0,
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.1,
                "cost_percentile": 0.1,
                "success_percentile": 0.2,
                "consistency_percentile": 0.1,
            }
        }

        weaknesses = detect_weaknesses("test_agent", stats, percentiles, min_events=5)
        assert len(weaknesses) == 0

    def test_detect_no_weaknesses(self):
        """Test agent with no detected weaknesses."""
        stats = {
            "event_count": 10,
            "success_rate": 0.9,
            "avg_duration": 60.0,
            "avg_cost": 0.03,
            "avg_tokens": 3000,
            "duration_variance": 100.0,
            "artifact_count": 5,
        }

        percentiles = {
            "test_agent": {
                "duration_percentile": 0.5,
                "cost_percentile": 0.5,
                "success_percentile": 0.5,
                "consistency_percentile": 0.5,
            }
        }

        weaknesses = detect_weaknesses("test_agent", stats, percentiles)
        assert len(weaknesses) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_data_edge_case(self):
        """Test with completely empty data."""
        state: DashboardState = {"agents": {}, "events": []}

        result = update_agent_strengths_weaknesses(state, window_size=20, min_events=5)

        assert result["agents"] == {}

    def test_single_agent_edge_case(self):
        """Test with single agent and sufficient events."""
        event: AgentEvent = {
            "event_id": "evt-1",
            "agent_name": "coding",
            "session_id": "sess-1",
            "ticket_key": "AI-100",
            "started_at": "2026-02-14T10:00:00Z",
            "ended_at": "2026-02-14T10:01:00Z",
            "duration_seconds": 60.0,
            "status": "success",
            "input_tokens": 1000,
            "output_tokens": 2000,
            "total_tokens": 3000,
            "estimated_cost_usd": 0.03,
            "artifacts": [],
            "error_message": "",
            "model_used": "claude-sonnet-4-5",
        }

        agents: Dict[str, AgentProfile] = {
            "coding": {
                "agent_name": "coding",
                "total_invocations": 1,
                "successful_invocations": 1,
                "failed_invocations": 0,
                "total_tokens": 3000,
                "total_cost_usd": 0.03,
                "total_duration_seconds": 60.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "strengths": [],
                "weaknesses": [],
                "xp_earned": 100,
                "level": 1,
                "last_seen": "2026-02-14T10:00:00Z",
            }
        }

        state: DashboardState = {"agents": agents, "events": [event] * 10}
        result = update_agent_strengths_weaknesses(state, window_size=20, min_events=5)

        # Single agent gets 0.5 percentile for percentile-based metrics
        # But still detects high_success_rate if success_rate >= 0.95
        assert "high_success_rate" in result["agents"]["coding"]["strengths"]
        assert result["agents"]["coding"]["weaknesses"] == []

    def test_all_equal_metrics_edge_case(self):
        """Test when all agents have identical metrics (no variation)."""
        events: List[AgentEvent] = []
        agents: Dict[str, AgentProfile] = {}

        # Create identical events for 3 agents, with lower success rate so no high_success_rate strength
        for agent in ["agent1", "agent2", "agent3"]:
            for i in range(10):
                events.append({
                    "event_id": f"evt-{agent}-{i}",
                    "agent_name": agent,
                    "session_id": "sess-1",
                    "ticket_key": "AI-100",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:01:00Z",
                    "duration_seconds": 60.0,
                    "status": "success" if i < 8 else "error",  # 80% success rate
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": [],
                    "error_message": "" if i < 8 else "Error",
                    "model_used": "claude-sonnet-4-5",
                })

            agents[agent] = {
                "agent_name": agent,
                "total_invocations": 10,
                "successful_invocations": 8,
                "failed_invocations": 2,
                "total_tokens": 30000,
                "total_cost_usd": 0.3,
                "total_duration_seconds": 600.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "strengths": [],
                "weaknesses": [],
                "xp_earned": 100,
                "level": 1,
                "last_seen": "2026-02-14T10:00:00Z",
            }

        state: DashboardState = {"agents": agents, "events": events}
        result = update_agent_strengths_weaknesses(state, window_size=20, min_events=5)

        # All agents have equal metrics - percentile-based strengths/weaknesses are ranked
        # When equal, some will get higher ranking than others (0.0, 0.5, 1.0)
        # But none should get absolute strengths/weaknesses with equal performance
        for agent_name in ["agent1", "agent2", "agent3"]:
            strengths = result["agents"][agent_name]["strengths"]
            weaknesses = result["agents"][agent_name]["weaknesses"]
            # With 80% success rate, no high_error_rate weakness
            assert "high_error_rate" not in weaknesses
            # With equal performance on percentile metrics, some will rank lower/higher
            # but with equal data, the high_success_rate strength won't trigger (< 0.95)

    def test_outliers_edge_case(self):
        """Test when one agent is a significant outlier."""
        events: List[AgentEvent] = []
        agents: Dict[str, AgentProfile] = {}

        # Create normal agents
        for agent in ["normal1", "normal2"]:
            for i in range(10):
                events.append({
                    "event_id": f"evt-{agent}-{i}",
                    "agent_name": agent,
                    "session_id": "sess-1",
                    "ticket_key": "AI-100",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:01:00Z",
                    "duration_seconds": 60.0,
                    "status": "success" if i < 9 else "error",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": [],
                    "error_message": "" if i < 9 else "Error",
                    "model_used": "claude-sonnet-4-5",
                })

            agents[agent] = {
                "agent_name": agent,
                "total_invocations": 10,
                "successful_invocations": 9,
                "failed_invocations": 1,
                "total_tokens": 30000,
                "total_cost_usd": 0.3,
                "total_duration_seconds": 600.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "strengths": [],
                "weaknesses": [],
                "xp_earned": 100,
                "level": 1,
                "last_seen": "2026-02-14T10:00:00Z",
            }

        # Create outlier agent (very fast, very cheap, high success)
        for i in range(10):
            events.append({
                "event_id": f"evt-outlier-{i}",
                "agent_name": "outlier",
                "session_id": "sess-1",
                "ticket_key": "AI-100",
                "started_at": "2026-02-14T10:00:00Z",
                "ended_at": "2026-02-14T10:00:10Z",
                "duration_seconds": 10.0,  # Much faster
                "status": "success",  # Perfect success
                "input_tokens": 500,
                "output_tokens": 1000,
                "total_tokens": 1500,
                "estimated_cost_usd": 0.01,  # Much cheaper
                "artifacts": ["file:test.py", "commit:abc123"],
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
            })

        agents["outlier"] = {
            "agent_name": "outlier",
            "total_invocations": 10,
            "successful_invocations": 10,
            "failed_invocations": 0,
            "total_tokens": 15000,
            "total_cost_usd": 0.1,
            "total_duration_seconds": 100.0,
            "commits_made": 10,
            "prs_created": 0,
            "prs_merged": 0,
            "files_created": 10,
            "files_modified": 0,
            "lines_added": 100,
            "lines_removed": 0,
            "tests_written": 0,
            "issues_created": 0,
            "issues_completed": 0,
            "messages_sent": 0,
            "reviews_completed": 0,
            "strengths": [],
            "weaknesses": [],
            "xp_earned": 200,
            "level": 2,
            "last_seen": "2026-02-14T10:00:00Z",
        }

        state: DashboardState = {"agents": agents, "events": events}
        result = update_agent_strengths_weaknesses(state, window_size=20, min_events=5)

        # Outlier should have multiple strengths
        outlier_strengths = result["agents"]["outlier"]["strengths"]
        assert len(outlier_strengths) > 0
        assert "fast_execution" in outlier_strengths
        assert "low_cost" in outlier_strengths
        assert "high_success_rate" in outlier_strengths


class TestDescriptions:
    """Test strength and weakness description functions."""

    def test_strength_descriptions(self):
        """Test all strength descriptions are available."""
        strengths = [
            "fast_execution",
            "high_success_rate",
            "low_cost",
            "consistent",
            "prolific",
        ]

        for strength in strengths:
            desc = get_strength_description(strength)
            assert desc != "Unknown strength"
            assert len(desc) > 0

    def test_weakness_descriptions(self):
        """Test all weakness descriptions are available."""
        weaknesses = [
            "high_error_rate",
            "slow",
            "expensive",
            "inconsistent",
        ]

        for weakness in weaknesses:
            desc = get_weakness_description(weakness)
            assert desc != "Unknown weakness"
            assert len(desc) > 0

    def test_unknown_strength_description(self):
        """Test unknown strength returns default description."""
        desc = get_strength_description("unknown_strength")
        assert desc == "Unknown strength"

    def test_unknown_weakness_description(self):
        """Test unknown weakness returns default description."""
        desc = get_weakness_description("unknown_weakness")
        assert desc == "Unknown weakness"


class TestIntegration:
    """Integration tests for the complete strengths/weaknesses system."""

    def test_full_update_flow(self):
        """Test complete flow of updating agent strengths/weaknesses."""
        # Create events for multiple agents with different characteristics
        events: List[AgentEvent] = []

        # Fast, successful agent
        for i in range(20):
            events.append({
                "event_id": f"evt-fast-{i}",
                "agent_name": "fast_agent",
                "session_id": "sess-1",
                "ticket_key": "AI-100",
                "started_at": "2026-02-14T10:00:00Z",
                "ended_at": "2026-02-14T10:01:00Z",
                "duration_seconds": 30.0,
                "status": "success",
                "input_tokens": 1000,
                "output_tokens": 2000,
                "total_tokens": 3000,
                "estimated_cost_usd": 0.01,
                "artifacts": ["file:test.py"],
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
            })

        # Slow, failing agent
        for i in range(20):
            events.append({
                "event_id": f"evt-slow-{i}",
                "agent_name": "slow_agent",
                "session_id": "sess-1",
                "ticket_key": "AI-100",
                "started_at": "2026-02-14T10:00:00Z",
                "ended_at": "2026-02-14T10:01:00Z",
                "duration_seconds": 120.0,
                "status": "success" if i < 12 else "error",
                "input_tokens": 1000,
                "output_tokens": 2000,
                "total_tokens": 3000,
                "estimated_cost_usd": 0.05,
                "artifacts": [],
                "error_message": "" if i < 12 else "Timeout",
                "model_used": "claude-sonnet-4-5",
            })

        agents: Dict[str, AgentProfile] = {
            "fast_agent": {
                "agent_name": "fast_agent",
                "total_invocations": 20,
                "successful_invocations": 20,
                "failed_invocations": 0,
                "total_tokens": 60000,
                "total_cost_usd": 0.2,
                "total_duration_seconds": 600.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "strengths": [],
                "weaknesses": [],
                "xp_earned": 500,
                "level": 3,
                "last_seen": "2026-02-14T10:00:00Z",
            },
            "slow_agent": {
                "agent_name": "slow_agent",
                "total_invocations": 20,
                "successful_invocations": 12,
                "failed_invocations": 8,
                "total_tokens": 60000,
                "total_cost_usd": 1.0,
                "total_duration_seconds": 2400.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "strengths": [],
                "weaknesses": [],
                "xp_earned": 300,
                "level": 2,
                "last_seen": "2026-02-14T10:00:00Z",
            },
        }

        state: DashboardState = {"agents": agents, "events": events}
        result = update_agent_strengths_weaknesses(state, window_size=20, min_events=5)

        # Fast agent should have strengths
        fast_strengths = result["agents"]["fast_agent"]["strengths"]
        assert "fast_execution" in fast_strengths
        assert "high_success_rate" in fast_strengths
        assert "low_cost" in fast_strengths

        # Slow agent should have weaknesses
        slow_weaknesses = result["agents"]["slow_agent"]["weaknesses"]
        assert "slow" in slow_weaknesses
        assert "expensive" in slow_weaknesses
        assert "high_error_rate" in slow_weaknesses


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
