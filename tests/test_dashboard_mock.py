#!/usr/bin/env python3
"""Mock-based tests for dashboard that don't require rich library.

These tests verify the dashboard logic without requiring the rich library
to be installed. They use mocking to simulate the rich components.
"""

import json
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
import sys

import pytest

# Mock the rich library before importing dashboard
sys.modules['rich'] = MagicMock()
sys.modules['rich.console'] = MagicMock()
sys.modules['rich.layout'] = MagicMock()
sys.modules['rich.live'] = MagicMock()
sys.modules['rich.panel'] = MagicMock()
sys.modules['rich.table'] = MagicMock()
sys.modules['rich.text'] = MagicMock()

# Now we can import dashboard
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from dashboard import (
    DashboardRenderer,
    MetricsFileMonitor,
    find_metrics_file,
)


class TestMetricsFileMonitorMocked:
    """Test suite for MetricsFileMonitor without requiring rich."""

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


class TestFindMetricsFileMocked:
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


class TestDashboardRendererMocked:
    """Test dashboard renderer with mocked rich components."""

    @pytest.fixture
    def mock_console(self):
        """Create a mock console."""
        return Mock()

    @pytest.fixture
    def renderer(self, mock_console):
        """Create renderer with mock console."""
        return DashboardRenderer(mock_console)

    @pytest.fixture
    def sample_state(self):
        """Create a sample DashboardState for testing."""
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(seconds=30)).isoformat()

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
                },
            },
            "events": [
                {
                    "event_id": "evt-1",
                    "agent_name": "coding",
                    "ticket_key": "AI-100",
                    "status": "success",
                    "started_at": recent,
                },
            ],
            "sessions": [],
        }

    def test_renderer_initialization(self, mock_console):
        """Test that renderer can be initialized."""
        renderer = DashboardRenderer(mock_console)
        assert renderer.console == mock_console

    def test_create_agent_status_table(self, renderer, sample_state):
        """Test creating agent status table."""
        # This will create a mocked Table object
        table = renderer.create_agent_status_table(
            sample_state["agents"],
            sample_state["events"]
        )
        # Verify it returns something
        assert table is not None

    def test_create_metrics_panel(self, renderer, sample_state):
        """Test creating metrics panel."""
        panel = renderer.create_metrics_panel(sample_state)
        assert panel is not None

    def test_create_project_header(self, renderer, sample_state):
        """Test creating project header."""
        panel = renderer.create_project_header(sample_state)
        assert panel is not None

    def test_create_initializing_layout(self, renderer):
        """Test creating initializing layout."""
        layout = renderer.create_initializing_layout()
        assert layout is not None

    def test_create_dashboard_layout(self, renderer, sample_state):
        """Test creating complete dashboard layout."""
        layout = renderer.create_dashboard_layout(sample_state)
        assert layout is not None

    def test_format_time_ago_seconds(self, renderer):
        """Test formatting time ago for seconds."""
        assert renderer._format_time_ago(30) == "30s ago"
        assert renderer._format_time_ago(59) == "59s ago"

    def test_format_time_ago_minutes(self, renderer):
        """Test formatting time ago for minutes."""
        assert renderer._format_time_ago(60) == "1m ago"
        assert renderer._format_time_ago(300) == "5m ago"

    def test_format_time_ago_hours(self, renderer):
        """Test formatting time ago for hours."""
        assert renderer._format_time_ago(3600) == "1h ago"
        assert renderer._format_time_ago(7200) == "2h ago"

    def test_format_time_ago_days(self, renderer):
        """Test formatting time ago for days."""
        assert renderer._format_time_ago(86400) == "1d ago"
        assert renderer._format_time_ago(172800) == "2d ago"


class TestDashboardIntegrationMocked:
    """Integration tests with mocked rich components."""

    def test_dashboard_with_valid_metrics(self):
        """Test dashboard can load and process valid metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_file = Path(tmpdir) / "metrics.json"
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
                        "success_rate": 1.0,
                        "last_active": datetime.now(timezone.utc).isoformat(),
                    }
                },
                "events": [],
                "sessions": [],
            }

            with open(metrics_file, 'w') as f:
                json.dump(sample_data, f)

            monitor = MetricsFileMonitor(metrics_file)
            state = monitor.load_metrics()

            assert state is not None
            assert state["project_name"] == "integration-test"
            assert state["total_tokens"] == 10000

    def test_dashboard_with_missing_metrics(self):
        """Test dashboard handles missing metrics gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_file = Path(tmpdir) / "nonexistent.json"
            monitor = MetricsFileMonitor(metrics_file)
            state = monitor.load_metrics()

            assert state is None

    def test_dashboard_handles_empty_state(self):
        """Test dashboard handles empty state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_file = Path(tmpdir) / "metrics.json"
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

            monitor = MetricsFileMonitor(metrics_file)
            state = monitor.load_metrics()

            assert state is not None
            assert len(state["agents"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
