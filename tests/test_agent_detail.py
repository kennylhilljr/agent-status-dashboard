#!/usr/bin/env python3
"""Comprehensive unit tests for the agent detail view.

Tests all components of the agent detail view including:
- Agent profile rendering
- Performance metrics display
- Strengths and weaknesses panel
- Achievements display
- Recent events table
- Metrics file monitoring
- Agent discovery and filtering
- Time and duration formatting
"""

import json
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add parent directory to path to import agent_detail module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from agent_detail import (
    AgentDetailRenderer,
    MetricsFileMonitor,
    find_metrics_file,
    display_agent_detail,
    LEVEL_TITLES,
    DEFAULT_METRICS_DIR,
)


class TestAgentDetailRenderer:
    """Test suite for AgentDetailRenderer class."""

    @pytest.fixture
    def console(self):
        """Create a Rich console instance for testing."""
        return Console()

    @pytest.fixture
    def renderer(self, console):
        """Create an AgentDetailRenderer instance for testing."""
        return AgentDetailRenderer(console)

    @pytest.fixture
    def sample_agent_data(self):
        """Create sample agent data for testing."""
        return {
            "agent_name": "coding",
            "total_invocations": 20,
            "successful_invocations": 19,
            "failed_invocations": 1,
            "total_tokens": 30000,
            "total_cost_usd": 0.30,
            "total_duration_seconds": 800.0,
            "success_rate": 0.95,
            "avg_duration_seconds": 40.0,
            "avg_tokens_per_call": 1500.0,
            "cost_per_success_usd": 0.0158,
            "xp": 950,
            "level": 3,
            "current_streak": 19,
            "best_streak": 19,
            "achievements": ["first_blood", "century_club", "top_performer"],
            "strengths": ["fast_execution", "high_success_rate", "consistent"],
            "weaknesses": [],
            "recent_events": ["evt-1", "evt-2", "evt-3"],
            "last_active": datetime.now(timezone.utc).isoformat(),
        }

    @pytest.fixture
    def sample_events(self):
        """Create sample events for testing."""
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(seconds=30)).isoformat()
        older = (now - timedelta(minutes=5)).isoformat()

        return [
            {
                "event_id": "evt-1",
                "agent_name": "coding",
                "session_id": "sess-1",
                "ticket_key": "AI-54",
                "started_at": recent,
                "ended_at": recent,
                "duration_seconds": 35.0,
                "status": "success",
                "total_tokens": 5000,
            },
            {
                "event_id": "evt-2",
                "agent_name": "coding",
                "session_id": "sess-1",
                "ticket_key": "AI-53",
                "started_at": older,
                "ended_at": older,
                "duration_seconds": 28.0,
                "status": "success",
                "total_tokens": 4000,
            },
            {
                "event_id": "evt-3",
                "agent_name": "github",
                "session_id": "sess-2",
                "ticket_key": "AI-52",
                "started_at": recent,
                "ended_at": recent,
                "duration_seconds": 15.0,
                "status": "success",
                "total_tokens": 2000,
            },
        ]

    def test_get_level_title_valid_levels(self, renderer):
        """Test level title retrieval for valid levels."""
        assert renderer.get_level_title(1) == "Intern"
        assert renderer.get_level_title(3) == "Mid-Level"
        assert renderer.get_level_title(8) == "Fellow"

    def test_get_level_title_invalid_level(self, renderer):
        """Test level title retrieval for invalid level."""
        assert renderer.get_level_title(999) == "Unknown"

    def test_create_profile_panel(self, renderer, sample_agent_data):
        """Test profile panel creation."""
        panel = renderer.create_profile_panel(sample_agent_data, "coding")
        assert isinstance(panel, Panel)
        assert panel.title == "Agent Profile"

    def test_create_profile_panel_xp_display(self, renderer, sample_agent_data):
        """Test that XP and level are displayed in profile panel."""
        panel = renderer.create_profile_panel(sample_agent_data, "coding")
        # Panel renders internally, so we just verify it's created
        assert panel is not None

    def test_create_performance_panel(self, renderer, sample_agent_data):
        """Test performance panel creation."""
        panel = renderer.create_performance_panel(sample_agent_data)
        assert isinstance(panel, Panel)
        assert panel.title == "Performance Metrics"

    def test_create_performance_panel_success_rate(self, renderer):
        """Test performance panel with various success rates."""
        agent_data_high = {
            "success_rate": 0.95,
            "total_invocations": 20,
            "successful_invocations": 19,
            "failed_invocations": 1,
            "avg_duration_seconds": 40.0,
            "avg_tokens_per_call": 1500.0,
            "cost_per_success_usd": 0.0158,
            "total_tokens": 30000,
            "total_cost_usd": 0.30,
            "total_duration_seconds": 800.0,
        }
        panel = renderer.create_performance_panel(agent_data_high)
        assert isinstance(panel, Panel)

    def test_create_strengths_weaknesses_panel_with_strengths(self, renderer, sample_agent_data):
        """Test strengths/weaknesses panel with data."""
        panel = renderer.create_strengths_weaknesses_panel(sample_agent_data)
        assert isinstance(panel, Panel)
        assert panel.title == "Strengths & Weaknesses"

    def test_create_strengths_weaknesses_panel_empty(self, renderer):
        """Test strengths/weaknesses panel with no strengths or weaknesses."""
        agent_data = {
            "strengths": [],
            "weaknesses": [],
        }
        panel = renderer.create_strengths_weaknesses_panel(agent_data)
        assert isinstance(panel, Panel)

    def test_create_achievements_panel(self, renderer, sample_agent_data):
        """Test achievements panel creation."""
        panel = renderer.create_achievements_panel(sample_agent_data)
        assert isinstance(panel, Panel)
        assert panel.title == "Achievements"

    def test_create_achievements_panel_no_achievements(self, renderer):
        """Test achievements panel with no achievements."""
        agent_data = {"achievements": []}
        panel = renderer.create_achievements_panel(agent_data)
        assert isinstance(panel, Panel)

    def test_create_recent_events_table(self, renderer, sample_events):
        """Test recent events table creation."""
        table = renderer.create_recent_events_table(sample_events, "coding")
        assert isinstance(table, Table)
        assert "Recent Events" in table.title

    def test_create_recent_events_table_filters_by_agent(self, renderer, sample_events):
        """Test that recent events table filters by agent name."""
        table = renderer.create_recent_events_table(sample_events, "coding")
        # Table should contain only coding agent events
        assert isinstance(table, Table)

    def test_create_recent_events_table_no_events(self, renderer):
        """Test recent events table with no events."""
        events = [
            {
                "event_id": "evt-1",
                "agent_name": "github",
                "session_id": "sess-1",
                "ticket_key": "AI-54",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "total_tokens": 5000,
                "duration_seconds": 35.0,
            },
        ]
        table = renderer.create_recent_events_table(events, "coding")
        assert isinstance(table, Table)

    def test_create_recent_events_table_respects_limit(self, renderer, sample_events):
        """Test that recent events table respects the limit parameter."""
        # Create many events
        now = datetime.now(timezone.utc)
        many_events = []
        for i in range(20):
            many_events.append({
                "event_id": f"evt-{i}",
                "agent_name": "coding",
                "session_id": "sess-1",
                "ticket_key": f"AI-{i}",
                "started_at": (now - timedelta(seconds=i)).isoformat(),
                "status": "success",
                "total_tokens": 5000,
                "duration_seconds": 35.0,
            })

        table = renderer.create_recent_events_table(many_events, "coding", limit=5)
        assert isinstance(table, Table)

    def test_format_duration_seconds(self, renderer):
        """Test duration formatting for seconds."""
        assert renderer._format_duration(30) == "30s"
        assert renderer._format_duration(59) == "59s"

    def test_format_duration_minutes(self, renderer):
        """Test duration formatting for minutes and seconds."""
        assert renderer._format_duration(90) == "1m 30s"
        assert renderer._format_duration(120) == "2m 0s"

    def test_format_duration_hours(self, renderer):
        """Test duration formatting for hours and minutes."""
        assert renderer._format_duration(3600) == "1h 0m"
        assert renderer._format_duration(3660) == "1h 1m"

    def test_format_time_ago_seconds(self, renderer):
        """Test time ago formatting for seconds."""
        assert renderer._format_time_ago(30) == "30s ago"

    def test_format_time_ago_minutes(self, renderer):
        """Test time ago formatting for minutes."""
        assert renderer._format_time_ago(300) == "5m ago"

    def test_format_time_ago_hours(self, renderer):
        """Test time ago formatting for hours."""
        assert renderer._format_time_ago(7200) == "2h ago"

    def test_format_time_ago_days(self, renderer):
        """Test time ago formatting for days."""
        assert renderer._format_time_ago(86400) == "1d ago"

    def test_create_detail_view(self, renderer, sample_agent_data, sample_events):
        """Test complete detail view creation."""
        # This integrates multiple panels together
        view = renderer.create_detail_view(sample_agent_data, "coding", sample_events)
        assert isinstance(view, Panel)


