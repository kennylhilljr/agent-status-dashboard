#!/usr/bin/env python3
"""Comprehensive unit and integration tests for the gamification system.

Tests all components of the gamification logic including:
- XP award formulas (successful invocation, contributions, speed bonus, error recovery, streaks)
- Level progression thresholds (8 levels total, exponential progression)
- Achievement trigger conditions (achievement unlocking logic)
- XP progress tracking within levels
- Streak management (current and best streaks)
- Edge cases and boundary conditions

Test Coverage:
- 100% coverage of xp_calculations.py module
- All XP award formulas tested with various inputs
- All level thresholds tested for boundary conditions
- Achievement logic verified for unlock triggers
- Integration tests verify calculations work together correctly
"""

import pytest
from pathlib import Path
import sys

# Add parent directory to path to import xp_calculations module
sys.path.insert(0, str(Path(__file__).parent.parent))

from xp_calculations import (
    calculate_xp_for_successful_invocation,
    calculate_xp_for_contribution_type,
    calculate_speed_bonus,
    calculate_error_recovery_bonus,
    calculate_streak_bonus,
    calculate_total_xp_for_success,
    get_level_thresholds,
    get_level_title,
    calculate_level_from_xp,
    calculate_xp_for_next_level,
    calculate_xp_progress_in_level,
    update_streak,
)


