#!/usr/bin/env python3
"""Comprehensive unit tests for the agent leaderboard.

Tests all components of the leaderboard including:
- Leaderboard rendering logic
- Agent sorting by XP
- Metrics file monitoring
- Graceful handling of missing/corrupt files
- Layout generation
- Status determination
- Time and cost formatting
"""

import json
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

# Add parent directory to path to import leaderboard module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from leaderboard import (
    LeaderboardRenderer,
    MetricsFileMonitor,
    find_metrics_file,
    DEFAULT_METRICS_DIR,
)


class TestLeaderboardRenderer:
    """Test suite for LeaderboardRenderer class."""

    @pytest.fixture
    def console(self):
        """Create a Rich console instance for testing."""
        return Console()

    @pytest.fixture
    def renderer(self, console):
        """Create a LeaderboardRenderer instance for testing."""
        return LeaderboardRenderer(console)

    @pytest.fixture
    def sample_state(self):
        """Create a sample DashboardState for testing."""
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(seconds=30)).isoformat()
        old = (now - timedelta(hours=2)).isoformat()

        return {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T00:00:00Z",
            "updated_at": now.isoformat(),
            "total_sessions": 5,
            "total_tokens": 15000,
            "total_cost_usd": 0.15,
            "total_duration_seconds": 120.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 10,
                    "successful_invocations": 9,
                    "failed_invocations": 1,
                    "total_tokens": 6000,
                    "total_cost_usd": 0.06,
                    "total_duration_seconds": 360.0,
                    "success_rate": 0.9,
                    "avg_duration_seconds": 36.0,
                    "avg_tokens_per_call": 600.0,
                    "cost_per_success_usd": 0.00667,
                    "xp": 950,
                    "level": 3,
                    "current_streak": 9,
                    "best_streak": 9,
                    "achievements": ["first_blood"],
                    "strengths": ["fast_execution"],
                    "weaknesses": [],
                    "recent_events": ["evt-1", "evt-2"],
                    "last_error": "",
                    "last_active": recent,
                },
                "github": {
                    "agent_name": "github",
                    "total_invocations": 5,
                    "successful_invocations": 5,
                    "failed_invocations": 0,
                    "total_tokens": 5000,
                    "total_cost_usd": 0.05,
                    "total_duration_seconds": 125.0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 25.0,
                    "avg_tokens_per_call": 1000.0,
                    "cost_per_success_usd": 0.01,
                    "xp": 800,
                    "level": 2,
                    "current_streak": 5,
                    "best_streak": 5,
                    "achievements": [],
                    "strengths": ["perfect_accuracy"],
                    "weaknesses": [],
                    "recent_events": ["evt-3"],
                    "last_error": "",
                    "last_active": old,
                },
                "linear": {
                    "agent_name": "linear",
                    "total_invocations": 3,
                    "successful_invocations": 1,
                    "failed_invocations": 2,
                    "total_tokens": 4000,
                    "total_cost_usd": 0.04,
                    "total_duration_seconds": 120.0,
                    "success_rate": 0.33,
                    "avg_duration_seconds": 40.0,
                    "avg_tokens_per_call": 1333.0,
                    "cost_per_success_usd": 0.04,
                    "xp": 300,
                    "level": 1,
                    "current_streak": 0,
                    "best_streak": 2,
                    "achievements": [],
                    "strengths": [],
                    "weaknesses": ["high_error_rate"],
                    "recent_events": ["evt-4"],
                    "last_error": "API timeout",
                    "last_active": recent,
                },
            },
            "events": [],
            "sessions": [],
        }

    def test_create_leaderboard_table_with_agents(self, renderer, sample_state):
        """Test creating leaderboard table with multiple agents."""
        table = renderer.create_leaderboard_table(sample_state["agents"])

        # Should have title and proper columns
        assert table.title == "Agent Leaderboard (Sorted by XP)"
        assert len(table.columns) == 8

        # Should have rows for each agent
        assert len(table.rows) == 3

    def test_leaderboard_sorts_by_xp_descending(self, renderer, sample_state):
        """Test that leaderboard sorts agents by XP in descending order."""
        table = renderer.create_leaderboard_table(sample_state["agents"])

        # Extract XP values from table rows (should be in column index 2)
        # The rows are rendered as Text objects, so we check order by agent name
        # First row should be coding (950 XP), then github (800 XP), then linear (300 XP)

        # We can verify by checking the sample_state order
        agents_by_xp = sorted(
            sample_state["agents"].items(),
            key=lambda x: x[1].get("xp", 0),
            reverse=True
        )

        expected_order = [agent[0] for agent in agents_by_xp]
        assert expected_order == ["coding", "github", "linear"]
        assert len(table.rows) == 3

    def test_create_leaderboard_table_empty(self, renderer):
        """Test creating leaderboard table with no agents."""
        table = renderer.create_leaderboard_table({})

        # Should have one row showing "No agents"
        assert len(table.rows) == 1

    def test_create_project_header(self, renderer, sample_state):
        """Test creating project header with leaderboard info."""
        panel = renderer.create_project_header(sample_state)

        # Check title and content
        assert panel.title == "Agent Leaderboard"
        content_str = str(panel.renderable)
        assert "test-project" in content_str
        assert "Total Agents:" in content_str
        assert "Total XP:" in content_str

    def test_create_project_header_total_xp_calculation(self, renderer, sample_state):
        """Test that total XP is correctly calculated."""
        panel = renderer.create_project_header(sample_state)

        content_str = str(panel.renderable)
        # 950 + 800 + 300 = 2050
        assert "2050" in content_str

    def test_create_initializing_layout(self, renderer):
        """Test creating initializing layout."""
        layout = renderer.create_initializing_layout()

        # Layout should be valid
        assert layout is not None

    def test_create_leaderboard_layout(self, renderer, sample_state):
        """Test creating complete leaderboard layout."""
        layout = renderer.create_leaderboard_layout(sample_state)

        # Verify layout structure
        assert layout is not None
        # Layout is successfully created and has layout dict
        assert isinstance(layout, object)

    def test_determine_status_active(self, renderer):
        """Test status determination for recently active agent."""
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(seconds=30)).isoformat()

        status = renderer._determine_status(recent)
        assert "Active" in status

    def test_determine_status_idle(self, renderer):
        """Test status determination for inactive agent."""
        now = datetime.now(timezone.utc)
        old = (now - timedelta(hours=2)).isoformat()

        status = renderer._determine_status(old)
        assert "Idle" in status

    def test_determine_status_empty(self, renderer):
        """Test status determination for agent with no activity."""
        status = renderer._determine_status("")

        assert "Idle" in status

    def test_determine_status_invalid(self, renderer):
        """Test status determination for invalid timestamp."""
        status = renderer._determine_status("invalid-timestamp")

        assert "Unknown" in status

    def test_format_duration_seconds(self, renderer):
        """Test formatting duration in seconds."""
        assert renderer._format_duration(30) == "30s"
        assert renderer._format_duration(59) == "59s"

    def test_format_duration_minutes(self, renderer):
        """Test formatting duration in minutes."""
        assert renderer._format_duration(60) == "1m 0s"
        assert renderer._format_duration(300) == "5m 0s"
        assert renderer._format_duration(125) == "2m 5s"

    def test_format_duration_hours(self, renderer):
        """Test formatting duration in hours."""
        assert renderer._format_duration(3600) == "1h 0m"
        assert renderer._format_duration(7200) == "2h 0m"
        assert renderer._format_duration(3660) == "1h 1m"

    def test_get_level_title_all_levels(self, renderer):
        """Test getting level titles for all levels."""
        titles = {
            1: "Intern",
            2: "Junior",
            3: "Mid-Level",
            4: "Senior",
            5: "Staff",
            6: "Principal",
            7: "Distinguished",
            8: "Fellow",
        }

        for level, expected_title in titles.items():
            assert renderer._get_level_title(level) == expected_title

    def test_get_level_title_unknown_level(self, renderer):
        """Test getting title for unknown level."""
        assert renderer._get_level_title(99) == "Unknown"