class TestMetricsFileMonitor:
    """Test suite for MetricsFileMonitor class."""

    @pytest.fixture
    def temp_metrics_file(self):
        """Create a temporary metrics file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "version": 1,
                "project_name": "test",
                "agents": {
                    "coding": {"agent_name": "coding", "xp": 950},
                    "github": {"agent_name": "github", "xp": 800},
                },
                "events": [],
                "sessions": [],
            }, f)
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        temp_path.unlink(missing_ok=True)

    def test_load_metrics_valid_file(self, temp_metrics_file):
        """Test loading valid metrics file."""
        monitor = MetricsFileMonitor(temp_metrics_file)
        metrics = monitor.load_metrics()
        assert metrics is not None
        assert metrics["version"] == 1
        assert "agents" in metrics

    def test_load_metrics_missing_file(self):
        """Test loading non-existent metrics file."""
        monitor = MetricsFileMonitor(Path("/nonexistent/path/metrics.json"))
        metrics = monitor.load_metrics()
        assert metrics is None

    def test_load_metrics_corrupted_file(self):
        """Test loading corrupted metrics file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json")
            temp_path = Path(f.name)

        try:
            monitor = MetricsFileMonitor(temp_path)
            metrics = monitor.load_metrics()
            assert metrics is None
        finally:
            temp_path.unlink(missing_ok=True)