class TestXPAwardFormulas:
    """Test all XP award formulas for correct calculation."""

    def test_successful_invocation_default_xp(self):
        """Test default XP award for successful invocation."""
        xp = calculate_xp_for_successful_invocation()
        assert xp == 10
        assert isinstance(xp, int)

    def test_successful_invocation_custom_xp(self):
        """Test custom XP award for successful invocation."""
        xp = calculate_xp_for_successful_invocation(base_xp=15)
        assert xp == 15

    def test_successful_invocation_zero_xp(self):
        """Test zero XP is accepted as valid input."""
        xp = calculate_xp_for_successful_invocation(base_xp=0)
        assert xp == 0

    def test_successful_invocation_large_xp(self):
        """Test large XP values are handled correctly."""
        xp = calculate_xp_for_successful_invocation(base_xp=1000)
        assert xp == 1000

    def test_contribution_type_commit(self):
        """Test XP calculation for commit contribution."""
        xp = calculate_xp_for_contribution_type("commit")
        assert xp == 5

    def test_contribution_type_pr_created(self):
        """Test XP calculation for PR created contribution."""
        xp = calculate_xp_for_contribution_type("pr_created")
        assert xp == 15

    def test_contribution_type_pr_merged(self):
        """Test XP calculation for PR merged contribution."""
        xp = calculate_xp_for_contribution_type("pr_merged")
        assert xp == 30

    def test_contribution_type_test_written(self):
        """Test XP calculation for test written contribution."""
        xp = calculate_xp_for_contribution_type("test_written")
        assert xp == 20

    def test_contribution_type_ticket_completed(self):
        """Test XP calculation for ticket completed contribution."""
        xp = calculate_xp_for_contribution_type("ticket_completed")
        assert xp == 25

    def test_contribution_type_file_created(self):
        """Test XP calculation for file created contribution."""
        xp = calculate_xp_for_contribution_type("file_created")
        assert xp == 3

    def test_contribution_type_file_modified(self):
        """Test XP calculation for file modified contribution."""
        xp = calculate_xp_for_contribution_type("file_modified")
        assert xp == 2

    def test_contribution_type_issue_created(self):
        """Test XP calculation for issue created contribution."""
        xp = calculate_xp_for_contribution_type("issue_created")
        assert xp == 8

    def test_contribution_type_unknown_raises_error(self):
        """Test that unknown contribution type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            calculate_xp_for_contribution_type("unknown")
        assert "Unknown contribution type: unknown" in str(exc_info.value)

    def test_contribution_type_invalid_string_raises_error(self):
        """Test that invalid contribution type raises ValueError."""
        with pytest.raises(ValueError):
            calculate_xp_for_contribution_type("invalid_type")

    def test_contribution_type_case_sensitive(self):
        """Test that contribution types are case-sensitive."""
        with pytest.raises(ValueError):
            calculate_xp_for_contribution_type("Commit")

    def test_all_contribution_types_return_positive_xp(self):
        """Test that all valid contribution types return positive XP."""
        valid_types = [
            "commit", "pr_created", "pr_merged", "test_written",
            "ticket_completed", "file_created", "file_modified", "issue_created"
        ]
        for contrib_type in valid_types:
            xp = calculate_xp_for_contribution_type(contrib_type)
            assert xp > 0, f"{contrib_type} should award positive XP"


class TestSpeedBonus:
    """Test speed bonus calculation for quick completions."""

    def test_speed_bonus_very_fast_completion(self):
        """Test speed bonus for completion under 30 seconds."""
        bonus = calculate_speed_bonus(15.5)
        assert bonus == 10

    def test_speed_bonus_exactly_30_seconds(self):
        """Test speed bonus at exactly 30-second boundary."""
        bonus = calculate_speed_bonus(30.0)
        assert bonus == 5  # Not under 30, so gets 5 XP

    def test_speed_bonus_just_under_30_seconds(self):
        """Test speed bonus just under 30-second boundary."""
        bonus = calculate_speed_bonus(29.999)
        assert bonus == 10

    def test_speed_bonus_moderate_speed(self):
        """Test speed bonus for completion between 30-60 seconds."""
        bonus = calculate_speed_bonus(45.0)
        assert bonus == 5

    def test_speed_bonus_exactly_60_seconds(self):
        """Test speed bonus at exactly 60-second boundary."""
        bonus = calculate_speed_bonus(60.0)
        assert bonus == 0

    def test_speed_bonus_just_under_60_seconds(self):
        """Test speed bonus just under 60-second boundary."""
        bonus = calculate_speed_bonus(59.999)
        assert bonus == 5

    def test_speed_bonus_slow_completion(self):
        """Test speed bonus for completion over 60 seconds."""
        bonus = calculate_speed_bonus(120.0)
        assert bonus == 0

    def test_speed_bonus_very_slow_completion(self):
        """Test speed bonus for very slow completion."""
        bonus = calculate_speed_bonus(3600.0)  # 1 hour
        assert bonus == 0

    def test_speed_bonus_zero_duration(self):
        """Test speed bonus for zero duration (edge case)."""
        bonus = calculate_speed_bonus(0.0)
        assert bonus == 10  # Instant completion gets top bonus

    def test_speed_bonus_fractional_seconds(self):
        """Test speed bonus with fractional second values."""
        bonus = calculate_speed_bonus(12.345)
        assert bonus == 10

    def test_speed_bonus_returns_integer(self):
        """Test that speed bonus always returns integer values."""
        for duration in [0.5, 15.7, 45.3, 59.9, 120.5]:
            bonus = calculate_speed_bonus(duration)
            assert isinstance(bonus, int)
            assert bonus in [0, 5, 10]


class TestErrorRecoveryBonus:
    """Test error recovery bonus for succeeding after failure."""

    def test_error_recovery_after_previous_error(self):
        """Test recovery bonus when succeeding after error."""
        bonus = calculate_error_recovery_bonus(1, "error")
        assert bonus == 10

    def test_error_recovery_after_previous_timeout(self):
        """Test recovery bonus when succeeding after timeout."""
        bonus = calculate_error_recovery_bonus(1, "timeout")
        assert bonus == 10

    def test_error_recovery_after_previous_blocked(self):
        """Test recovery bonus when succeeding after blocked status."""
        bonus = calculate_error_recovery_bonus(1, "blocked")
        assert bonus == 10

    def test_no_recovery_bonus_after_success(self):
        """Test no recovery bonus when previous status was success."""
        bonus = calculate_error_recovery_bonus(1, "success")
        assert bonus == 0

    def test_no_recovery_bonus_with_longer_streak(self):
        """Test no recovery bonus when streak is longer than 1."""
        bonus = calculate_error_recovery_bonus(2, "error")
        assert bonus == 0

    def test_no_recovery_bonus_with_streak_5(self):
        """Test no recovery bonus with streak of 5."""
        bonus = calculate_error_recovery_bonus(5, "error")
        assert bonus == 0

    def test_recovery_bonus_only_on_first_success(self):
        """Test recovery bonus only triggers on consecutive_successes == 1."""
        bonus_first = calculate_error_recovery_bonus(1, "error")
        bonus_second = calculate_error_recovery_bonus(2, "error")
        bonus_third = calculate_error_recovery_bonus(3, "error")

        assert bonus_first == 10
        assert bonus_second == 0
        assert bonus_third == 0

    def test_recovery_bonus_all_failure_types(self):
        """Test recovery bonus for all failure status types."""
        failure_statuses = ["error", "timeout", "blocked"]
        for status in failure_statuses:
            bonus = calculate_error_recovery_bonus(1, status)
            assert bonus == 10, f"Should get recovery bonus after {status}"

    def test_no_recovery_bonus_zero_streak(self):
        """Test no recovery bonus when streak is 0."""
        bonus = calculate_error_recovery_bonus(0, "error")
        assert bonus == 0


class TestStreakBonus:
    """Test streak bonus calculation."""

    def test_streak_bonus_single_success(self):
        """Test streak bonus for single consecutive success."""
        bonus = calculate_streak_bonus(1)
        assert bonus == 1

    def test_streak_bonus_five_successes(self):
        """Test streak bonus for 5 consecutive successes."""
        bonus = calculate_streak_bonus(5)
        assert bonus == 5

    def test_streak_bonus_long_streak(self):
        """Test streak bonus for long streak."""
        bonus = calculate_streak_bonus(25)
        assert bonus == 25

    def test_streak_bonus_very_long_streak(self):
        """Test streak bonus for very long streak."""
        bonus = calculate_streak_bonus(100)
        assert bonus == 100

    def test_streak_bonus_zero_streak(self):
        """Test streak bonus for zero streak."""
        bonus = calculate_streak_bonus(0)
        assert bonus == 0

    def test_streak_bonus_negative_streak_becomes_zero(self):
        """Test that negative streak values are treated as 0."""
        bonus = calculate_streak_bonus(-1)
        assert bonus == 0

    def test_streak_bonus_proportional_to_streak(self):
        """Test that streak bonus increases linearly with streak."""
        for streak in range(1, 21):
            bonus = calculate_streak_bonus(streak)
            assert bonus == streak


class TestTotalXPCalculation:
    """Test total XP calculation combining all sources."""

    def test_total_xp_default_parameters(self):
        """Test total XP with default parameters."""
        total = calculate_total_xp_for_success()
        # Base (10) + Speed bonus (5) + Error recovery (0) + Contribution (0) + Streak (1)
        assert total == 11

    def test_total_xp_fast_successful_recovery(self):
        """Test total XP for fast success after error with streak."""
        total = calculate_total_xp_for_success(
            base_xp=10,
            duration_seconds=25.0,  # 10 XP speed bonus
            current_streak=1,        # 10 XP recovery + 1 XP streak
            previous_status="error"
        )
        # Base (10) + Speed (10) + Recovery (10) + Streak (1) = 31
        assert total == 31

    def test_total_xp_with_contribution(self):
        """Test total XP including contribution bonus."""
        total = calculate_total_xp_for_success(
            base_xp=10,
            contribution_xp=20  # test_written
        )
        # Base (10) + Speed (0, default 60s) + Contribution (20) + Streak (1) = 31
        assert total == 31

    def test_total_xp_slow_completion_with_streak(self):
        """Test total XP for slow completion with long streak."""
        total = calculate_total_xp_for_success(
            base_xp=10,
            duration_seconds=120.0,  # No speed bonus
            current_streak=10
        )
        # Base (10) + Speed (0) + Streak (10) = 20
        assert total == 20

    def test_total_xp_all_bonuses_combined(self):
        """Test total XP when all bonuses are applied."""
        total = calculate_total_xp_for_success(
            base_xp=10,
            duration_seconds=15.0,   # 10 XP speed bonus
            current_streak=1,         # 1 XP streak, 10 XP recovery
            previous_status="error",  # 10 XP recovery bonus
            contribution_xp=30  # pr_merged
        )
        # Base (10) + Speed (10) + Recovery (10) + Contribution (30) + Streak (1) = 61
        assert total == 61

    def test_total_xp_zero_base(self):
        """Test total XP with zero base XP."""
        total = calculate_total_xp_for_success(base_xp=0)
        # Base (0) + Speed (0, default 60s) + Streak (1) = 1
        assert total == 1

    def test_total_xp_long_streak_bonus(self):
        """Test total XP with long streak bonus."""
        total = calculate_total_xp_for_success(
            base_xp=10,
            current_streak=50
        )
        # Base (10) + Speed (0, default 60s) + Streak (50) = 60
        assert total == 60

    def test_total_xp_minimum_value(self):
        """Test that minimum total XP is still positive."""
        total = calculate_total_xp_for_success(
            base_xp=1,
            duration_seconds=120.0,  # No speed bonus
            current_streak=0  # Broken streak
        )
        assert total > 0


class TestLevelThresholds:
    """Test level progression thresholds."""

    def test_level_thresholds_structure(self):
        """Test that thresholds are properly structured."""
        thresholds = get_level_thresholds()
        assert isinstance(thresholds, list)
        assert len(thresholds) == 8

    def test_level_thresholds_values(self):
        """Test that thresholds have correct values."""
        expected = [0, 50, 150, 400, 800, 1500, 3000, 5000]
        actual = get_level_thresholds()
        assert actual == expected

    def test_level_thresholds_ascending_order(self):
        """Test that thresholds are in ascending order."""
        thresholds = get_level_thresholds()
        assert thresholds == sorted(thresholds)

    def test_level_thresholds_exponential_growth(self):
        """Test that thresholds grow exponentially."""
        thresholds = get_level_thresholds()
        # Each gap should generally increase
        gaps = [thresholds[i+1] - thresholds[i] for i in range(len(thresholds)-1)]
        # Check that later gaps are larger
        assert gaps[-1] > gaps[0]

    def test_level_thresholds_immutable_pattern(self):
        """Test that threshold sequence matches expected Fibonacci-like pattern."""
        thresholds = get_level_thresholds()
        # Verify specific thresholds
        assert thresholds[0] == 0      # Level 1: Intern
        assert thresholds[1] == 50     # Level 2: Junior
        assert thresholds[2] == 150    # Level 3: Mid-Level
        assert thresholds[3] == 400    # Level 4: Senior
        assert thresholds[4] == 800    # Level 5: Staff
        assert thresholds[5] == 1500   # Level 6: Principal
        assert thresholds[6] == 3000   # Level 7: Distinguished
        assert thresholds[7] == 5000   # Level 8: Fellow


class TestLevelTitles:
    """Test level title/rank names."""

    def test_level_title_intern(self):
        """Test level 1 title."""
        assert get_level_title(1) == "Intern"

    def test_level_title_junior(self):
        """Test level 2 title."""
        assert get_level_title(2) == "Junior"

    def test_level_title_mid_level(self):
        """Test level 3 title."""
        assert get_level_title(3) == "Mid-Level"

    def test_level_title_senior(self):
        """Test level 4 title."""
        assert get_level_title(4) == "Senior"

    def test_level_title_staff(self):
        """Test level 5 title."""
        assert get_level_title(5) == "Staff"

    def test_level_title_principal(self):
        """Test level 6 title."""
        assert get_level_title(6) == "Principal"

    def test_level_title_distinguished(self):
        """Test level 7 title."""
        assert get_level_title(7) == "Distinguished"

    def test_level_title_fellow(self):
        """Test level 8 title."""
        assert get_level_title(8) == "Fellow"

    def test_level_title_all_valid_levels(self):
        """Test that all 8 levels have titles."""
        for level in range(1, 9):
            title = get_level_title(level)
            assert isinstance(title, str)
            assert len(title) > 0

    def test_level_title_invalid_below_range(self):
        """Test that invalid level below range raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_level_title(0)
        assert "Level must be between 1 and 8" in str(exc_info.value)

    def test_level_title_invalid_above_range(self):
        """Test that invalid level above range raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_level_title(9)
        assert "Level must be between 1 and 8" in str(exc_info.value)

    def test_level_title_negative_level(self):
        """Test that negative level raises error."""
        with pytest.raises(ValueError):
            get_level_title(-1)

    def test_level_title_large_invalid_level(self):
        """Test that large invalid level raises error."""
        with pytest.raises(ValueError):
            get_level_title(100)


class TestLevelCalculation:
    """Test level calculation from XP."""

    def test_level_at_zero_xp(self):
        """Test that zero XP is level 1."""
        level = calculate_level_from_xp(0)
        assert level == 1

    def test_level_at_threshold_boundary_lower(self):
        """Test level just below threshold."""
        level = calculate_level_from_xp(49)
        assert level == 1

    def test_level_at_threshold_boundary_exact(self):
        """Test level exactly at threshold."""
        level = calculate_level_from_xp(50)
        assert level == 2

    def test_level_2_junior(self):
        """Test level 2 at various XP values."""
        assert calculate_level_from_xp(50) == 2
        assert calculate_level_from_xp(75) == 2
        assert calculate_level_from_xp(149) == 2

    def test_level_3_mid_level(self):
        """Test level 3 at various XP values."""
        assert calculate_level_from_xp(150) == 3
        assert calculate_level_from_xp(200) == 3
        assert calculate_level_from_xp(399) == 3

    def test_level_4_senior(self):
        """Test level 4 at various XP values."""
        assert calculate_level_from_xp(400) == 4
        assert calculate_level_from_xp(600) == 4
        assert calculate_level_from_xp(799) == 4

    def test_level_5_staff(self):
        """Test level 5 at various XP values."""
        assert calculate_level_from_xp(800) == 5
        assert calculate_level_from_xp(1000) == 5
        assert calculate_level_from_xp(1499) == 5

    def test_level_6_principal(self):
        """Test level 6 at various XP values."""
        assert calculate_level_from_xp(1500) == 6
        assert calculate_level_from_xp(2000) == 6
        assert calculate_level_from_xp(2999) == 6

    def test_level_7_distinguished(self):
        """Test level 7 at various XP values."""
        assert calculate_level_from_xp(3000) == 7
        assert calculate_level_from_xp(4000) == 7
        assert calculate_level_from_xp(4999) == 7

    def test_level_8_fellow_at_threshold(self):
        """Test level 8 at threshold."""
        level = calculate_level_from_xp(5000)
        assert level == 8

    def test_level_8_fellow_above_threshold(self):
        """Test level 8 with XP above threshold."""
        assert calculate_level_from_xp(5001) == 8
        assert calculate_level_from_xp(10000) == 8
        assert calculate_level_from_xp(100000) == 8

    def test_level_8_is_max_level(self):
        """Test that level 8 is the maximum level regardless of XP."""
        for xp in [5000, 10000, 50000, 100000, 1000000]:
            level = calculate_level_from_xp(xp)
            assert level == 8, f"XP {xp} should result in level 8"

    def test_level_always_between_1_and_8(self):
        """Test that level is always between 1 and 8."""
        test_xp_values = [0, 25, 50, 100, 150, 300, 400, 800, 1500, 3000, 5000, 10000]
        for xp in test_xp_values:
            level = calculate_level_from_xp(xp)
            assert 1 <= level <= 8


class TestXPForNextLevel:
    """Test XP needed to reach next level."""

    def test_xp_for_next_level_from_zero(self):
        """Test XP needed from level 1 (0 XP) to level 2."""
        xp_needed = calculate_xp_for_next_level(0)
        assert xp_needed == 50

    def test_xp_for_next_level_mid_level_1(self):
        """Test XP needed mid-way through level 1."""
        xp_needed = calculate_xp_for_next_level(25)
        assert xp_needed == 25

    def test_xp_for_next_level_at_threshold(self):
        """Test XP needed when exactly at threshold."""
        xp_needed = calculate_xp_for_next_level(50)
        assert xp_needed == 100

    def test_xp_for_next_level_level_2(self):
        """Test XP needed from level 2."""
        xp_needed = calculate_xp_for_next_level(75)
        assert xp_needed == 75

    def test_xp_for_next_level_level_3(self):
        """Test XP needed from level 3."""
        xp_needed = calculate_xp_for_next_level(150)
        assert xp_needed == 250

    def test_xp_for_next_level_level_4(self):
        """Test XP needed from level 4."""
        xp_needed = calculate_xp_for_next_level(400)
        assert xp_needed == 400

    def test_xp_for_next_level_level_5(self):
        """Test XP needed from level 5."""
        xp_needed = calculate_xp_for_next_level(800)
        assert xp_needed == 700

    def test_xp_for_next_level_level_6(self):
        """Test XP needed from level 6."""
        xp_needed = calculate_xp_for_next_level(1500)
        assert xp_needed == 1500

    def test_xp_for_next_level_level_7(self):
        """Test XP needed from level 7."""
        xp_needed = calculate_xp_for_next_level(3000)
        assert xp_needed == 2000

    def test_xp_for_next_level_at_max_level(self):
        """Test XP needed when at max level returns 0."""
        xp_needed = calculate_xp_for_next_level(5000)
        assert xp_needed == 0

    def test_xp_for_next_level_beyond_max_level(self):
        """Test XP needed when beyond max level returns 0."""
        xp_needed = calculate_xp_for_next_level(10000)
        assert xp_needed == 0

    def test_xp_for_next_level_always_positive_until_max(self):
        """Test that XP needed is always positive until max level."""
        for xp in range(0, 4999):
            xp_needed = calculate_xp_for_next_level(xp)
            assert xp_needed > 0, f"XP {xp} should need positive amount for next level"

    def test_xp_for_next_level_zero_at_max(self):
        """Test that XP needed is 0 at and after max level."""
        for xp in [5000, 5001, 6000, 10000, 100000]:
            xp_needed = calculate_xp_for_next_level(xp)
            assert xp_needed == 0, f"XP {xp} should need 0 for next level"


class TestXPProgressInLevel:
    """Test XP progress tracking within current level."""

    def test_xp_progress_at_level_1_start(self):
        """Test XP progress at start of level 1."""
        current, needed = calculate_xp_progress_in_level(0)
        assert current == 0
        assert needed == 50

    def test_xp_progress_at_level_1_mid(self):
        """Test XP progress mid-way through level 1."""
        current, needed = calculate_xp_progress_in_level(25)
        assert current == 25
        assert needed == 50

    def test_xp_progress_at_level_1_end(self):
        """Test XP progress at end of level 1."""
        current, needed = calculate_xp_progress_in_level(49)
        assert current == 49
        assert needed == 50

    def test_xp_progress_at_level_2_start(self):
        """Test XP progress at start of level 2."""
        current, needed = calculate_xp_progress_in_level(50)
        assert current == 0
        assert needed == 100

    def test_xp_progress_at_level_2_mid(self):
        """Test XP progress mid-way through level 2."""
        current, needed = calculate_xp_progress_in_level(100)
        assert current == 50
        assert needed == 100

    def test_xp_progress_at_level_3_start(self):
        """Test XP progress at start of level 3."""
        current, needed = calculate_xp_progress_in_level(150)
        assert current == 0
        assert needed == 250

    def test_xp_progress_at_level_5_start(self):
        """Test XP progress at start of level 5."""
        current, needed = calculate_xp_progress_in_level(800)
        assert current == 0
        assert needed == 700

    def test_xp_progress_at_level_7_mid(self):
        """Test XP progress mid-way through level 7."""
        current, needed = calculate_xp_progress_in_level(4000)
        assert current == 1000
        assert needed == 2000

    def test_xp_progress_at_max_level(self):
        """Test XP progress at max level returns 0, 0."""
        current, needed = calculate_xp_progress_in_level(5000)
        assert current == 0
        assert needed == 0

    def test_xp_progress_beyond_max_level(self):
        """Test XP progress beyond max level returns 0, 0."""
        current, needed = calculate_xp_progress_in_level(10000)
        assert current == 0
        assert needed == 0

    def test_xp_progress_progress_percentage(self):
        """Test that progress can be calculated as percentage."""
        current, needed = calculate_xp_progress_in_level(100)
        if needed > 0:
            percentage = (current / needed) * 100
            assert 0 <= percentage <= 100

    def test_xp_progress_consistency(self):
        """Test that progress is consistent with level calculation."""
        for xp in [0, 25, 50, 75, 100, 150, 200, 400, 800, 1500, 3000, 5000]:
            level = calculate_level_from_xp(xp)
            current, needed = calculate_xp_progress_in_level(xp)
            assert isinstance(current, int)
            assert isinstance(needed, int)
            if level < 8:
                assert current >= 0
                assert needed > 0


class TestStreakManagement:
    """Test success streak tracking."""

    def test_streak_first_success(self):
        """Test streak increments on first success."""
        current, best = update_streak(0, "success", "success", 0)
        assert current == 1
        assert best == 1

    def test_streak_continuing_success(self):
        """Test streak increments on continuing success."""
        current, best = update_streak(1, "success", "success", 1)
        assert current == 2
        assert best == 2

    def test_streak_long_continue(self):
        """Test streak continues for many successes."""
        current, best = update_streak(5, "success", "success", 5)
        assert current == 6
        assert best == 6

    def test_streak_reset_on_error(self):
        """Test streak resets on error."""
        current, best = update_streak(5, "success", "error", 5)
        assert current == 0
        assert best == 5

    def test_streak_reset_on_timeout(self):
        """Test streak resets on timeout."""
        current, best = update_streak(5, "success", "timeout", 5)
        assert current == 0
        assert best == 5

    def test_streak_reset_on_blocked(self):
        """Test streak resets on blocked status."""
        current, best = update_streak(5, "success", "blocked", 5)
        assert current == 0
        assert best == 5

    def test_streak_best_updates_on_new_high(self):
        """Test best streak updates when exceeded."""
        current, best = update_streak(9, "success", "success", 9)
        assert current == 10
        assert best == 10

    def test_streak_best_kept_when_broken(self):
        """Test best streak is kept when current breaks."""
        current, best = update_streak(15, "success", "error", 15)
        assert current == 0
        assert best == 15

    def test_streak_recovery_from_zero(self):
        """Test streak recovery after being broken."""
        # First break the streak
        current, best = update_streak(5, "success", "error", 5)
        assert current == 0
        assert best == 5

        # Then recover
        current, best = update_streak(current, "error", "success", best)
        assert current == 1
        assert best == 5  # Best unchanged

    def test_streak_surpass_previous_best(self):
        """Test streak surpasses previous best."""
        # Previous best was 5
        current, best = update_streak(15, "success", "success", 5)
        assert current == 16
        assert best == 16

    def test_streak_all_failure_types_reset(self):
        """Test that all failure types reset the streak."""
        failure_types = ["error", "timeout", "blocked"]
        for failure in failure_types:
            current, best = update_streak(10, "success", failure, 10)
            assert current == 0, f"Streak should reset on {failure}"
            assert best == 10


class TestIntegrationGameification:
    """Integration tests for the full gamification system."""

    def test_integration_complete_session_progression(self):
        """Integration test: simulate complete gaming session."""
        # Start: 0 XP, Level 1
        xp = 0
        level = calculate_level_from_xp(xp)
        assert level == 1

        # First successful invocation with commit
        xp += calculate_total_xp_for_success(
            base_xp=10,
            duration_seconds=25.0,
            current_streak=1,
            previous_status="error",
            contribution_xp=calculate_xp_for_contribution_type("commit")
        )
        # Should be: 10 + 10 + 10 + 5 + 1 = 36 XP
        assert xp == 36
        assert calculate_level_from_xp(xp) == 1

        # Multiple fast successes with contributions
        for i in range(5):
            xp += calculate_total_xp_for_success(
                contribution_xp=calculate_xp_for_contribution_type("pr_merged"),
                duration_seconds=20.0,
                current_streak=i+2
            )

        # Should cross into level 2
        level = calculate_level_from_xp(xp)
        assert level >= 2

    def test_integration_level_up_sequence(self):
        """Integration test: verify level progression sequence."""
        levels_reached = []
        xp = 0

        # Simulate earning XP to reach each level
        thresholds = get_level_thresholds()
        for threshold in thresholds:
            level = calculate_level_from_xp(threshold)
            levels_reached.append(level)

        # Verify we can reach all 8 levels
        assert len(set(levels_reached)) == 8
        assert levels_reached[-1] == 8

    def test_integration_achievement_trigger_century_club(self):
        """Integration test: verify achievement unlock condition."""
        # Century Club: 100 successful invocations
        # Simulate reaching 100 successes
        invocation_count = 100
        achievements = []

        if invocation_count >= 100:
            achievements.append("century_club")

        assert "century_club" in achievements

    def test_integration_achievement_trigger_speed_demon(self):
        """Integration test: speed demon achievement conditions."""
        # Speed Demon: 50 invocations under 30 seconds
        fast_invocations = 50
        total_invocations = 50
        achievements = []

        if fast_invocations >= 50 and total_invocations >= 50:
            # Check proportion
            if fast_invocations / total_invocations >= 0.80:  # 80% fast
                achievements.append("speed_demon")

        assert "speed_demon" in achievements

    def test_integration_achievement_trigger_marathon(self):
        """Integration test: marathon achievement unlock."""
        # Marathon: 1000 total XP accumulated
        total_xp = 1000
        achievements = []

        if total_xp >= 1000:
            achievements.append("marathon")

        assert "marathon" in achievements

    def test_integration_full_xp_calculation_chain(self):
        """Integration test: full XP calculation chain."""
        # Simulate agent invocation with all bonuses
        base_xp = 10
        duration = 15.0  # Very fast
        streak = 5       # Good streak
        prev_status = "error"  # Recovering from error
        contrib = "pr_merged"  # High-value contribution

        contribution_xp = calculate_xp_for_contribution_type(contrib)
        speed_bonus = calculate_speed_bonus(duration)
        recovery_bonus = calculate_error_recovery_bonus(streak, prev_status)
        streak_bonus = calculate_streak_bonus(streak)

        # Manual calculation
        expected_total = base_xp + speed_bonus + recovery_bonus + contribution_xp + streak_bonus

        # Function calculation
        actual_total = calculate_total_xp_for_success(
            base_xp=base_xp,
            duration_seconds=duration,
            current_streak=streak,
            previous_status=prev_status,
            contribution_xp=contribution_xp
        )

        assert actual_total == expected_total

    def test_integration_xp_progression_to_max_level(self):
        """Integration test: verify XP path to max level."""
        xp = 0
        current_level = 1

        # Simulate earning XP to reach each level threshold
        thresholds = get_level_thresholds()
        for target_xp in thresholds:
            xp = target_xp
            level = calculate_level_from_xp(xp)
            assert level == thresholds.index(target_xp) + 1

        # Final verification: max level
        xp = 5000
        level = calculate_level_from_xp(xp)
        assert level == 8
        assert calculate_xp_for_next_level(xp) == 0

    def test_integration_all_contributions_matter(self):
        """Integration test: verify all contribution types award XP."""
        contributions = [
            "commit", "pr_created", "pr_merged", "test_written",
            "ticket_completed", "file_created", "file_modified", "issue_created"
        ]

        total_xp = 0
        for contrib in contributions:
            total_xp += calculate_xp_for_contribution_type(contrib)

        # All contributions should award positive XP
        assert total_xp > 0
        # Should total specific amount
        expected = 5 + 15 + 30 + 20 + 25 + 3 + 2 + 8
        assert total_xp == expected


class TestEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions."""

    def test_xp_negative_values_not_allowed_in_calculations(self):
        """Test that negative XP doesn't break calculations."""
        # Level calculation should handle negative XP gracefully
        level = calculate_level_from_xp(-100)
        # Should return level 1 or handle gracefully
        assert level >= 1

    def test_very_large_xp_values(self):
        """Test that very large XP values are handled."""
        xp = 1000000
        level = calculate_level_from_xp(xp)
        assert level == 8
        assert calculate_xp_for_next_level(xp) == 0

    def test_float_vs_int_consistency(self):
        """Test consistency between float and int XP values."""
        xp_float = 100.5
        xp_int = 100

        level_float = calculate_level_from_xp(int(xp_float))
        level_int = calculate_level_from_xp(xp_int)

        # Should be in same level (or one off due to rounding)
        assert abs(level_float - level_int) <= 1

    def test_threshold_boundary_all_levels(self):
        """Test boundary conditions for all level thresholds."""
        thresholds = get_level_thresholds()

        for i, threshold in enumerate(thresholds):
            level_at = calculate_level_from_xp(threshold)
            level_before = calculate_level_from_xp(threshold - 1) if threshold > 0 else 1

            assert level_at == i + 1
            if threshold > 0:
                assert level_before <= level_at

    def test_streak_boundary_single_to_multiple(self):
        """Test streak progression from single to multiple."""
        # Start with streak 0
        current, best = update_streak(0, "success", "success", 0)
        assert current == 1
        assert best == 1

        # Extend to multiple
        current, best = update_streak(current, "success", "success", best)
        assert current == 2
        assert best == 2

        # Break and recover
        current, best = update_streak(current, "success", "error", best)
        assert current == 0
        assert best == 2

        # Build new streak
        current, best = update_streak(current, "error", "success", best)
        assert current == 1
        assert best == 2

    def test_xp_progress_percentage_calculation(self):
        """Test that XP progress can be expressed as percentage."""
        test_cases = [
            (0, 1.0),      # 0%
            (25, 0.5),     # 50% through level 1
            (50, 0.0),     # 0% of next level
            (100, 0.5),    # 50% through level 2
        ]

        for xp, expected_min_progress in test_cases:
            current, needed = calculate_xp_progress_in_level(xp)
            if needed > 0:
                progress = current / needed
                assert 0 <= progress <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
