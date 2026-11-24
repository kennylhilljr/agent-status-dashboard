"""End-to-end tests: gamification fields are computed by the real collector pipeline.

Regression tests for issue #24: before the fix, track_agent() left xp at 0,
level at 1, achievements empty and strengths/weaknesses empty, and unknown
models fell back to Sonnet pricing without any warning.
"""

import logging

import pytest

import agent_metrics_collector
from agent_metrics_collector import AgentMetricsCollector, _calculate_cost
from xp_calculations import calculate_speed_bonus


@pytest.fixture
def collector(tmp_path):
    return AgentMetricsCollector(project_name="test-project", metrics_dir=tmp_path)


def _speed_bonus_total(collector, agent_name):
    """Sum the speed bonus actually earned, so assertions don't depend on timing."""
    return sum(
        calculate_speed_bonus(e["duration_seconds"])
        for e in collector.get_state()["events"]
        if e["agent_name"] == agent_name and e["status"] == "success"
    )


def test_track_agent_awards_xp_and_first_blood(collector):
    with collector.track_agent("coding", "AI-1", "claude-sonnet-4-5") as tracker:
        tracker.add_tokens(input_tokens=100, output_tokens=200)
        tracker.add_artifact("commit:abc123")

    profile = collector.get_state()["agents"]["coding"]
    # base 10 + speed bonus + commit 5 + streak 1
    assert profile["xp"] == 16 + _speed_bonus_total(collector, "coding")
    assert profile["level"] == 1
    assert "first_blood" in profile["achievements"]


def test_xp_accumulates_and_level_rises(collector):
    for i in range(3):
        with collector.track_agent("coding", f"AI-{i}", "claude-sonnet-4-5") as tracker:
            tracker.add_artifact(f"pr:#{i}:merged")
            tracker.add_artifact(f"pr:#{i + 10}:merged")

    profile = collector.get_state()["agents"]["coding"]
    # Each: base 10 + speed bonus + 2 * pr_merged 30 + streak (1, 2, 3)
    assert profile["xp"] == 70 * 3 + 6 + _speed_bonus_total(collector, "coding")
    # 216-246 XP is level 3 whatever the speed bonus
    assert profile["level"] == 3
    assert profile["achievements"].count("first_blood") == 1


def test_failure_earns_no_xp_and_recovery_bonus_applies(collector):
    with pytest.raises(RuntimeError):
        with collector.track_agent("coding", "AI-1", "claude-sonnet-4-5"):
            raise RuntimeError("boom")

    profile = collector.get_state()["agents"]["coding"]
    assert profile["xp"] == 0
    assert "first_blood" not in profile["achievements"]

    with collector.track_agent("coding", "AI-2", "claude-sonnet-4-5"):
        pass

    profile = collector.get_state()["agents"]["coding"]
    # base 10 + speed bonus + recovery 10 + streak 1
    assert profile["xp"] == 21 + _speed_bonus_total(collector, "coding")


def test_history_based_achievement_uses_event_log(collector):
    for i in range(5):
        with collector.track_agent("coding", f"AI-{i}", "claude-sonnet-4-5"):
            pass

    state = collector.get_state()
    # speed_demon needs the last 5 events from the log, not just the current one
    assert all(e["duration_seconds"] < 30 for e in state["events"])
    assert "speed_demon" in state["agents"]["coding"]["achievements"]


def test_strengths_and_weaknesses_are_populated(collector):
    for i in range(6):
        with collector.track_agent("coding", f"AI-{i}", "claude-sonnet-4-5"):
            pass

    profile = collector.get_state()["agents"]["coding"]
    assert "high_success_rate" in profile["strengths"]


def test_strengths_survive_when_agent_history_ages_out(collector):
    for i in range(6):
        with collector.track_agent("coding", f"AI-{i}", "claude-sonnet-4-5"):
            pass
    assert collector.get_state()["agents"]["coding"]["strengths"]

    # Push coding's events out of the capped event log with another agent
    state = collector.get_state()
    state["events"] = [e for e in state["events"] if e["agent_name"] != "coding"]
    collector.store.save(state)
    with collector.track_agent("linear", "AI-99", "claude-haiku-4-5"):
        pass

    assert "high_success_rate" in collector.get_state()["agents"]["coding"]["strengths"]


def test_strengths_kept_when_eviction_drops_agent_below_minimum(collector, monkeypatch):
    for i in range(5):
        with collector.track_agent("coding", f"AI-{i}", "claude-sonnet-4-5"):
            pass
    strengths = collector.get_state()["agents"]["coding"]["strengths"]
    assert strengths

    # With a 5-event cap, the next event evicts one of coding's five events.
    monkeypatch.setattr(collector.store, "MAX_EVENTS", 5)
    with collector.track_agent("linear", "AI-99", "claude-haiku-4-5"):
        pass

    state = collector.get_state()
    assert len(state["events"]) == 5
    assert state["agents"]["coding"]["strengths"] == strengths


def test_unknown_model_logs_warning_once(caplog, monkeypatch):
    monkeypatch.setattr(agent_metrics_collector, "_warned_unpriced_models", set())
    with caplog.at_level(logging.WARNING, logger="agent_metrics_collector"):
        cost = _calculate_cost("gpt-4o", 1000, 1000)
        _calculate_cost("gpt-4o", 1000, 1000)

    assert cost == pytest.approx(0.018)
    warnings = [r for r in caplog.records if "gpt-4o" in r.getMessage()]
    assert len(warnings) == 1


def test_known_model_does_not_warn(caplog):
    with caplog.at_level(logging.WARNING, logger="agent_metrics_collector"):
        _calculate_cost("claude-haiku-4-5", 1000, 1000)
    assert not caplog.records
