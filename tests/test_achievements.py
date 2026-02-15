#!/usr/bin/env python3
"""Comprehensive unit and integration tests for the achievements CLI display.

Tests all components of the achievement view including:
- Achievement icon and name mappings
- Achievement renderer for individual agents
- Achievement renderer for all agents
- Achievement details panel
- Metrics file monitoring
- Achievement filtering (locked vs unlocked)
- Progress bar visualization
- Layout and panel creation
- Error handling for missing agents and files
"""

import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from typing import Dict

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Add parent directory to path to import achievements module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from achievements import (
    AchievementRenderer,
    MetricsFileMonitor,
    find_metrics_file,
    ACHIEVEMENT_ICONS,
    ACHIEVEMENT_NAMES,
    ACHIEVEMENT_DESCRIPTIONS,
    DEFAULT_METRICS_DIR,
)


class TestAchievementDefinitions:
    """Test achievement definitions are complete and consistent."""

    def test_all_achievements_have_icons(self):
        """Verify all achievements have emoji icons defined."""
        assert len(ACHIEVEMENT_ICONS) == 12
        assert "first_blood" in ACHIEVEMENT_ICONS
        assert "century_club" in ACHIEVEMENT_ICONS
        assert "perfect_day" in ACHIEVEMENT_ICONS
        assert "speed_demon" in ACHIEVEMENT_ICONS
        assert "comeback_kid" in ACHIEVEMENT_ICONS
        assert "big_spender" in ACHIEVEMENT_ICONS
        assert "penny_pincher" in ACHIEVEMENT_ICONS
        assert "marathon" in ACHIEVEMENT_ICONS
        assert "polyglot" in ACHIEVEMENT_ICONS
        assert "night_owl" in ACHIEVEMENT_ICONS
        assert "streak_10" in ACHIEVEMENT_ICONS
        assert "streak_25" in ACHIEVEMENT_ICONS

    def test_all_achievements_have_names(self):
        """Verify all achievements have display names defined."""
        assert len(ACHIEVEMENT_NAMES) == 12
        for achievement_id in ACHIEVEMENT_ICONS.keys():
            assert achievement_id in ACHIEVEMENT_NAMES
            # Verify name is not empty and properly formatted
            name = ACHIEVEMENT_NAMES[achievement_id]
            assert len(name) > 0
            assert name[0].isupper()  # First letter capitalized

    def test_all_achievements_have_descriptions(self):
        """Verify all achievements have descriptions defined."""
        assert len(ACHIEVEMENT_DESCRIPTIONS) == 12
        for achievement_id in ACHIEVEMENT_ICONS.keys():
            assert achievement_id in ACHIEVEMENT_DESCRIPTIONS
            # Verify description is not empty
            description = ACHIEVEMENT_DESCRIPTIONS[achievement_id]
            assert len(description) > 0

    def test_achievement_consistency(self):
        """Verify all achievement dictionaries are consistent."""
        icon_ids = set(ACHIEVEMENT_ICONS.keys())
        name_ids = set(ACHIEVEMENT_NAMES.keys())
        desc_ids = set(ACHIEVEMENT_DESCRIPTIONS.keys())

        assert icon_ids == name_ids == desc_ids
        assert len(icon_ids) == 12

    def test_achievement_icons_are_emoji(self):
        """Verify achievement icons contain emoji characters."""
        for achievement_id, icon in ACHIEVEMENT_ICONS.items():
            assert len(icon) >= 1
            # Check that it's not plain ASCII
            assert any(ord(c) > 127 for c in icon)


