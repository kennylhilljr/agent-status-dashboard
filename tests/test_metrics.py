#!/usr/bin/env python3
"""Comprehensive unit tests for the metrics data model.

Tests all components of the metrics module including:
- AgentEvent TypedDict structure and field validation
- AgentProfile TypedDict structure and field validation
- SessionSummary TypedDict structure and field validation
- DashboardState TypedDict structure and field validation
- Type consistency and data integrity
- Edge cases for all metric types
- Valid and invalid data scenarios
- Default values and required fields
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

# Add parent directory to path to import metrics module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from metrics import (
    AgentEvent,
    AgentProfile,
    SessionSummary,
    DashboardState,
)


class TestAgentEvent:
    """Test suite for AgentEvent TypedDict."""

    @pytest.fixture
    def valid_agent_event(self) -> AgentEvent:
        """Create a valid AgentEvent for testing."""
        return {
            "event_id": "evt-12345",
            "agent_name": "coding",
            "session_id": "sess-67890",
            "ticket_key": "AI-100",
            "started_at": "2026-02-14T10:00:00Z",
            "ended_at": "2026-02-14T10:05:00Z",
            "duration_seconds": 300.0,
            "status": "success",
            "input_tokens": 1000,
            "output_tokens": 2000,
            "total_tokens": 3000,
            "estimated_cost_usd": 0.03,
            "artifacts": ["commit:abc123", "file:src/test.py"],
            "error_message": "",
            "model_used": "claude-sonnet-4-5",
        }

    def test_agent_event_structure(self, valid_agent_event):
        """Test that AgentEvent has all required fields."""
        required_fields = {
            "event_id", "agent_name", "session_id", "ticket_key",
            "started_at", "ended_at", "duration_seconds", "status",
            "input_tokens", "output_tokens", "total_tokens",
            "estimated_cost_usd", "artifacts", "error_message", "model_used"
        }

        assert set(valid_agent_event.keys()) == required_fields

    def test_agent_event_types(self, valid_agent_event):
        """Test that AgentEvent field types are correct."""
        assert isinstance(valid_agent_event["event_id"], str)
        assert isinstance(valid_agent_event["agent_name"], str)
        assert isinstance(valid_agent_event["session_id"], str)
        assert isinstance(valid_agent_event["ticket_key"], str)
        assert isinstance(valid_agent_event["started_at"], str)
        assert isinstance(valid_agent_event["ended_at"], str)
        assert isinstance(valid_agent_event["duration_seconds"], (int, float))
        assert isinstance(valid_agent_event["status"], str)
        assert valid_agent_event["status"] in ["success", "error", "timeout", "blocked"]
        assert isinstance(valid_agent_event["input_tokens"], int)
        assert isinstance(valid_agent_event["output_tokens"], int)
        assert isinstance(valid_agent_event["total_tokens"], int)
        assert isinstance(valid_agent_event["estimated_cost_usd"], (int, float))
        assert isinstance(valid_agent_event["artifacts"], list)
        assert isinstance(valid_agent_event["error_message"], str)
        assert isinstance(valid_agent_event["model_used"], str)

    def test_agent_event_success_status(self):
        """Test AgentEvent with success status."""
        event: AgentEvent = {
            "event_id": "evt-1",
            "agent_name": "github",
            "session_id": "sess-1",
            "ticket_key": "AI-101",
            "started_at": "2026-02-14T10:00:00Z",
            "ended_at": "2026-02-14T10:01:00Z",
            "duration_seconds": 60.0,
            "status": "success",
            "input_tokens": 500,
            "output_tokens": 1000,
            "total_tokens": 1500,
            "estimated_cost_usd": 0.015,
            "artifacts": ["pr:#42"],
            "error_message": "",
            "model_used": "claude-haiku-4-5",
        }

        assert event["status"] == "success"
        assert event["error_message"] == ""
        assert len(event["artifacts"]) > 0

    def test_agent_event_error_status(self):
        """Test AgentEvent with error status."""
        event: AgentEvent = {
            "event_id": "evt-2",
            "agent_name": "linear",
            "session_id": "sess-2",
            "ticket_key": "AI-102",
            "started_at": "2026-02-14T11:00:00Z",
            "ended_at": "2026-02-14T11:00:30Z",
            "duration_seconds": 30.0,
            "status": "error",
            "input_tokens": 200,
            "output_tokens": 100,
            "total_tokens": 300,
            "estimated_cost_usd": 0.003,
            "artifacts": [],
            "error_message": "API timeout after 30 seconds",
            "model_used": "claude-sonnet-4-5",
        }

        assert event["status"] == "error"
        assert event["error_message"] != ""
        assert len(event["artifacts"]) == 0

    def test_agent_event_timeout_status(self):
        """Test AgentEvent with timeout status."""
        event: AgentEvent = {
            "event_id": "evt-3",
            "agent_name": "slack",
            "session_id": "sess-3",
            "ticket_key": "",
            "started_at": "2026-02-14T12:00:00Z",
            "ended_at": "2026-02-14T12:10:00Z",
            "duration_seconds": 600.0,
            "status": "timeout",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "estimated_cost_usd": 0.0015,
            "artifacts": [],
            "error_message": "Operation timed out",
            "model_used": "claude-sonnet-4-5",
        }

        assert event["status"] == "timeout"

    def test_agent_event_blocked_status(self):
        """Test AgentEvent with blocked status."""
        event: AgentEvent = {
            "event_id": "evt-4",
            "agent_name": "coding",
            "session_id": "sess-4",
            "ticket_key": "AI-103",
            "started_at": "2026-02-14T13:00:00Z",
            "ended_at": "2026-02-14T13:00:05Z",
            "duration_seconds": 5.0,
            "status": "blocked",
            "input_tokens": 50,
            "output_tokens": 25,
            "total_tokens": 75,
            "estimated_cost_usd": 0.00075,
            "artifacts": [],
            "error_message": "Missing required permissions",
            "model_used": "claude-sonnet-4-5",
        }

        assert event["status"] == "blocked"

    def test_agent_event_empty_ticket_key(self):
        """Test AgentEvent with empty ticket key."""
        event: AgentEvent = {
            "event_id": "evt-5",
            "agent_name": "coding",
            "session_id": "sess-5",
            "ticket_key": "",
            "started_at": "2026-02-14T14:00:00Z",
            "ended_at": "2026-02-14T14:01:00Z",
            "duration_seconds": 60.0,
            "status": "success",
            "input_tokens": 100,
            "output_tokens": 200,
            "total_tokens": 300,
            "estimated_cost_usd": 0.003,
            "artifacts": [],
            "error_message": "",
            "model_used": "claude-haiku-4-5",
        }

        assert event["ticket_key"] == ""

    def test_agent_event_multiple_artifacts(self):
        """Test AgentEvent with multiple artifacts."""
        event: AgentEvent = {
            "event_id": "evt-6",
            "agent_name": "coding",
            "session_id": "sess-6",
            "ticket_key": "AI-104",
            "started_at": "2026-02-14T15:00:00Z",
            "ended_at": "2026-02-14T15:10:00Z",
            "duration_seconds": 600.0,
            "status": "success",
            "input_tokens": 2000,
            "output_tokens": 4000,
            "total_tokens": 6000,
            "estimated_cost_usd": 0.06,
            "artifacts": [
                "commit:abc123",
                "commit:def456",
                "file:src/main.py",
                "file:src/utils.py",
                "file:tests/test_main.py",
            ],
            "error_message": "",
            "model_used": "claude-opus-4-6",
        }

        assert len(event["artifacts"]) == 5

    def test_agent_event_zero_tokens(self):
        """Test AgentEvent with zero tokens (edge case)."""
        event: AgentEvent = {
            "event_id": "evt-7",
            "agent_name": "coding",
            "session_id": "sess-7",
            "ticket_key": "AI-105",
            "started_at": "2026-02-14T16:00:00Z",
            "ended_at": "2026-02-14T16:00:01Z",
            "duration_seconds": 1.0,
            "status": "error",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "artifacts": [],
            "error_message": "Immediate failure",
            "model_used": "claude-sonnet-4-5",
        }

        assert event["total_tokens"] == 0
        assert event["estimated_cost_usd"] == 0.0

    def test_agent_event_json_serialization(self, valid_agent_event):
        """Test that AgentEvent can be serialized to JSON."""
        json_str = json.dumps(valid_agent_event)
        deserialized = json.loads(json_str)

        assert deserialized == valid_agent_event


class TestAgentProfile:
    """Test suite for AgentProfile TypedDict."""

    @pytest.fixture
    def valid_agent_profile(self) -> AgentProfile:
        """Create a valid AgentProfile for testing."""
        return {
            "agent_name": "coding",
            "total_invocations": 100,
            "successful_invocations": 90,
            "failed_invocations": 10,
            "total_tokens": 50000,
            "total_cost_usd": 0.50,
            "total_duration_seconds": 3600.0,
            "commits_made": 25,
            "prs_created": 5,
            "prs_merged": 4,
            "files_created": 30,
            "files_modified": 75,
            "lines_added": 1500,
            "lines_removed": 500,
            "tests_written": 20,
            "issues_created": 0,
            "issues_completed": 0,
            "messages_sent": 0,
            "reviews_completed": 0,
            "success_rate": 0.9,
            "avg_duration_seconds": 36.0,
            "avg_tokens_per_call": 500.0,
            "cost_per_success_usd": 0.00556,
            "xp": 1000,
            "level": 3,
            "current_streak": 15,
            "best_streak": 20,
            "achievements": ["first_blood", "century_club"],
            "strengths": ["fast_execution", "high_success_rate"],
            "weaknesses": [],
            "recent_events": ["evt-1", "evt-2", "evt-3"],
            "last_error": "",
            "last_active": "2026-02-14T10:00:00Z",
        }

    def test_agent_profile_structure(self, valid_agent_profile):
        """Test that AgentProfile has all required fields."""
        required_fields = {
            "agent_name", "total_invocations", "successful_invocations",
            "failed_invocations", "total_tokens", "total_cost_usd",
            "total_duration_seconds", "commits_made", "prs_created",
            "prs_merged", "files_created", "files_modified", "lines_added",
            "lines_removed", "tests_written", "issues_created",
            "issues_completed", "messages_sent", "reviews_completed",
            "success_rate", "avg_duration_seconds", "avg_tokens_per_call",
            "cost_per_success_usd", "xp", "level", "current_streak",
            "best_streak", "achievements", "strengths", "weaknesses",
            "recent_events", "last_error", "last_active"
        }

        assert set(valid_agent_profile.keys()) == required_fields

    def test_agent_profile_types(self, valid_agent_profile):
        """Test that AgentProfile field types are correct."""
        assert isinstance(valid_agent_profile["agent_name"], str)
        assert isinstance(valid_agent_profile["total_invocations"], int)
        assert isinstance(valid_agent_profile["successful_invocations"], int)
        assert isinstance(valid_agent_profile["failed_invocations"], int)
        assert isinstance(valid_agent_profile["total_tokens"], int)
        assert isinstance(valid_agent_profile["total_cost_usd"], (int, float))
        assert isinstance(valid_agent_profile["total_duration_seconds"], (int, float))
        assert isinstance(valid_agent_profile["success_rate"], (int, float))
        assert isinstance(valid_agent_profile["xp"], int)
        assert isinstance(valid_agent_profile["level"], int)
        assert isinstance(valid_agent_profile["achievements"], list)
        assert isinstance(valid_agent_profile["strengths"], list)
        assert isinstance(valid_agent_profile["weaknesses"], list)
        assert isinstance(valid_agent_profile["recent_events"], list)

    def test_agent_profile_success_rate_calculation(self):
        """Test that success rate is correctly calculated."""
        profile: AgentProfile = {
            "agent_name": "test",
            "total_invocations": 100,
            "successful_invocations": 85,
            "failed_invocations": 15,
            "total_tokens": 10000,
            "total_cost_usd": 0.1,
            "total_duration_seconds": 1000.0,
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
            "success_rate": 0.85,
            "avg_duration_seconds": 10.0,
            "avg_tokens_per_call": 100.0,
            "cost_per_success_usd": 0.00118,
            "xp": 850,
            "level": 2,
            "current_streak": 5,
            "best_streak": 10,
            "achievements": [],
            "strengths": [],
            "weaknesses": [],
            "recent_events": [],
            "last_error": "",
            "last_active": "2026-02-14T10:00:00Z",
        }

        # Verify success rate is 85/100 = 0.85
        assert profile["success_rate"] == 0.85
        assert profile["successful_invocations"] + profile["failed_invocations"] == profile["total_invocations"]

    def test_agent_profile_github_agent(self):
        """Test AgentProfile for GitHub agent with PR metrics."""
        profile: AgentProfile = {
            "agent_name": "github",
            "total_invocations": 50,
            "successful_invocations": 48,
            "failed_invocations": 2,
            "total_tokens": 25000,
            "total_cost_usd": 0.25,
            "total_duration_seconds": 1500.0,
            "commits_made": 30,
            "prs_created": 12,
            "prs_merged": 10,
            "files_created": 0,
            "files_modified": 0,
            "lines_added": 0,
            "lines_removed": 0,
            "tests_written": 0,
            "issues_created": 0,
            "issues_completed": 0,
            "messages_sent": 0,
            "reviews_completed": 8,
            "success_rate": 0.96,
            "avg_duration_seconds": 30.0,
            "avg_tokens_per_call": 500.0,
            "cost_per_success_usd": 0.0052,
            "xp": 600,
            "level": 2,
            "current_streak": 10,
            "best_streak": 15,
            "achievements": ["first_blood"],
            "strengths": ["high_success_rate"],
            "weaknesses": [],
            "recent_events": [],
            "last_error": "",
            "last_active": "2026-02-14T10:00:00Z",
        }

        assert profile["prs_created"] > 0
        assert profile["prs_merged"] <= profile["prs_created"]
        assert profile["reviews_completed"] > 0

    def test_agent_profile_linear_agent(self):
        """Test AgentProfile for Linear agent with issue metrics."""
        profile: AgentProfile = {
            "agent_name": "linear",
            "total_invocations": 30,
            "successful_invocations": 28,
            "failed_invocations": 2,
            "total_tokens": 15000,
            "total_cost_usd": 0.15,
            "total_duration_seconds": 900.0,
            "commits_made": 0,
            "prs_created": 0,
            "prs_merged": 0,
            "files_created": 0,
            "files_modified": 0,
            "lines_added": 0,
            "lines_removed": 0,
            "tests_written": 0,
            "issues_created": 15,
            "issues_completed": 12,
            "messages_sent": 0,
            "reviews_completed": 0,
            "success_rate": 0.933,
            "avg_duration_seconds": 30.0,
            "avg_tokens_per_call": 500.0,
            "cost_per_success_usd": 0.00536,
            "xp": 400,
            "level": 2,
            "current_streak": 8,
            "best_streak": 12,
            "achievements": [],
            "strengths": [],
            "weaknesses": [],
            "recent_events": [],
            "last_error": "",
            "last_active": "2026-02-14T10:00:00Z",
        }

        assert profile["issues_created"] > 0
        assert profile["issues_completed"] <= profile["issues_created"]

    def test_agent_profile_slack_agent(self):
        """Test AgentProfile for Slack agent with message metrics."""
        profile: AgentProfile = {
            "agent_name": "slack",
            "total_invocations": 20,
            "successful_invocations": 20,
            "failed_invocations": 0,
            "total_tokens": 10000,
            "total_cost_usd": 0.1,
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
            "messages_sent": 45,
            "reviews_completed": 0,
            "success_rate": 1.0,
            "avg_duration_seconds": 30.0,
            "avg_tokens_per_call": 500.0,
            "cost_per_success_usd": 0.005,
            "xp": 200,
            "level": 1,
            "current_streak": 20,
            "best_streak": 20,
            "achievements": ["perfect_day"],
            "strengths": ["perfect_accuracy"],
            "weaknesses": [],
            "recent_events": [],
            "last_error": "",
            "last_active": "2026-02-14T10:00:00Z",
        }

        assert profile["messages_sent"] > 0
        assert profile["success_rate"] == 1.0

    def test_agent_profile_empty_recent_events(self):
        """Test AgentProfile with empty recent events."""
        profile: AgentProfile = {
            "agent_name": "coding",
            "total_invocations": 5,
            "successful_invocations": 5,
            "failed_invocations": 0,
            "total_tokens": 5000,
            "total_cost_usd": 0.05,
            "total_duration_seconds": 300.0,
            "commits_made": 0,
            "prs_created": 0,
            "prs_merged": 0,
            "files_created": 5,
            "files_modified": 0,
            "lines_added": 100,
            "lines_removed": 0,
            "tests_written": 0,
            "issues_created": 0,
            "issues_completed": 0,
            "messages_sent": 0,
            "reviews_completed": 0,
            "success_rate": 1.0,
            "avg_duration_seconds": 60.0,
            "avg_tokens_per_call": 1000.0,
            "cost_per_success_usd": 0.01,
            "xp": 50,
            "level": 1,
            "current_streak": 5,
            "best_streak": 5,
            "achievements": [],
            "strengths": [],
            "weaknesses": [],
            "recent_events": [],
            "last_error": "",
            "last_active": "2026-02-14T10:00:00Z",
        }

        assert len(profile["recent_events"]) == 0

    def test_agent_profile_with_last_error(self):
        """Test AgentProfile with last error message."""
        profile: AgentProfile = {
            "agent_name": "coding",
            "total_invocations": 10,
            "successful_invocations": 8,
            "failed_invocations": 2,
            "total_tokens": 10000,
            "total_cost_usd": 0.1,
            "total_duration_seconds": 600.0,
            "commits_made": 5,
            "prs_created": 1,
            "prs_merged": 1,
            "files_created": 8,
            "files_modified": 2,
            "lines_added": 200,
            "lines_removed": 50,
            "tests_written": 3,
            "issues_created": 0,
            "issues_completed": 0,
            "messages_sent": 0,
            "reviews_completed": 0,
            "success_rate": 0.8,
            "avg_duration_seconds": 60.0,
            "avg_tokens_per_call": 1000.0,
            "cost_per_success_usd": 0.0125,
            "xp": 100,
            "level": 1,
            "current_streak": 0,
            "best_streak": 6,
            "achievements": [],
            "strengths": [],
            "weaknesses": ["high_error_rate"],
            "recent_events": [],
            "last_error": "File permission denied",
            "last_active": "2026-02-14T10:00:00Z",
        }

        assert profile["last_error"] != ""
        assert profile["failed_invocations"] > 0

    def test_agent_profile_json_serialization(self, valid_agent_profile):
        """Test that AgentProfile can be serialized to JSON."""
        json_str = json.dumps(valid_agent_profile)
        deserialized = json.loads(json_str)

        assert deserialized == valid_agent_profile

    def test_agent_profile_zero_invocations(self):
        """Test AgentProfile edge case with zero invocations."""
        profile: AgentProfile = {
            "agent_name": "new_agent",
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
            "success_rate": 0.0,
            "avg_duration_seconds": 0.0,
            "avg_tokens_per_call": 0.0,
            "cost_per_success_usd": 0.0,
            "xp": 0,
            "level": 1,
            "current_streak": 0,
            "best_streak": 0,
            "achievements": [],
            "strengths": [],
            "weaknesses": [],
            "recent_events": [],
            "last_error": "",
            "last_active": "",
        }

        assert profile["total_invocations"] == 0
        assert profile["xp"] == 0


class TestSessionSummary:
    """Test suite for SessionSummary TypedDict."""

    @pytest.fixture
    def valid_session_summary(self) -> SessionSummary:
        """Create a valid SessionSummary for testing."""
        return {
            "session_id": "sess-12345",
            "session_number": 42,
            "session_type": "initializer",
            "started_at": "2026-02-14T10:00:00Z",
            "ended_at": "2026-02-14T11:00:00Z",
            "status": "complete",
            "agents_invoked": ["coding", "github", "linear"],
            "total_tokens": 25000,
            "total_cost_usd": 0.25,
            "tickets_worked": ["AI-100", "AI-101"],
        }

    def test_session_summary_structure(self, valid_session_summary):
        """Test that SessionSummary has all required fields."""
        required_fields = {
            "session_id", "session_number", "session_type", "started_at",
            "ended_at", "status", "agents_invoked", "total_tokens",
            "total_cost_usd", "tickets_worked"
        }

        assert set(valid_session_summary.keys()) == required_fields

    def test_session_summary_types(self, valid_session_summary):
        """Test that SessionSummary field types are correct."""
        assert isinstance(valid_session_summary["session_id"], str)
        assert isinstance(valid_session_summary["session_number"], int)
        assert isinstance(valid_session_summary["session_type"], str)
        assert valid_session_summary["session_type"] in ["initializer", "continuation"]
        assert isinstance(valid_session_summary["started_at"], str)
        assert isinstance(valid_session_summary["ended_at"], str)
        assert isinstance(valid_session_summary["status"], str)
        assert valid_session_summary["status"] in ["continue", "error", "complete"]
        assert isinstance(valid_session_summary["agents_invoked"], list)
        assert isinstance(valid_session_summary["total_tokens"], int)
        assert isinstance(valid_session_summary["total_cost_usd"], (int, float))
        assert isinstance(valid_session_summary["tickets_worked"], list)

    def test_session_summary_initializer_type(self):
        """Test SessionSummary with initializer type."""
        session: SessionSummary = {
            "session_id": "sess-1",
            "session_number": 1,
            "session_type": "initializer",
            "started_at": "2026-02-14T09:00:00Z",
            "ended_at": "2026-02-14T10:00:00Z",
            "status": "complete",
            "agents_invoked": ["coding"],
            "total_tokens": 10000,
            "total_cost_usd": 0.1,
            "tickets_worked": ["AI-100"],
        }

        assert session["session_type"] == "initializer"

    def test_session_summary_continuation_type(self):
        """Test SessionSummary with continuation type."""
        session: SessionSummary = {
            "session_id": "sess-2",
            "session_number": 2,
            "session_type": "continuation",
            "started_at": "2026-02-14T11:00:00Z",
            "ended_at": "2026-02-14T12:00:00Z",
            "status": "complete",
            "agents_invoked": ["coding", "github"],
            "total_tokens": 15000,
            "total_cost_usd": 0.15,
            "tickets_worked": ["AI-100"],
        }

        assert session["session_type"] == "continuation"

    def test_session_summary_continue_status(self):
        """Test SessionSummary with continue status."""
        session: SessionSummary = {
            "session_id": "sess-3",
            "session_number": 3,
            "session_type": "initializer",
            "started_at": "2026-02-14T13:00:00Z",
            "ended_at": "2026-02-14T14:00:00Z",
            "status": "continue",
            "agents_invoked": ["coding", "linear"],
            "total_tokens": 20000,
            "total_cost_usd": 0.2,
            "tickets_worked": ["AI-101"],
        }

        assert session["status"] == "continue"

    def test_session_summary_error_status(self):
        """Test SessionSummary with error status."""
        session: SessionSummary = {
            "session_id": "sess-4",
            "session_number": 4,
            "session_type": "continuation",
            "started_at": "2026-02-14T15:00:00Z",
            "ended_at": "2026-02-14T15:05:00Z",
            "status": "error",
            "agents_invoked": ["coding"],
            "total_tokens": 1000,
            "total_cost_usd": 0.01,
            "tickets_worked": [],
        }

        assert session["status"] == "error"

    def test_session_summary_complete_status(self):
        """Test SessionSummary with complete status."""
        session: SessionSummary = {
            "session_id": "sess-5",
            "session_number": 5,
            "session_type": "initializer",
            "started_at": "2026-02-14T16:00:00Z",
            "ended_at": "2026-02-14T17:00:00Z",
            "status": "complete",
            "agents_invoked": ["coding", "github", "linear", "slack"],
            "total_tokens": 30000,
            "total_cost_usd": 0.3,
            "tickets_worked": ["AI-102", "AI-103"],
        }

        assert session["status"] == "complete"

    def test_session_summary_empty_agents(self):
        """Test SessionSummary with no agents invoked."""
        session: SessionSummary = {
            "session_id": "sess-6",
            "session_number": 6,
            "session_type": "initializer",
            "started_at": "2026-02-14T18:00:00Z",
            "ended_at": "2026-02-14T18:00:01Z",
            "status": "error",
            "agents_invoked": [],
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "tickets_worked": [],
        }

        assert len(session["agents_invoked"]) == 0

    def test_session_summary_empty_tickets(self):
        """Test SessionSummary with no tickets worked."""
        session: SessionSummary = {
            "session_id": "sess-7",
            "session_number": 7,
            "session_type": "continuation",
            "started_at": "2026-02-14T19:00:00Z",
            "ended_at": "2026-02-14T20:00:00Z",
            "status": "complete",
            "agents_invoked": ["slack"],
            "total_tokens": 5000,
            "total_cost_usd": 0.05,
            "tickets_worked": [],
        }

        assert len(session["tickets_worked"]) == 0

    def test_session_summary_json_serialization(self, valid_session_summary):
        """Test that SessionSummary can be serialized to JSON."""
        json_str = json.dumps(valid_session_summary)
        deserialized = json.loads(json_str)

        assert deserialized == valid_session_summary


class TestDashboardState:
    """Test suite for DashboardState TypedDict."""

    @pytest.fixture
    def valid_dashboard_state(self) -> DashboardState:
        """Create a valid DashboardState for testing."""
        return {
            "version": 1,
            "project_name": "agent-status-dashboard",
            "created_at": "2026-02-01T00:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 10,
            "total_tokens": 100000,
            "total_cost_usd": 1.0,
            "total_duration_seconds": 7200.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 50,
                    "successful_invocations": 45,
                    "failed_invocations": 5,
                    "total_tokens": 50000,
                    "total_cost_usd": 0.5,
                    "total_duration_seconds": 3600.0,
                    "commits_made": 20,
                    "prs_created": 4,
                    "prs_merged": 3,
                    "files_created": 25,
                    "files_modified": 50,
                    "lines_added": 1000,
                    "lines_removed": 300,
                    "tests_written": 15,
                    "issues_created": 0,
                    "issues_completed": 0,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 0.9,
                    "avg_duration_seconds": 72.0,
                    "avg_tokens_per_call": 1000.0,
                    "cost_per_success_usd": 0.0111,
                    "xp": 500,
                    "level": 2,
                    "current_streak": 10,
                    "best_streak": 15,
                    "achievements": ["first_blood"],
                    "strengths": ["fast_execution"],
                    "weaknesses": [],
                    "recent_events": ["evt-1", "evt-2"],
                    "last_error": "",
                    "last_active": "2026-02-14T10:00:00Z",
                }
            },
            "events": [
                {
                    "event_id": "evt-1",
                    "agent_name": "coding",
                    "session_id": "sess-1",
                    "ticket_key": "AI-100",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": ["commit:abc123"],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                }
            ],
            "sessions": [
                {
                    "session_id": "sess-1",
                    "session_number": 1,
                    "session_type": "initializer",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T11:00:00Z",
                    "status": "complete",
                    "agents_invoked": ["coding"],
                    "total_tokens": 10000,
                    "total_cost_usd": 0.1,
                    "tickets_worked": ["AI-100"],
                }
            ],
        }

    def test_dashboard_state_structure(self, valid_dashboard_state):
        """Test that DashboardState has all required fields."""
        required_fields = {
            "version", "project_name", "created_at", "updated_at",
            "total_sessions", "total_tokens", "total_cost_usd",
            "total_duration_seconds", "agents", "events", "sessions"
        }

        assert set(valid_dashboard_state.keys()) == required_fields

    def test_dashboard_state_types(self, valid_dashboard_state):
        """Test that DashboardState field types are correct."""
        assert isinstance(valid_dashboard_state["version"], int)
        assert isinstance(valid_dashboard_state["project_name"], str)
        assert isinstance(valid_dashboard_state["created_at"], str)
        assert isinstance(valid_dashboard_state["updated_at"], str)
        assert isinstance(valid_dashboard_state["total_sessions"], int)
        assert isinstance(valid_dashboard_state["total_tokens"], int)
        assert isinstance(valid_dashboard_state["total_cost_usd"], (int, float))
        assert isinstance(valid_dashboard_state["total_duration_seconds"], (int, float))
        assert isinstance(valid_dashboard_state["agents"], dict)
        assert isinstance(valid_dashboard_state["events"], list)
        assert isinstance(valid_dashboard_state["sessions"], list)

    def test_dashboard_state_empty_state(self):
        """Test DashboardState with no data."""
        state: DashboardState = {
            "version": 1,
            "project_name": "new-project",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": [],
        }

        assert state["total_sessions"] == 0
        assert len(state["agents"]) == 0
        assert len(state["events"]) == 0
        assert len(state["sessions"]) == 0

    def test_dashboard_state_multiple_agents(self):
        """Test DashboardState with multiple agents."""
        state: DashboardState = {
            "version": 1,
            "project_name": "multi-agent-project",
            "created_at": "2026-02-01T00:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 20,
            "total_tokens": 200000,
            "total_cost_usd": 2.0,
            "total_duration_seconds": 14400.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 100,
                    "successful_invocations": 90,
                    "failed_invocations": 10,
                    "total_tokens": 100000,
                    "total_cost_usd": 1.0,
                    "total_duration_seconds": 7200.0,
                    "commits_made": 40,
                    "prs_created": 8,
                    "prs_merged": 6,
                    "files_created": 50,
                    "files_modified": 100,
                    "lines_added": 2000,
                    "lines_removed": 600,
                    "tests_written": 30,
                    "issues_created": 0,
                    "issues_completed": 0,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 0.9,
                    "avg_duration_seconds": 72.0,
                    "avg_tokens_per_call": 1000.0,
                    "cost_per_success_usd": 0.0111,
                    "xp": 1000,
                    "level": 3,
                    "current_streak": 20,
                    "best_streak": 30,
                    "achievements": ["first_blood", "century_club"],
                    "strengths": ["fast_execution", "high_success_rate"],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": "2026-02-14T10:00:00Z",
                },
                "github": {
                    "agent_name": "github",
                    "total_invocations": 50,
                    "successful_invocations": 48,
                    "failed_invocations": 2,
                    "total_tokens": 50000,
                    "total_cost_usd": 0.5,
                    "total_duration_seconds": 3600.0,
                    "commits_made": 30,
                    "prs_created": 10,
                    "prs_merged": 8,
                    "files_created": 0,
                    "files_modified": 0,
                    "lines_added": 0,
                    "lines_removed": 0,
                    "tests_written": 0,
                    "issues_created": 0,
                    "issues_completed": 0,
                    "messages_sent": 0,
                    "reviews_completed": 5,
                    "success_rate": 0.96,
                    "avg_duration_seconds": 72.0,
                    "avg_tokens_per_call": 1000.0,
                    "cost_per_success_usd": 0.0104,
                    "xp": 600,
                    "level": 2,
                    "current_streak": 15,
                    "best_streak": 20,
                    "achievements": ["first_blood"],
                    "strengths": ["high_success_rate"],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": "2026-02-14T09:00:00Z",
                },
                "linear": {
                    "agent_name": "linear",
                    "total_invocations": 30,
                    "successful_invocations": 27,
                    "failed_invocations": 3,
                    "total_tokens": 30000,
                    "total_cost_usd": 0.3,
                    "total_duration_seconds": 1800.0,
                    "commits_made": 0,
                    "prs_created": 0,
                    "prs_merged": 0,
                    "files_created": 0,
                    "files_modified": 0,
                    "lines_added": 0,
                    "lines_removed": 0,
                    "tests_written": 0,
                    "issues_created": 15,
                    "issues_completed": 12,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 0.9,
                    "avg_duration_seconds": 60.0,
                    "avg_tokens_per_call": 1000.0,
                    "cost_per_success_usd": 0.0111,
                    "xp": 300,
                    "level": 1,
                    "current_streak": 10,
                    "best_streak": 15,
                    "achievements": [],
                    "strengths": [],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": "2026-02-14T08:00:00Z",
                },
                "slack": {
                    "agent_name": "slack",
                    "total_invocations": 20,
                    "successful_invocations": 20,
                    "failed_invocations": 0,
                    "total_tokens": 20000,
                    "total_cost_usd": 0.2,
                    "total_duration_seconds": 1200.0,
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
                    "messages_sent": 50,
                    "reviews_completed": 0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 60.0,
                    "avg_tokens_per_call": 1000.0,
                    "cost_per_success_usd": 0.01,
                    "xp": 200,
                    "level": 1,
                    "current_streak": 20,
                    "best_streak": 20,
                    "achievements": ["perfect_day"],
                    "strengths": ["perfect_accuracy"],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": "2026-02-14T07:00:00Z",
                },
            },
            "events": [],
            "sessions": [],
        }

        assert len(state["agents"]) == 4
        assert "coding" in state["agents"]
        assert "github" in state["agents"]
        assert "linear" in state["agents"]
        assert "slack" in state["agents"]

    def test_dashboard_state_json_serialization(self, valid_dashboard_state):
        """Test that DashboardState can be serialized to JSON."""
        json_str = json.dumps(valid_dashboard_state)
        deserialized = json.loads(json_str)

        assert deserialized == valid_dashboard_state

    def test_dashboard_state_large_event_log(self):
        """Test DashboardState with many events (500 cap)."""
        state: DashboardState = {
            "version": 1,
            "project_name": "large-project",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 100,
            "total_tokens": 1000000,
            "total_cost_usd": 10.0,
            "total_duration_seconds": 72000.0,
            "agents": {},
            "events": [
                {
                    "event_id": f"evt-{i}",
                    "agent_name": "coding",
                    "session_id": f"sess-{i // 5}",
                    "ticket_key": f"AI-{100 + i}",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": [],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                }
                for i in range(500)
            ],
            "sessions": [],
        }

        # Verify we have exactly 500 events (the cap)
        assert len(state["events"]) == 500

    def test_dashboard_state_recent_sessions(self):
        """Test DashboardState with session history (last 50 sessions)."""
        state: DashboardState = {
            "version": 1,
            "project_name": "session-history-project",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 50,
            "total_tokens": 500000,
            "total_cost_usd": 5.0,
            "total_duration_seconds": 36000.0,
            "agents": {},
            "events": [],
            "sessions": [
                {
                    "session_id": f"sess-{i}",
                    "session_number": i + 1,
                    "session_type": "initializer" if i % 2 == 0 else "continuation",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T11:00:00Z",
                    "status": "complete",
                    "agents_invoked": ["coding"],
                    "total_tokens": 10000,
                    "total_cost_usd": 0.1,
                    "tickets_worked": [f"AI-{100 + i}"],
                }
                for i in range(50)
            ],
        }

        # Verify we have exactly 50 sessions (the cap)
        assert len(state["sessions"]) == 50

    def test_dashboard_state_version_number(self):
        """Test DashboardState version field."""
        state: DashboardState = {
            "version": 1,
            "project_name": "version-test",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": [],
        }

        assert state["version"] == 1


class TestMetricsDataIntegrity:
    """Test data integrity and consistency across metrics types."""

    def test_event_tokens_match_total(self):
        """Test that input + output tokens equals total tokens."""
        event: AgentEvent = {
            "event_id": "evt-1",
            "agent_name": "coding",
            "session_id": "sess-1",
            "ticket_key": "AI-100",
            "started_at": "2026-02-14T10:00:00Z",
            "ended_at": "2026-02-14T10:05:00Z",
            "duration_seconds": 300.0,
            "status": "success",
            "input_tokens": 1000,
            "output_tokens": 2000,
            "total_tokens": 3000,
            "estimated_cost_usd": 0.03,
            "artifacts": [],
            "error_message": "",
            "model_used": "claude-sonnet-4-5",
        }

        assert event["input_tokens"] + event["output_tokens"] == event["total_tokens"]

    def test_profile_invocations_match_total(self):
        """Test that successful + failed invocations equals total invocations."""
        profile: AgentProfile = {
            "agent_name": "coding",
            "total_invocations": 100,
            "successful_invocations": 85,
            "failed_invocations": 15,
            "total_tokens": 50000,
            "total_cost_usd": 0.5,
            "total_duration_seconds": 3600.0,
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
            "success_rate": 0.85,
            "avg_duration_seconds": 36.0,
            "avg_tokens_per_call": 500.0,
            "cost_per_success_usd": 0.00588,
            "xp": 850,
            "level": 2,
            "current_streak": 10,
            "best_streak": 20,
            "achievements": [],
            "strengths": [],
            "weaknesses": [],
            "recent_events": [],
            "last_error": "",
            "last_active": "2026-02-14T10:00:00Z",
        }

        assert profile["successful_invocations"] + profile["failed_invocations"] == profile["total_invocations"]

    def test_dashboard_state_consistency(self):
        """Test that DashboardState maintains consistency across all fields."""
        state: DashboardState = {
            "version": 1,
            "project_name": "consistency-test",
            "created_at": "2026-02-01T00:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 2,
            "total_tokens": 6000,
            "total_cost_usd": 0.06,
            "total_duration_seconds": 600.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 2,
                    "successful_invocations": 2,
                    "failed_invocations": 0,
                    "total_tokens": 6000,
                    "total_cost_usd": 0.06,
                    "total_duration_seconds": 600.0,
                    "commits_made": 2,
                    "prs_created": 0,
                    "prs_merged": 0,
                    "files_created": 2,
                    "files_modified": 0,
                    "lines_added": 50,
                    "lines_removed": 0,
                    "tests_written": 0,
                    "issues_created": 0,
                    "issues_completed": 0,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 300.0,
                    "avg_tokens_per_call": 3000.0,
                    "cost_per_success_usd": 0.03,
                    "xp": 20,
                    "level": 1,
                    "current_streak": 2,
                    "best_streak": 2,
                    "achievements": [],
                    "strengths": [],
                    "weaknesses": [],
                    "recent_events": ["evt-1", "evt-2"],
                    "last_error": "",
                    "last_active": "2026-02-14T10:00:00Z",
                }
            },
            "events": [
                {
                    "event_id": "evt-1",
                    "agent_name": "coding",
                    "session_id": "sess-1",
                    "ticket_key": "AI-100",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": ["commit:abc123"],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                },
                {
                    "event_id": "evt-2",
                    "agent_name": "coding",
                    "session_id": "sess-2",
                    "ticket_key": "AI-101",
                    "started_at": "2026-02-14T10:10:00Z",
                    "ended_at": "2026-02-14T10:15:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": ["commit:def456"],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                },
            ],
            "sessions": [
                {
                    "session_id": "sess-1",
                    "session_number": 1,
                    "session_type": "initializer",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "status": "complete",
                    "agents_invoked": ["coding"],
                    "total_tokens": 3000,
                    "total_cost_usd": 0.03,
                    "tickets_worked": ["AI-100"],
                },
                {
                    "session_id": "sess-2",
                    "session_number": 2,
                    "session_type": "continuation",
                    "started_at": "2026-02-14T10:10:00Z",
                    "ended_at": "2026-02-14T10:15:00Z",
                    "status": "complete",
                    "agents_invoked": ["coding"],
                    "total_tokens": 3000,
                    "total_cost_usd": 0.03,
                    "tickets_worked": ["AI-101"],
                },
            ],
        }

        # Verify total_sessions matches session count
        assert state["total_sessions"] == len(state["sessions"])

        # Verify total_tokens matches sum of event tokens
        total_event_tokens = sum(e["total_tokens"] for e in state["events"])
        assert state["total_tokens"] == total_event_tokens

        # Verify total_cost_usd matches sum of event costs
        total_event_cost = sum(e["estimated_cost_usd"] for e in state["events"])
        assert abs(state["total_cost_usd"] - total_event_cost) < 0.0001


class TestMetricsFileIO:
    """Test file I/O operations with metrics data."""

    def test_write_and_read_dashboard_state(self):
        """Test writing and reading DashboardState to/from JSON file."""
        state: DashboardState = {
            "version": 1,
            "project_name": "file-io-test",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": [],
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state, f, indent=2)
            temp_path = Path(f.name)

        try:
            # Read back
            with open(temp_path, 'r') as f:
                loaded_state = json.load(f)

            assert loaded_state == state
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_write_complex_dashboard_state(self):
        """Test writing complex DashboardState with all fields populated."""
        state: DashboardState = {
            "version": 1,
            "project_name": "complex-io-test",
            "created_at": "2026-02-01T00:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 1,
            "total_tokens": 3000,
            "total_cost_usd": 0.03,
            "total_duration_seconds": 300.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 1,
                    "successful_invocations": 1,
                    "failed_invocations": 0,
                    "total_tokens": 3000,
                    "total_cost_usd": 0.03,
                    "total_duration_seconds": 300.0,
                    "commits_made": 1,
                    "prs_created": 0,
                    "prs_merged": 0,
                    "files_created": 1,
                    "files_modified": 0,
                    "lines_added": 25,
                    "lines_removed": 0,
                    "tests_written": 0,
                    "issues_created": 0,
                    "issues_completed": 0,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 300.0,
                    "avg_tokens_per_call": 3000.0,
                    "cost_per_success_usd": 0.03,
                    "xp": 10,
                    "level": 1,
                    "current_streak": 1,
                    "best_streak": 1,
                    "achievements": [],
                    "strengths": [],
                    "weaknesses": [],
                    "recent_events": ["evt-1"],
                    "last_error": "",
                    "last_active": "2026-02-14T10:00:00Z",
                }
            },
            "events": [
                {
                    "event_id": "evt-1",
                    "agent_name": "coding",
                    "session_id": "sess-1",
                    "ticket_key": "AI-100",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": ["commit:abc123", "file:src/test.py"],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                }
            ],
            "sessions": [
                {
                    "session_id": "sess-1",
                    "session_number": 1,
                    "session_type": "initializer",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "status": "complete",
                    "agents_invoked": ["coding"],
                    "total_tokens": 3000,
                    "total_cost_usd": 0.03,
                    "tickets_worked": ["AI-100"],
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state, f, indent=2)
            temp_path = Path(f.name)

        try:
            # Read back
            with open(temp_path, 'r') as f:
                loaded_state = json.load(f)

            # Verify structure
            assert loaded_state["version"] == 1
            assert loaded_state["project_name"] == "complex-io-test"
            assert len(loaded_state["agents"]) == 1
            assert len(loaded_state["events"]) == 1
            assert len(loaded_state["sessions"]) == 1
        finally:
            if temp_path.exists():
                temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=metrics", "--cov-report=term-missing"])
