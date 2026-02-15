#!/usr/bin/env python3
"""Comprehensive unit tests for the agent status dashboard.

Tests all components of the dashboard including:
- Dashboard rendering logic
- Metrics file monitoring
- Graceful handling of missing/corrupt files
- Layout generation
- Time formatting utilities
"""

import json
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

# Add parent directory to path to import dashboard module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dashboard import (
    DashboardRenderer,
    MetricsFileMonitor,
    find_metrics_file,
    DEFAULT_METRICS_DIR,
)


class TestDashboardRenderer:
    """Test suite for DashboardRenderer class."""

    @pytest.fixture
    def console(self):
        """Create a Rich console instance for testing."""
        return Console()

    @pytest.fixture
    def renderer(self, console):
        """Create a DashboardRenderer instance for testing."""
        return DashboardRenderer(console)

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
                    "success_rate": 0.9,
                    "last_active": recent,
                    "recent_events": ["evt-1", "evt-2"],
                },
                "github": {
                    "agent_name": "github",
                    "total_invocations": 5,
                    "successful_invocations": 5,
                    "failed_invocations": 0,
                    "success_rate": 1.0,
                    "last_active": old,
                    "recent_events": ["evt-3"],
                },
                "linear": {
                    "agent_name": "linear",
                    "total_invocations": 3,
                    "successful_invocations": 1,
                    "failed_invocations": 2,
                    "success_rate": 0.33,
                    "last_active": recent,
                    "recent_events": ["evt-4"],
                },
            },
            "events": [
                {
                    "event_id": "evt-1",
                    "agent_name": "coding",
                    "session_id": "sess-1",
                    "ticket_key": "AI-100",
                    "started_at": recent,
                    "ended_at": recent,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                },
                {
                    "event_id": "evt-2",
                    "agent_name": "coding",
                    "session_id": "sess-1",
                    "ticket_key": "AI-101",
                    "started_at": recent,
                    "ended_at": recent,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                },
                {
                    "event_id": "evt-3",
                    "agent_name": "github",
                    "session_id": "sess-1",
                    "ticket_key": "AI-100",
                    "started_at": old,
                    "ended_at": old,
                    "status": "success",
                    "input_tokens": 500,
                    "output_tokens": 500,
                    "total_tokens": 1000,
                },
                {
                    "event_id": "evt-4",
                    "agent_name": "linear",
                    "session_id": "sess-2",
                    "ticket_key": "AI-102",
                    "started_at": recent,
                    "ended_at": recent,
                    "status": "error",
                    "input_tokens": 200,
                    "output_tokens": 100,
                    "total_tokens": 300,
                },
            ],
            "sessions": [
                {
                    "session_id": "sess-1",
                    "session_number": 1,
                    "session_type": "initializer",
                    "started_at": recent,
                    "ended_at": recent,
                    "status": "complete",
                },
            ],
        }

    def test_create_agent_status_table_with_agents(self, renderer, sample_state):
        """Test creating agent status table with active agents."""
        table = renderer.create_agent_status_table(
            sample_state["agents"],
            sample_state["events"]
        )

        # Should have title and proper columns
        assert table.title == "Agent Status"
        assert len(table.columns) == 4

        # Should have rows for each agent
        assert len(table.rows) == 3

    def test_create_agent_status_table_empty(self, renderer):
        """Test creating agent status table with no agents."""
        table = renderer.create_agent_status_table({}, [])

        # Should have one row showing "No agents"
        assert len(table.rows) == 1
        assert "No agents" in str(table.rows[0])

    def test_create_metrics_panel(self, renderer, sample_state):
        """Test creating metrics panel with system metrics."""
        panel = renderer.create_metrics_panel(sample_state)

        # Panel should have title
        assert panel.title == "Dashboard Metrics"

        # Check that content contains expected elements
        content_str = str(panel.renderable)
        assert "Active Tasks:" in content_str
        assert "Recent Completions:" in content_str
        assert "System Load:" in content_str

    def test_create_metrics_panel_high_load(self, renderer, sample_state):
        """Test metrics panel shows high load indicator for many tokens."""
        sample_state["total_tokens"] = 60000
        panel = renderer.create_metrics_panel(sample_state)

        content_str = str(panel.renderable)
        assert "High" in content_str

    def test_create_metrics_panel_medium_load(self, renderer, sample_state):
        """Test metrics panel shows medium load indicator."""
        sample_state["total_tokens"] = 20000
        panel = renderer.create_metrics_panel(sample_state)

        content_str = str(panel.renderable)
        assert "Medium" in content_str

    def test_create_metrics_panel_low_load(self, renderer, sample_state):
        """Test metrics panel shows low load indicator for few tokens."""
        sample_state["total_tokens"] = 5000
        panel = renderer.create_metrics_panel(sample_state)

        content_str = str(panel.renderable)
        assert "Low" in content_str

    def test_create_metrics_panel_recent_completions(self, renderer, sample_state):
        """Test that recent completions are properly shown."""
        panel = renderer.create_metrics_panel(sample_state)

        content_str = str(panel.renderable)
        # Should show successful events
        assert "coding: AI-100" in content_str or "coding: AI-101" in content_str

    def test_create_metrics_panel_no_completions(self, renderer):
        """Test metrics panel with no completions."""
        empty_state = {
            "agents": {},
            "events": [],
            "sessions": [],
            "total_sessions": 0,
            "total_tokens": 0,
        }
        panel = renderer.create_metrics_panel(empty_state)

        content_str = str(panel.renderable)
        assert "No completions yet" in content_str

    def test_create_project_header(self, renderer, sample_state):
        """Test creating project header."""
        panel = renderer.create_project_header(sample_state)

        # Check title and content
        assert panel.title == "Agent Status Dashboard"
        content_str = str(panel.renderable)
        assert "test-project" in content_str
        assert "Last Updated:" in content_str

    def test_create_project_header_no_update_time(self, renderer):
        """Test project header with missing update time."""
        state = {
            "project_name": "test-project",
            "updated_at": "",
        }
        panel = renderer.create_project_header(state)

        content_str = str(panel.renderable)
        assert "Never" in content_str

    def test_create_initializing_layout(self, renderer):
        """Test creating initializing layout."""
        layout = renderer.create_initializing_layout()

        # Layout should contain initializing message
        # Note: We can't easily test the exact content of Layout,
        # but we can verify it returns a Layout object
        assert layout is not None

    def test_create_dashboard_layout(self, renderer, sample_state):
        """Test creating complete dashboard layout."""
        layout = renderer.create_dashboard_layout(sample_state)

        # Verify layout structure
        assert layout is not None
        assert "header" in layout
        assert "body" in layout

    def test_format_time_ago_seconds(self, renderer):
        """Test formatting time ago for seconds."""
        assert renderer._format_time_ago(30) == "30s ago"
        assert renderer._format_time_ago(59) == "59s ago"

    def test_format_time_ago_minutes(self, renderer):
        """Test formatting time ago for minutes."""
        assert renderer._format_time_ago(60) == "1m ago"
        assert renderer._format_time_ago(300) == "5m ago"
        assert renderer._format_time_ago(3599) == "59m ago"

    def test_format_time_ago_hours(self, renderer):
        """Test formatting time ago for hours."""
        assert renderer._format_time_ago(3600) == "1h ago"
        assert renderer._format_time_ago(7200) == "2h ago"
        assert renderer._format_time_ago(86399) == "23h ago"

    def test_format_time_ago_days(self, renderer):
        """Test formatting time ago for days."""
        assert renderer._format_time_ago(86400) == "1d ago"
        assert renderer._format_time_ago(172800) == "2d ago"


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

    def test_find_metrics_file_prefers_existing(self):
        """Test that find_metrics_file prefers existing file in home directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a metrics file in a temp location
            temp_home = Path(tmpdir) / ".agent_metrics"
            temp_home.mkdir()
            temp_metrics = temp_home / "metrics.json"
            temp_metrics.write_text('{"version": 1}')

            # Mock DEFAULT_METRICS_DIR
            with patch('dashboard.DEFAULT_METRICS_DIR', temp_home):
                result = find_metrics_file()

                # Should find the existing file
                assert result == temp_metrics


class TestDashboardIntegration:
    """Integration tests for the dashboard."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_dashboard_with_valid_metrics(self, temp_dir):
        """Test dashboard rendering with valid metrics file."""
        # Create metrics file
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
                    "success_rate": 1.0,
                    "last_active": datetime.now(timezone.utc).isoformat(),
                }
            },
            "events": [
                {
                    "event_id": "evt-1",
                    "agent_name": "coding",
                    "session_id": "sess-1",
                    "ticket_key": "AI-200",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                }
            ],
            "sessions": [],
        }

        with open(metrics_file, 'w') as f:
            json.dump(sample_data, f)

        # Load and render
        console = Console()
        renderer = DashboardRenderer(console)
        monitor = MetricsFileMonitor(metrics_file)

        state = monitor.load_metrics()
        assert state is not None

        layout = renderer.create_dashboard_layout(state)
        assert layout is not None

    def test_dashboard_with_missing_metrics(self, temp_dir):
        """Test dashboard rendering with missing metrics file."""
        metrics_file = temp_dir / "nonexistent.json"

        console = Console()
        renderer = DashboardRenderer(console)
        monitor = MetricsFileMonitor(metrics_file)

        state = monitor.load_metrics()
        assert state is None

        # Should show initializing layout
        layout = renderer.create_initializing_layout()
        assert layout is not None

    def test_dashboard_handles_empty_agents(self, temp_dir):
        """Test dashboard gracefully handles empty agents dictionary."""
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
        renderer = DashboardRenderer(console)
        monitor = MetricsFileMonitor(metrics_file)

        state = monitor.load_metrics()
        assert state is not None

        # Should render without errors
        table = renderer.create_agent_status_table(state["agents"], state["events"])
        assert len(table.rows) == 1  # "No agents" row


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=dashboard", "--cov-report=term-missing"])