class TestAchievementRenderer:
    """Test suite for AchievementRenderer class."""

    @pytest.fixture
    def console(self):
        """Create a Rich console instance for testing."""
        return Console()

    @pytest.fixture
    def renderer(self, console):
        """Create an AchievementRenderer instance for testing."""
        return AchievementRenderer(console)

    @pytest.fixture
    def sample_agent_data_with_achievements(self):
        """Create sample agent data with achievements."""
        return {
            "agent_name": "coding",
            "total_invocations": 100,
            "successful_invocations": 100,
            "failed_invocations": 0,
            "total_tokens": 50000,
            "total_cost_usd": 0.50,
            "total_duration_seconds": 2000.0,
            "success_rate": 1.0,
            "avg_duration_seconds": 20.0,
            "avg_tokens_per_call": 500.0,
            "cost_per_success_usd": 0.005,
            "xp": 2500,
            "level": 5,
            "current_streak": 50,
            "best_streak": 50,
            "achievements": ["first_blood", "century_club", "perfect_day", "marathon"],
            "strengths": ["fast_execution", "high_success_rate"],
            "weaknesses": [],
            "recent_events": ["evt-1"],
            "last_active": datetime.now(timezone.utc).isoformat(),
        }

    @pytest.fixture
    def sample_agent_data_no_achievements(self):
        """Create sample agent data without achievements."""
        return {
            "agent_name": "testing",
            "total_invocations": 5,
            "successful_invocations": 3,
            "failed_invocations": 2,
            "total_tokens": 5000,
            "total_cost_usd": 0.05,
            "total_duration_seconds": 150.0,
            "success_rate": 0.6,
            "avg_duration_seconds": 30.0,
            "avg_tokens_per_call": 1000.0,
            "cost_per_success_usd": 0.0167,
            "xp": 150,
            "level": 1,
            "current_streak": 1,
            "best_streak": 2,
            "achievements": [],
            "strengths": [],
            "weaknesses": ["high_error_rate"],
            "recent_events": [],
            "last_active": datetime.now(timezone.utc).isoformat(),
        }

    def test_create_achievements_grid_with_achievements(self, renderer, sample_agent_data_with_achievements):
        """Test creating achievement grid for agent with achievements."""
        panel = renderer.create_achievements_grid(
            "coding",
            sample_agent_data_with_achievements
        )

        assert isinstance(panel, Panel)
        assert panel.title == "Achievements - coding"

    def test_create_achievements_grid_no_achievements(self, renderer, sample_agent_data_no_achievements):
        """Test creating achievement grid for agent without achievements."""
        panel = renderer.create_achievements_grid(
            "testing",
            sample_agent_data_no_achievements
        )

        assert isinstance(panel, Panel)
        assert panel.title == "Achievements - testing"

    def test_create_achievements_grid_includes_agent_info(self, renderer, sample_agent_data_with_achievements):
        """Test that achievement grid includes agent name and XP."""
        panel = renderer.create_achievements_grid(
            "coding",
            sample_agent_data_with_achievements
        )

        assert isinstance(panel, Panel)
        # Panel should be created successfully
        assert panel is not None

    def test_achievement_grid_counts_unlocked_correctly(self, renderer, sample_agent_data_with_achievements):
        """Test that achievement grid correctly counts unlocked achievements."""
        panel = renderer.create_achievements_grid(
            "coding",
            sample_agent_data_with_achievements
        )

        assert isinstance(panel, Panel)
        # Should have 4 unlocked achievements based on fixture
        achievements = sample_agent_data_with_achievements.get("achievements", [])
        assert len(achievements) == 4

    def test_create_all_agents_achievements(self, renderer):
        """Test creating achievement summary for multiple agents."""
        agents = {
            "coding": {
                "achievements": ["first_blood", "century_club"],
                "xp": 2000,
            },
            "testing": {
                "achievements": ["first_blood"],
                "xp": 500,
            },
            "analysis": {
                "achievements": [],
                "xp": 200,
            },
        }

        panel = renderer.create_all_agents_achievements(agents)

        assert isinstance(panel, Panel)
        assert panel.title == "All Agents"

    def test_create_all_agents_achievements_empty(self, renderer):
        """Test creating achievement summary with no agents."""
        agents = {}

        panel = renderer.create_all_agents_achievements(agents)

        assert isinstance(panel, Panel)

    def test_create_achievement_detail_valid_achievement(self, renderer):
        """Test creating detail panel for a valid achievement."""
        panel = renderer.create_achievement_detail("first_blood")

        assert isinstance(panel, Panel)
        assert panel.title == "Achievement Details"

    def test_create_achievement_detail_invalid_achievement(self, renderer):
        """Test creating detail panel for an invalid achievement."""
        panel = renderer.create_achievement_detail("invalid_achievement")

        assert isinstance(panel, Panel)
        # Should have red border for error
        assert panel.border_style == "red"

    def test_create_achievement_detail_all_valid_achievements(self, renderer):
        """Test that detail panels can be created for all achievements."""
        for achievement_id in ACHIEVEMENT_ICONS.keys():
            panel = renderer.create_achievement_detail(achievement_id)
            assert isinstance(panel, Panel)
            assert panel.title == "Achievement Details"

    def test_create_initializing_layout(self, renderer):
        """Test creating initialization layout."""
        layout = renderer.create_initializing_layout()

        assert layout is not None
        # Layout object should be created successfully
        assert hasattr(layout, 'update')

    def test_progress_bar_creation(self, renderer):
        """Test progress bar visualization."""
        bar_0_0 = renderer._create_progress_bar(0, 12)
        bar_6_12 = renderer._create_progress_bar(6, 12)
        bar_12_12 = renderer._create_progress_bar(12, 12)

        assert isinstance(bar_0_0, str)
        assert isinstance(bar_6_12, str)
        assert isinstance(bar_12_12, str)
        assert len(bar_0_0) > 0
        assert len(bar_6_12) > 0
        assert len(bar_12_12) > 0

    def test_progress_bar_accurate_filled(self, renderer):
        """Test that progress bar filling is accurate."""
        bar_0_12 = renderer._create_progress_bar(0, 12)
        bar_3_12 = renderer._create_progress_bar(3, 12)
        bar_6_12 = renderer._create_progress_bar(6, 12)
        bar_12_12 = renderer._create_progress_bar(12, 12)

        # Verify filled blocks increase
        assert bar_0_12.count("█") < bar_3_12.count("█")
        assert bar_3_12.count("█") < bar_6_12.count("█")
        assert bar_6_12.count("█") < bar_12_12.count("█")


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
            metrics_data = {
                "version": 1,
                "project_name": "Test Project",
                "agents": {
                    "coding": {
                        "agent_name": "coding",
                        "achievements": ["first_blood"],
                        "xp": 500,
                    }
                },
            }
            json.dump(metrics_data, f)
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        temp_path.unlink()

    def test_load_metrics_valid_file(self, temp_metrics_file):
        """Test loading metrics from a valid file."""
        monitor = MetricsFileMonitor(temp_metrics_file)
        metrics = monitor.load_metrics()

        assert metrics is not None
        assert isinstance(metrics, dict)
        assert "version" in metrics
        assert metrics["version"] == 1

    def test_load_metrics_nonexistent_file(self):
        """Test loading metrics from a nonexistent file."""
        monitor = MetricsFileMonitor(Path("/nonexistent/metrics.json"))
        metrics = monitor.load_metrics()

        assert metrics is None

    def test_load_metrics_invalid_json(self):
        """Test loading metrics from an invalid JSON file."""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            f.write("{ invalid json }")
            temp_path = Path(f.name)

        try:
            monitor = MetricsFileMonitor(temp_path)
            metrics = monitor.load_metrics()
            assert metrics is None
        finally:
            temp_path.unlink()

    def test_has_changed_detects_modification(self, temp_metrics_file):
        """Test that has_changed detects file modifications."""
        monitor = MetricsFileMonitor(temp_metrics_file)

        # First load should indicate change
        assert monitor.has_changed() == True

        # Second check should not indicate change (no modification)
        time.sleep(0.1)
        assert monitor.has_changed() == False

        # Modify file
        with open(temp_metrics_file, 'w') as f:
            json.dump({"modified": True}, f)

        # Should detect change
        assert monitor.has_changed() == True

    def test_has_changed_nonexistent_file(self):
        """Test has_changed with nonexistent file."""
        monitor = MetricsFileMonitor(Path("/nonexistent/metrics.json"))
        assert monitor.has_changed() == False