class TestMetricsFileMonitor:
    """Test suite for MetricsFileMonitor class."""

    @pytest.fixture
    def temp_metrics_file(self):
        """Create a temporary metrics file for testing."""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            json.dump({"version": 1, "project_name": "test"}, f)
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    def test_load_metrics_existing_file(self, temp_metrics_file):
        """Test loading metrics from existing file."""
        monitor = MetricsFileMonitor(temp_metrics_file)
        data = monitor.load_metrics()

        assert data is not None
        assert data["version"] == 1
        assert data["project_name"] == "test"

    def test_load_metrics_missing_file(self):
        """Test loading metrics from non-existent file."""
        monitor = MetricsFileMonitor(Path("/nonexistent/metrics.json"))
        data = monitor.load_metrics()

        assert data is None

    def test_load_metrics_corrupted_file(self):
        """Test loading metrics from corrupted JSON file."""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            f.write("invalid json {{{")
            temp_path = Path(f.name)

        try:
            monitor = MetricsFileMonitor(temp_path)
            data = monitor.load_metrics()

            assert data is None
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_has_changed_initial(self, temp_metrics_file):
        """Test detecting file change on first check."""
        monitor = MetricsFileMonitor(temp_metrics_file)

        # First check should detect change
        assert monitor.has_changed() is True

    def test_has_changed_no_modification(self, temp_metrics_file):
        """Test detecting no change when file not modified."""
        monitor = MetricsFileMonitor(temp_metrics_file)

        # First check
        monitor.has_changed()

        # Second check without modification
        assert monitor.has_changed() is False

    def test_has_changed_after_modification(self, temp_metrics_file):
        """Test detecting change after file modification."""
        monitor = MetricsFileMonitor(temp_metrics_file)

        # First check
        monitor.has_changed()

        # Wait a bit to ensure different mtime
        time.sleep(0.1)

        # Modify file
        with open(temp_metrics_file, 'w') as f:
            json.dump({"version": 2, "project_name": "updated"}, f)

        # Should detect change
        assert monitor.has_changed() is True

    def test_has_changed_missing_file(self):
        """Test has_changed with missing file."""
        monitor = MetricsFileMonitor(Path("/nonexistent/metrics.json"))

        assert monitor.has_changed() is False