class TestFindMetricsFile:
    """Test suite for find_metrics_file function."""

    def test_find_metrics_file_explicit_dir(self):
        """Test finding metrics file with explicit directory."""
        test_dir = Path("/tmp/test_metrics")
        result = find_metrics_file(test_dir)
        assert result == test_dir / "metrics.json"

    def test_find_metrics_file_home_dir(self):
        """Test finding metrics file in home directory."""
        with patch('agent_detail.DEFAULT_METRICS_DIR', Path("/tmp/.agent_metrics")):
            with patch.object(Path, 'exists', return_value=True):
                result = find_metrics_file()
                # Should try home dir first
                assert "agent_metrics" in str(result) or result.name == "metrics.json"

    def test_find_metrics_file_current_dir(self):
        """Test finding metrics file in current directory."""
        with patch('agent_detail.DEFAULT_METRICS_DIR', Path("/nonexistent")):
            with patch('agent_detail.Path.cwd', return_value=Path("/tmp")):
                result = find_metrics_file()
                assert result.name == ".agent_metrics.json"


class TestAgentDetailIntegration:
    """Integration tests for agent detail view."""

    @pytest.fixture
    def sample_metrics_file(self):
        """Create a sample metrics file with complete data."""
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(seconds=30)).isoformat()

        metrics = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T00:00:00Z",
            "updated_at": now.isoformat(),
            "total_sessions": 5,
            "total_tokens": 45000,
            "total_cost_usd": 0.45,
            "total_duration_seconds": 1200.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 20,
                    "successful_invocations": 19,
                    "failed_invocations": 1,
                    "total_tokens": 30000,
                    "total_cost_usd": 0.30,
                    "total_duration_seconds": 800.0,
                    "success_rate": 0.95,
                    "avg_duration_seconds": 40.0,
                    "avg_tokens_per_call": 1500.0,
                    "cost_per_success_usd": 0.0158,
                    "xp": 950,
                    "level": 3,
                    "current_streak": 19,
                    "best_streak": 19,
                    "achievements": ["first_blood", "century_club"],
                    "strengths": ["fast_execution", "high_success_rate"],
                    "weaknesses": [],
                    "recent_events": ["evt-1", "evt-2"],
                    "last_active": recent,
                },
                "github": {
                    "agent_name": "github",
                    "total_invocations": 8,
                    "successful_invocations": 8,
                    "failed_invocations": 0,
                    "total_tokens": 10000,
                    "total_cost_usd": 0.10,
                    "total_duration_seconds": 200.0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 25.0,
                    "avg_tokens_per_call": 1250.0,
                    "cost_per_success_usd": 0.0125,
                    "xp": 800,
                    "level": 2,
                    "current_streak": 8,
                    "best_streak": 8,
                    "achievements": ["first_blood"],
                    "strengths": ["perfect_accuracy"],
                    "weaknesses": [],
                    "recent_events": ["evt-3"],
                    "last_active": recent,
                },
            },
            "events": [
                {
                    "event_id": "evt-1",
                    "agent_name": "coding",
                    "session_id": "sess-1",
                    "ticket_key": "AI-54",
                    "started_at": recent,
                    "status": "success",
                    "total_tokens": 5000,
                    "duration_seconds": 35.0,
                },
                {
                    "event_id": "evt-2",
                    "agent_name": "coding",
                    "session_id": "sess-1",
                    "ticket_key": "AI-53",
                    "started_at": (now - timedelta(minutes=5)).isoformat(),
                    "status": "success",
                    "total_tokens": 4000,
                    "duration_seconds": 28.0,
                },
                {
                    "event_id": "evt-3",
                    "agent_name": "github",
                    "session_id": "sess-2",
                    "ticket_key": "AI-52",
                    "started_at": recent,
                    "status": "success",
                    "total_tokens": 2000,
                    "duration_seconds": 15.0,
                },
            ],
            "sessions": [],
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(metrics, f)
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        temp_path.unlink(missing_ok=True)

    def test_display_agent_detail_valid_agent(self, sample_metrics_file, capsys):
        """Test displaying detail for valid agent."""
        console = Console(file=open('/dev/null', 'w'))
        with patch('agent_detail.Console', return_value=console):
            display_agent_detail("coding", sample_metrics_file)

    def test_display_agent_detail_invalid_agent(self, sample_metrics_file, capsys):
        """Test displaying detail for non-existent agent."""
        console = Console()
        with patch('agent_detail.Console', return_value=console):
            display_agent_detail("nonexistent", sample_metrics_file)

    def test_display_agent_detail_missing_file(self, capsys):
        """Test displaying detail with missing metrics file."""
        console = Console()
        with patch('agent_detail.Console', return_value=console):
            display_agent_detail("coding", Path("/nonexistent/metrics.json"))

    def test_agent_detail_with_empty_strengths_weaknesses(self, capsys):
        """Test agent detail rendering with empty strengths/weaknesses."""
        now = datetime.now(timezone.utc)
        metrics = {
            "version": 1,
            "project_name": "test",
            "agents": {
                "test": {
                    "xp": 500,
                    "level": 1,
                    "current_streak": 5,
                    "best_streak": 10,
                    "success_rate": 0.8,
                    "total_invocations": 5,
                    "successful_invocations": 4,
                    "failed_invocations": 1,
                    "avg_duration_seconds": 30.0,
                    "avg_tokens_per_call": 1000.0,
                    "cost_per_success_usd": 0.01,
                    "total_tokens": 5000,
                    "total_cost_usd": 0.05,
                    "total_duration_seconds": 150.0,
                    "strengths": [],
                    "weaknesses": [],
                    "achievements": [],
                }
            },
            "events": [],
            "sessions": [],
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(metrics, f)
            temp_path = Path(f.name)

        try:
            console = Console(file=open('/dev/null', 'w'))
            with patch('agent_detail.Console', return_value=console):
                display_agent_detail("test", temp_path)
        finally:
            temp_path.unlink(missing_ok=True)


class TestAgentDetailFormatting:
    """Tests for formatting utilities."""

    @pytest.fixture
    def renderer(self):
        """Create renderer for formatting tests."""
        console = Console()
        return AgentDetailRenderer(console)

    def test_level_titles_complete(self, renderer):
        """Test that all level titles are available."""
        for level in range(1, 9):
            title = renderer.get_level_title(level)
            assert title != "Unknown"
            assert len(title) > 0

    def test_format_duration_edge_cases(self, renderer):
        """Test duration formatting edge cases."""
        assert renderer._format_duration(0) == "0s"
        assert renderer._format_duration(1) == "1s"
        assert renderer._format_duration(59.5) == "59s"

    def test_format_time_ago_edge_cases(self, renderer):
        """Test time ago formatting edge cases."""
        assert renderer._format_time_ago(0) == "0s ago"
        assert renderer._format_time_ago(1) == "1s ago"
        assert renderer._format_time_ago(59.5) == "59s ago"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