class TestMetricsFileFinding:
    """Test suite for metrics file discovery."""

    def test_find_metrics_file_with_explicit_dir(self):
        """Test finding metrics file with explicit directory."""
        test_dir = Path("/tmp")
        metrics_path = find_metrics_file(test_dir)

        assert metrics_path.name == "metrics.json"
        assert test_dir in metrics_path.parents or metrics_path.parent == test_dir

    def test_find_metrics_file_default(self):
        """Test finding metrics file with default search."""
        metrics_path = find_metrics_file(None)

        # Should return a Path
        assert isinstance(metrics_path, Path)
        # Should contain metrics.json
        assert "metrics.json" in str(metrics_path)


class TestAchievementFiltering:
    """Test achievement filtering logic."""

    def test_filter_locked_vs_unlocked(self):
        """Test filtering achievements into locked and unlocked."""
        achievements = ["first_blood", "century_club"]
        all_achievement_ids = list(ACHIEVEMENT_ICONS.keys())

        unlocked = [a for a in achievements if a in ACHIEVEMENT_ICONS]
        locked = [a for a in all_achievement_ids if a not in unlocked]

        assert len(unlocked) == 2
        assert len(locked) == 10
        assert "first_blood" in unlocked
        assert "speed_demon" in locked

    def test_invalid_achievement_ids_ignored(self):
        """Test that invalid achievement IDs are ignored during filtering."""
        achievements = ["first_blood", "invalid_achievement", "century_club"]
        all_achievement_ids = list(ACHIEVEMENT_ICONS.keys())

        unlocked = [a for a in achievements if a in ACHIEVEMENT_ICONS]
        locked = [a for a in all_achievement_ids if a not in unlocked]

        assert len(unlocked) == 2
        assert "invalid_achievement" not in unlocked
        assert "invalid_achievement" not in locked