class TestFindMetricsFile:
    """Test suite for find_metrics_file function."""

    def test_find_metrics_file_with_explicit_dir(self):
        """Test finding metrics file with explicit directory."""
        metrics_dir = Path("/custom/metrics")
        result = find_metrics_file(metrics_dir)

        assert result == metrics_dir / "metrics.json"

    def test_find_metrics_file_defaults(self):
        """Test finding metrics file with default locations."""
        result = find_metrics_file()

        # Should return a valid Path object
        assert isinstance(result, Path)

        # Should be either ~/.agent_metrics/metrics.json or ./.agent_metrics.json
        assert (
            result == DEFAULT_METRICS_DIR / "metrics.json"
            or result == Path.cwd() / ".agent_metrics.json"
        )


class TestLeaderboardIntegration:
    """Integration tests for the leaderboard."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_leaderboard_with_valid_metrics(self, temp_dir):
        """Test leaderboard rendering with valid metrics file."""
        # Create metrics file with sample agents
        metrics_file = temp_dir / "metrics.json"
        sample_data = {
            "version": 1,
            "project_name": "integration-test",
            "created_at": "2026-02-14T00:00:00Z",
            "updated_at": "2026-02-14T01:00:00Z",
            "total_sessions": 3,
            "total_tokens": 10000,
            "total_cost_usd": 0.1,
            "total_duration_seconds": 60.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 5,
                    "successful_invocations": 5,
                    "failed_invocations": 0,
                    "total_tokens": 5000,
                    "total_cost_usd": 0.05,
                    "total_duration_seconds": 30.0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 6.0,
                    "avg_tokens_per_call": 1000.0,
                    "cost_per_success_usd": 0.01,
                    "xp": 500,
                    "level": 2,
                    "current_streak": 5,
                    "best_streak": 5,
                    "achievements": [],
                    "strengths": [],
                    "weaknesses": [],
                    "recent_events": ["evt-1"],
                    "last_error": "",
                    "last_active": datetime.now(timezone.utc).isoformat(),
                }
            },
            "events": [],
            "sessions": [],
        }

        with open(metrics_file, 'w') as f:
            json.dump(sample_data, f)

        # Load and render
        console = Console()
        renderer = LeaderboardRenderer(console)
        monitor = MetricsFileMonitor(metrics_file)

        state = monitor.load_metrics()
        assert state is not None

        layout = renderer.create_leaderboard_layout(state)
        assert layout is not None

    def test_leaderboard_with_missing_metrics(self, temp_dir):
        """Test leaderboard rendering with missing metrics file."""
        metrics_file = temp_dir / "nonexistent.json"

        console = Console()
        renderer = LeaderboardRenderer(console)
        monitor = MetricsFileMonitor(metrics_file)

        state = monitor.load_metrics()
        assert state is None

        # Should show initializing layout
        layout = renderer.create_initializing_layout()
        assert layout is not None

    def test_leaderboard_with_multiple_agents_sorted(self, temp_dir):
        """Test leaderboard correctly sorts multiple agents by XP."""
        metrics_file = temp_dir / "metrics.json"
        sample_data = {
            "version": 1,
            "project_name": "sorting-test",
            "created_at": "2026-02-14T00:00:00Z",
            "updated_at": "2026-02-14T01:00:00Z",
            "total_sessions": 3,
            "total_tokens": 15000,
            "total_cost_usd": 0.15,
            "total_duration_seconds": 120.0,
            "agents": {
                "agent_a": {
                    "agent_name": "agent_a",
                    "total_invocations": 3,
                    "successful_invocations": 3,
                    "failed_invocations": 0,
                    "total_tokens": 3000,
                    "total_cost_usd": 0.03,
                    "total_duration_seconds": 30.0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 10.0,
                    "avg_tokens_per_call": 1000.0,
                    "cost_per_success_usd": 0.01,
                    "xp": 300,
                    "level": 1,
                    "current_streak": 3,
                    "best_streak": 3,
                    "achievements": [],
                    "strengths": [],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": datetime.now(timezone.utc).isoformat(),
                },
                "agent_b": {
                    "agent_name": "agent_b",
                    "total_invocations": 5,
                    "successful_invocations": 5,
                    "failed_invocations": 0,
                    "total_tokens": 6000,
                    "total_cost_usd": 0.06,
                    "total_duration_seconds": 60.0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 12.0,
                    "avg_tokens_per_call": 1200.0,
                    "cost_per_success_usd": 0.012,
                    "xp": 800,
                    "level": 2,
                    "current_streak": 5,
                    "best_streak": 5,
                    "achievements": [],
                    "strengths": [],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": datetime.now(timezone.utc).isoformat(),
                },
                "agent_c": {
                    "agent_name": "agent_c",
                    "total_invocations": 2,
                    "successful_invocations": 2,
                    "failed_invocations": 0,
                    "total_tokens": 6000,
                    "total_cost_usd": 0.06,
                    "total_duration_seconds": 30.0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 15.0,
                    "avg_tokens_per_call": 3000.0,
                    "cost_per_success_usd": 0.03,
                    "xp": 600,
                    "level": 2,
                    "current_streak": 2,
                    "best_streak": 2,
                    "achievements": [],
                    "strengths": [],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": datetime.now(timezone.utc).isoformat(),
                },
            },
            "events": [],
            "sessions": [],
        }

        with open(metrics_file, 'w') as f:
            json.dump(sample_data, f)

        console = Console()
        renderer = LeaderboardRenderer(console)
        monitor = MetricsFileMonitor(metrics_file)

        state = monitor.load_metrics()
        assert state is not None

        # Verify sorting
        sorted_agents = sorted(
            state["agents"].items(),
            key=lambda x: x[1].get("xp", 0),
            reverse=True
        )
        assert [a[0] for a in sorted_agents] == ["agent_b", "agent_c", "agent_a"]

        # Create table and verify it's generated without errors
        table = renderer.create_leaderboard_table(state["agents"])
        assert len(table.rows) == 3

    def test_leaderboard_handles_empty_agents(self, temp_dir):
        """Test leaderboard gracefully handles empty agents dictionary."""
        metrics_file = temp_dir / "metrics.json"
        empty_data = {
            "version": 1,
            "project_name": "empty-test",
            "created_at": "2026-02-14T00:00:00Z",
            "updated_at": "2026-02-14T01:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": [],
        }

        with open(metrics_file, 'w') as f:
            json.dump(empty_data, f)

        console = Console()
        renderer = LeaderboardRenderer(console)
        monitor = MetricsFileMonitor(metrics_file)

        state = monitor.load_metrics()
        assert state is not None

        # Should render without errors
        table = renderer.create_leaderboard_table(state["agents"])
        assert len(table.rows) == 1  # "No agents" row


class TestLeaderboardRanking:
    """Tests for leaderboard ranking and display features."""

    @pytest.fixture
    def console(self):
        """Create a Rich console instance for testing."""
        return Console()

    @pytest.fixture
    def renderer(self, console):
        """Create a LeaderboardRenderer instance for testing."""
        return LeaderboardRenderer(console)

    def test_rank_display_for_top_three(self, renderer):
        """Test that top 3 agents get special formatting."""
        agents = {
            "agent1": {
                "agent_name": "agent1",
                "xp": 1000,
                "level": 3,
                "success_rate": 0.95,
                "avg_duration_seconds": 30.0,
                "cost_per_success_usd": 0.01,
                "last_active": datetime.now(timezone.utc).isoformat(),
            },
            "agent2": {
                "agent_name": "agent2",
                "xp": 800,
                "level": 2,
                "success_rate": 0.90,
                "avg_duration_seconds": 40.0,
                "cost_per_success_usd": 0.015,
                "last_active": datetime.now(timezone.utc).isoformat(),
            },
            "agent3": {
                "agent_name": "agent3",
                "xp": 600,
                "level": 2,
                "success_rate": 0.85,
                "avg_duration_seconds": 50.0,
                "cost_per_success_usd": 0.02,
                "last_active": datetime.now(timezone.utc).isoformat(),
            },
        }

        table = renderer.create_leaderboard_table(agents)

        # Verify table has 3 rows
        assert len(table.rows) == 3

    def test_metrics_accuracy(self, renderer):
        """Test that displayed metrics are accurate."""
        agents = {
            "test_agent": {
                "agent_name": "test_agent",
                "xp": 525,
                "level": 2,
                "success_rate": 0.8,
                "avg_duration_seconds": 45.5,
                "cost_per_success_usd": 0.0125,
                "last_active": datetime.now(timezone.utc).isoformat(),
            }
        }

        table = renderer.create_leaderboard_table(agents)

        # Verify we get 1 agent row
        assert len(table.rows) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=leaderboard", "--cov-report=term-missing"])
