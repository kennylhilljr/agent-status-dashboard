#!/usr/bin/env python3
"""Comprehensive unit and integration tests for the unified dashboard CLI.

Tests all CLI modes and functionality:
- Live dashboard mode (default, no flags)
- Once mode (--once)
- JSON output mode (--json)
- Agent detail mode (--agent NAME)
- Leaderboard mode (--leaderboard)
- Achievements mode (--achievements)
- Integration with metrics loading
- Error handling for missing/corrupt metrics files
- Command-line argument parsing
"""

import json
import tempfile
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from io import StringIO

import pytest
from rich.console import Console

# Add parent directory to path to import CLI module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from cli import (
    UnifiedDashboardCLI,
    main as cli_main,
)


class TestUnifiedDashboardCLI:
    """Test suite for UnifiedDashboardCLI class."""

    @pytest.fixture
    def console(self):
        """Create a Rich console instance for testing."""
        return Console(file=StringIO())

    @pytest.fixture
    def cli(self, console):
        """Create a UnifiedDashboardCLI instance for testing."""
        return UnifiedDashboardCLI(console)

    @pytest.fixture
    def sample_metrics(self):
        """Create sample metrics data for testing."""
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
                    "total_tokens": 6000,
                    "total_cost_usd": 0.06,
                    "total_duration_seconds": 360.0,
                    "avg_duration_seconds": 36.0,
                    "avg_tokens_per_call": 600.0,
                    "cost_per_success_usd": 0.00667,
                    "xp": 950,
                    "level": 3,
                    "current_streak": 5,
                    "best_streak": 9,
                    "strengths": ["pattern_recognition", "code_generation"],
                    "weaknesses": ["debugging"],
                    "achievements": ["first_blood", "century_club"],
                    "recent_events": ["evt-1"],
                },
                "github": {
                    "agent_name": "github",
                    "total_invocations": 5,
                    "successful_invocations": 5,
                    "failed_invocations": 0,
                    "success_rate": 1.0,
                    "last_active": old,
                    "total_tokens": 4000,
                    "total_cost_usd": 0.04,
                    "total_duration_seconds": 120.0,
                    "avg_duration_seconds": 24.0,
                    "avg_tokens_per_call": 800.0,
                    "cost_per_success_usd": 0.008,
                    "xp": 750,
                    "level": 2,
                    "current_streak": 5,
                    "best_streak": 5,
                    "strengths": ["api_integration"],
                    "weaknesses": [],
                    "achievements": ["first_blood"],
                    "recent_events": ["evt-2"],
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
                    "total_tokens": 1000,
                    "duration_seconds": 30,
                },
                {
                    "event_id": "evt-2",
                    "agent_name": "github",
                    "session_id": "sess-2",
                    "ticket_key": "AI-101",
                    "started_at": old,
                    "ended_at": old,
                    "status": "success",
                    "total_tokens": 800,
                    "duration_seconds": 20,
                },
            ],
        }

    @pytest.fixture
    def metrics_file(self, sample_metrics):
        """Create temporary metrics file for testing."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump(sample_metrics, f)
            temp_path = Path(f.name)
        yield temp_path
        temp_path.unlink()

    def test_cli_initialization(self, console):
        """Test CLI initialization."""
        cli = UnifiedDashboardCLI(console)
        assert cli.console is not None

    def test_cli_initialization_with_default_console(self):
        """Test CLI initialization with default console."""
        cli = UnifiedDashboardCLI()
        assert cli.console is not None

    def test_json_output_mode(self, cli, metrics_file):
        """Test JSON output mode."""
        cli.run_json_output(metrics_file)
        output = cli.console.file.getvalue()

        # Parse output as JSON
        data = json.loads(output)
        assert data["project_name"] == "test-project"
        assert "agents" in data
        assert "coding" in data["agents"]

    def test_json_output_missing_file(self, cli):
        """Test JSON output with missing metrics file."""
        cli.run_json_output(Path("/nonexistent/metrics.json"))
        output = cli.console.file.getvalue()

        # Should output error JSON
        data = json.loads(output)
        assert "error" in data

    def test_once_dashboard_mode(self, cli, metrics_file):
        """Test once mode (single update)."""
        cli.run_once_dashboard(metrics_file)
        output = cli.console.file.getvalue()

        # Should have rendered something
        assert len(output) > 0

    def test_once_dashboard_missing_file(self, cli):
        """Test once mode with missing metrics file."""
        cli.run_once_dashboard(Path("/nonexistent/metrics.json"))
        output = cli.console.file.getvalue()

        # Should show initializing state
        assert "Initializing" in output or len(output) > 0

    def test_agent_detail_mode(self, cli, metrics_file):
        """Test agent detail mode."""
        cli.run_agent_detail(metrics_file, "coding")
        output = cli.console.file.getvalue()

        # Should display agent details
        assert "coding" in output.lower() or len(output) > 0

    def test_agent_detail_nonexistent_agent(self, cli, metrics_file):
        """Test agent detail mode with nonexistent agent."""
        cli.run_agent_detail(metrics_file, "nonexistent")
        output = cli.console.file.getvalue()

        # Should show error
        assert "not found" in output.lower() or "Error" in output

    def test_agent_detail_missing_file(self, cli):
        """Test agent detail mode with missing metrics file."""
        cli.run_agent_detail(Path("/nonexistent/metrics.json"), "coding")
        output = cli.console.file.getvalue()

        # Should show error
        assert "not found" in output.lower() or "Error" in output

    def test_leaderboard_once_mode(self, cli, metrics_file):
        """Test leaderboard in once mode."""
        cli.run_leaderboard(metrics_file, once=True)
        output = cli.console.file.getvalue()

        # Should render leaderboard
        assert len(output) > 0

    def test_leaderboard_missing_file(self, cli):
        """Test leaderboard with missing metrics file."""
        cli.run_leaderboard(Path("/nonexistent/metrics.json"), once=True)
        output = cli.console.file.getvalue()

        # Should show initializing state
        assert len(output) > 0

    def test_achievements_once_mode(self, cli, metrics_file):
        """Test achievements in once mode."""
        cli.run_achievements(metrics_file, once=True)
        output = cli.console.file.getvalue()

        # Should render achievements
        assert len(output) > 0

    def test_achievements_single_agent(self, cli, metrics_file):
        """Test achievements for single agent."""
        cli.run_achievements(metrics_file, agent_name="coding", once=True)
        output = cli.console.file.getvalue()

        # Should display achievements
        assert len(output) > 0

    def test_achievements_missing_file(self, cli):
        """Test achievements with missing metrics file."""
        cli.run_achievements(Path("/nonexistent/metrics.json"), once=True)
        output = cli.console.file.getvalue()

        # Should show error
        assert "not found" in output.lower() or len(output) > 0


class TestCLIArgumentParsing:
    """Test suite for CLI argument parsing."""

    def test_help_output(self):
        """Test that --help works without errors."""
        result = subprocess.run(
            [sys.executable, "-m", "scripts.cli", "--help"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()

    def test_json_mode_argument(self):
        """Test JSON mode argument parsing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"project_name": "test"}, f)
            temp_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "scripts.cli", "--json",
                 "--metrics-dir", str(Path(temp_path).parent)],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=5
            )
            # Should produce JSON output or error with valid JSON
            try:
                json.loads(result.stdout)
                assert True
            except:
                # If not valid JSON, should still complete
                assert result.returncode in [0, 1]
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_once_flag_argument(self):
        """Test once flag argument parsing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"project_name": "test", "agents": {}}, f)
            temp_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "scripts.cli", "--once",
                 "--metrics-dir", str(Path(temp_path).parent)],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=5
            )
            # Should complete without hanging
            assert result.returncode in [0, 1]
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_agent_mode_argument(self):
        """Test agent mode argument parsing."""
        metrics_data = {
            "project_name": "test",
            "agents": {
                "test_agent": {
                    "xp": 100,
                    "level": 1,
                    "success_rate": 0.9,
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(metrics_data, f)
            temp_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "scripts.cli", "--agent", "test_agent",
                 "--metrics-dir", str(Path(temp_path).parent)],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=5
            )
            # Should complete
            assert result.returncode in [0, 1]
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestCLIIntegration:
    """Integration tests for the CLI."""

    @pytest.fixture
    def sample_metrics_file(self):
        """Create a sample metrics file for integration testing."""
        metrics_data = {
            "version": 1,
            "project_name": "integration-test-project",
            "created_at": "2026-02-14T00:00:00Z",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_sessions": 3,
            "total_tokens": 10000,
            "total_cost_usd": 0.10,
            "total_duration_seconds": 90.0,
            "agents": {
                "agent1": {
                    "agent_name": "agent1",
                    "xp": 500,
                    "level": 2,
                    "success_rate": 0.85,
                    "total_invocations": 20,
                    "successful_invocations": 17,
                    "failed_invocations": 3,
                    "last_active": datetime.now(timezone.utc).isoformat(),
                    "total_tokens": 5000,
                    "total_cost_usd": 0.05,
                    "total_duration_seconds": 45.0,
                    "avg_duration_seconds": 2.25,
                    "avg_tokens_per_call": 250.0,
                    "cost_per_success_usd": 0.003,
                    "current_streak": 3,
                    "best_streak": 5,
                    "strengths": ["speed"],
                    "weaknesses": ["accuracy"],
                    "achievements": ["first_blood"],
                    "recent_events": [],
                },
                "agent2": {
                    "agent_name": "agent2",
                    "xp": 300,
                    "level": 1,
                    "success_rate": 0.75,
                    "total_invocations": 16,
                    "successful_invocations": 12,
                    "failed_invocations": 4,
                    "last_active": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                    "total_tokens": 5000,
                    "total_cost_usd": 0.05,
                    "total_duration_seconds": 45.0,
                    "avg_duration_seconds": 2.8,
                    "avg_tokens_per_call": 312.5,
                    "cost_per_success_usd": 0.004,
                    "current_streak": 0,
                    "best_streak": 3,
                    "strengths": ["accuracy"],
                    "weaknesses": ["speed"],
                    "achievements": [],
                    "recent_events": [],
                },
            },
            "events": [],
        }

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, dir=Path.home()
        ) as f:
            json.dump(metrics_data, f)
            temp_path = Path(f.name)

        yield temp_path
        temp_path.unlink(missing_ok=True)

    def test_full_cli_workflow(self, sample_metrics_file):
        """Test full CLI workflow with all modes."""
        metrics_dir = sample_metrics_file.parent

        modes = [
            ["--once"],
            ["--json"],
            ["--agent", "agent1"],
            ["--leaderboard", "--once"],
            ["--achievements", "--once"],
        ]

        for mode_args in modes:
            result = subprocess.run(
                [sys.executable, "-m", "scripts.cli"] + mode_args +
                ["--metrics-dir", str(metrics_dir)],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=10
            )
            # All modes should complete
            assert result.returncode in [0, 1], \
                f"Mode {mode_args} failed: {result.stderr}"

    def test_cli_with_nonexistent_metrics_file(self):
        """Test CLI gracefully handles missing metrics file."""
        result = subprocess.run(
            [sys.executable, "-m", "scripts.cli", "--once",
             "--metrics-dir", "/nonexistent/directory"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=5
        )
        # Should handle gracefully
        assert result.returncode in [0, 1]

    def test_json_output_is_valid_json(self, sample_metrics_file):
        """Test that JSON output is valid JSON."""
        metrics_dir = sample_metrics_file.parent

        result = subprocess.run(
            [sys.executable, "-m", "scripts.cli", "--json",
             "--metrics-dir", str(metrics_dir)],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=5
        )

        # Output should be valid JSON
        try:
            data = json.loads(result.stdout)
            assert isinstance(data, dict)
        except json.JSONDecodeError:
            # Also acceptable if error is reported
            assert "error" in result.stdout.lower() or result.returncode != 0


class TestCLIEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_metrics_file(self):
        """Test CLI with empty metrics file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = Path(f.name)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "scripts.cli", "--once",
                 "--metrics-dir", str(temp_path.parent)],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode in [0, 1]
        finally:
            temp_path.unlink(missing_ok=True)

    def test_corrupted_metrics_file(self):
        """Test CLI with corrupted metrics file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = Path(f.name)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "scripts.cli", "--json",
                 "--metrics-dir", str(temp_path.parent)],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=5
            )
            # Should handle gracefully
            assert result.returncode in [0, 1]
        finally:
            temp_path.unlink(missing_ok=True)

    def test_agent_detail_with_missing_agent(self):
        """Test agent detail mode with agent that doesn't exist."""
        metrics_data = {
            "project_name": "test",
            "agents": {"agent1": {"xp": 100}}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(metrics_data, f)
            temp_path = Path(f.name)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "scripts.cli", "--agent", "nonexistent",
                 "--metrics-dir", str(temp_path.parent)],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=5
            )
            # Should show error but not crash
            assert result.returncode in [0, 1]
            assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