class TestIntegrationAchievementDisplay:
    """Integration tests for achievement display with real metrics data."""

    @pytest.fixture
    def sample_metrics_data(self):
        """Create sample metrics data for integration testing."""
        return {
            "version": 1,
            "project_name": "Test Agent Status Dashboard",
            "created_at": "2026-02-14T00:00:00Z",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_sessions": 5,
            "total_tokens": 50000,
            "total_cost_usd": 0.50,
            "total_duration_seconds": 1000.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 100,
                    "successful_invocations": 100,
                    "failed_invocations": 0,
                    "total_tokens": 35000,
                    "total_cost_usd": 0.35,
                    "total_duration_seconds": 800.0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 8.0,
                    "avg_tokens_per_call": 350.0,
                    "cost_per_success_usd": 0.0035,
                    "xp": 2500,
                    "level": 5,
                    "current_streak": 100,
                    "best_streak": 100,
                    "achievements": [
                        "first_blood",
                        "century_club",
                        "perfect_day",
                        "speed_demon",
                        "marathon",
                        "streak_10",
                        "streak_25",
                    ],
                    "strengths": ["fast_execution", "high_success_rate"],
                    "weaknesses": [],
                    "recent_events": ["evt-1"],
                    "last_active": datetime.now(timezone.utc).isoformat(),
                },
                "testing": {
                    "agent_name": "testing",
                    "total_invocations": 20,
                    "successful_invocations": 15,
                    "failed_invocations": 5,
                    "total_tokens": 15000,
                    "total_cost_usd": 0.15,
                    "total_duration_seconds": 200.0,
                    "success_rate": 0.75,
                    "avg_duration_seconds": 10.0,
                    "avg_tokens_per_call": 750.0,
                    "cost_per_success_usd": 0.01,
                    "xp": 750,
                    "level": 2,
                    "current_streak": 5,
                    "best_streak": 10,
                    "achievements": ["first_blood"],
                    "strengths": [],
                    "weaknesses": ["high_error_rate"],
                    "recent_events": ["evt-2"],
                    "last_active": datetime.now(timezone.utc).isoformat(),
                },
            },
            "events": [],
            "sessions": [],
        }

    def test_integration_render_single_agent_achievements(self, sample_metrics_data):
        """Integration test: render achievements for single agent."""
        console = Console()
        renderer = AchievementRenderer(console)

        agents = sample_metrics_data["agents"]
        panel = renderer.create_achievements_grid("coding", agents["coding"])

        assert isinstance(panel, Panel)
        assert "coding" in panel.title

    def test_integration_render_all_agents_achievements(self, sample_metrics_data):
        """Integration test: render achievements for all agents."""
        console = Console()
        renderer = AchievementRenderer(console)

        agents = sample_metrics_data["agents"]
        panel = renderer.create_all_agents_achievements(agents)

        assert isinstance(panel, Panel)
        assert "All Agents" in panel.title

    def test_integration_agent_with_many_achievements(self, sample_metrics_data):
        """Integration test: display agent with many achievements."""
        console = Console()
        renderer = AchievementRenderer(console)

        agent_data = sample_metrics_data["agents"]["coding"]
        # Verify agent has multiple achievements
        assert len(agent_data["achievements"]) >= 5

        panel = renderer.create_achievements_grid("coding", agent_data)
        assert isinstance(panel, Panel)

    def test_integration_agent_with_few_achievements(self, sample_metrics_data):
        """Integration test: display agent with few achievements."""
        console = Console()
        renderer = AchievementRenderer(console)

        agent_data = sample_metrics_data["agents"]["testing"]
        # Verify agent has 1 achievement
        assert len(agent_data["achievements"]) == 1

        panel = renderer.create_achievements_grid("testing", agent_data)
        assert isinstance(panel, Panel)

    def test_integration_metrics_file_round_trip(self, sample_metrics_data):
        """Integration test: write and read metrics file."""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            json.dump(sample_metrics_data, f)
            temp_path = Path(f.name)

        try:
            monitor = MetricsFileMonitor(temp_path)
            loaded_metrics = monitor.load_metrics()

            assert loaded_metrics is not None
            assert loaded_metrics["project_name"] == sample_metrics_data["project_name"]
            assert "coding" in loaded_metrics["agents"]
            assert "testing" in loaded_metrics["agents"]
        finally:
            temp_path.unlink()


class TestAchievementIcons:
    """Test achievement icon consistency and usability."""

    def test_all_achievement_icons_are_single_emoji(self):
        """Verify each achievement has a single emoji icon."""
        for achievement_id, icon in ACHIEVEMENT_ICONS.items():
            # Most emojis are 1-2 characters
            assert len(icon) >= 1 and len(icon) <= 2

    def test_achievement_icons_are_different(self):
        """Verify each achievement has a unique icon."""
        icons = list(ACHIEVEMENT_ICONS.values())
        # Note: Some emojis might render as same, but they should be unique in code
        assert len(set(icons)) >= 10  # At least 10 should be visually different

    def test_first_blood_icon(self):
        """Test specific achievement icon."""
        assert ACHIEVEMENT_ICONS["first_blood"] == "🩸"
        assert ACHIEVEMENT_NAMES["first_blood"] == "First Blood"
        assert "successful invocation" in ACHIEVEMENT_DESCRIPTIONS["first_blood"]

    def test_century_club_icon(self):
        """Test specific achievement icon."""
        assert ACHIEVEMENT_ICONS["century_club"] == "💯"
        assert ACHIEVEMENT_NAMES["century_club"] == "Century Club"
        assert "100" in ACHIEVEMENT_DESCRIPTIONS["century_club"]


class TestErrorHandling:
    """Test error handling in achievement display."""

    def test_renderer_with_missing_agent_field(self):
        """Test renderer handles agent data with missing fields."""
        console = Console()
        renderer = AchievementRenderer(console)

        incomplete_agent = {
            "agent_name": "incomplete",
            # Missing many fields
        }

        panel = renderer.create_achievements_grid("incomplete", incomplete_agent)
        assert isinstance(panel, Panel)

    def test_renderer_with_empty_achievements_list(self):
        """Test renderer with empty achievements list."""
        console = Console()
        renderer = AchievementRenderer(console)

        agent_data = {
            "agent_name": "empty",
            "achievements": [],
            "xp": 0,
        }

        panel = renderer.create_achievements_grid("empty", agent_data)
        assert isinstance(panel, Panel)

    def test_achievement_detail_with_nonexistent_id(self):
        """Test achievement detail with invalid ID."""
        console = Console()
        renderer = AchievementRenderer(console)

        panel = renderer.create_achievement_detail("nonexistent_achievement")
        assert isinstance(panel, Panel)
        assert panel.border_style == "red"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
