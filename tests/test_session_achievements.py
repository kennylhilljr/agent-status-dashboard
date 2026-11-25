"""Perfect Day is awarded by the collector at end_session (issue #29)."""

import pytest

from agent_metrics_collector import AgentMetricsCollector


@pytest.fixture
def collector(tmp_path):
    return AgentMetricsCollector(project_name="test-project", metrics_dir=tmp_path)


def _run(collector, session_id, agent="coding", n=1, fail=False, status=None):
    for i in range(n):
        if fail or status is not None:
            try:
                with collector.track_agent(agent, f"AI-{i}", "claude-sonnet-4-5", session_id) as t:
                    if status is not None:
                        t.status = status
                    if fail:
                        raise RuntimeError("boom")
            except RuntimeError:
                pass
        else:
            with collector.track_agent(agent, f"AI-{i}", "claude-sonnet-4-5", session_id):
                pass


def _achievements(collector, agent="coding"):
    return collector.get_state()["agents"][agent]["achievements"]


def test_not_awarded_before_session_ends(collector):
    sid = collector.start_session()
    _run(collector, sid, n=10)
    assert "perfect_day" not in _achievements(collector)

    collector.end_session(sid, status="complete")
    assert _achievements(collector).count("perfect_day") == 1


def test_awarded_on_continue(collector):
    sid = collector.start_session()
    _run(collector, sid, n=10)
    collector.end_session(sid, status="continue")
    assert "perfect_day" in _achievements(collector)


def test_error_session_disqualifies(collector):
    sid = collector.start_session()
    _run(collector, sid, n=10)
    collector.end_session(sid, status="error")
    assert "perfect_day" not in _achievements(collector)


def test_fewer_than_ten_successes(collector):
    sid = collector.start_session()
    _run(collector, sid, n=9)
    collector.end_session(sid, status="complete")
    assert "perfect_day" not in _achievements(collector)


def test_late_own_failure_disqualifies(collector):
    sid = collector.start_session()
    _run(collector, sid, n=10)
    _run(collector, sid, fail=True)
    collector.end_session(sid, status="complete")
    assert "perfect_day" not in _achievements(collector)


@pytest.mark.parametrize("status", ["timeout", "blocked"])
def test_timeout_and_blocked_count_as_failures(collector, status):
    sid = collector.start_session()
    _run(collector, sid, n=10)
    _run(collector, sid, status=status)
    collector.end_session(sid, status="complete")
    assert "perfect_day" not in _achievements(collector)


def test_other_agents_failures_do_not_disqualify(collector):
    sid = collector.start_session()
    _run(collector, sid, n=10)
    _run(collector, sid, agent="github", fail=True)
    collector.end_session(sid, status="complete")
    assert "perfect_day" in _achievements(collector)
    assert "perfect_day" not in _achievements(collector, "github")


def test_sessions_are_counted_separately(collector):
    first = collector.start_session()
    _run(collector, first, n=6)
    collector.end_session(first, status="complete")
    second = collector.start_session()
    _run(collector, second, n=6)
    collector.end_session(second, status="complete")
    assert "perfect_day" not in _achievements(collector)


def test_concurrent_sessions_isolated(collector):
    good = collector.start_session()
    bad = collector.start_session()
    _run(collector, good, n=10)
    _run(collector, bad, n=10)
    _run(collector, bad, fail=True)
    collector.end_session(bad, status="complete")
    assert "perfect_day" not in _achievements(collector)
    collector.end_session(good, status="complete")
    assert "perfect_day" in _achievements(collector)


def test_evicted_failure_still_disqualifies(collector, monkeypatch):
    monkeypatch.setattr(collector.store, "MAX_EVENTS", 3)
    sid = collector.start_session()
    _run(collector, sid, fail=True)
    _run(collector, sid, n=10)
    assert all(e["status"] == "success" for e in collector.get_state()["events"])
    collector.end_session(sid, status="complete")
    assert "perfect_day" not in _achievements(collector)


def test_evicted_successes_still_count(collector, monkeypatch):
    monkeypatch.setattr(collector.store, "MAX_EVENTS", 3)
    sid = collector.start_session()
    _run(collector, sid, n=10)
    collector.end_session(sid, status="complete")
    assert "perfect_day" in _achievements(collector)


def test_preserves_existing_badges_and_xp_and_no_duplicate(collector):
    sid = collector.start_session()
    _run(collector, sid, n=10)
    before = collector.get_state()["agents"]["coding"]
    collector.end_session(sid, status="complete")
    after = collector.get_state()["agents"]["coding"]
    assert after["xp"] == before["xp"]
    assert after["achievements"] == before["achievements"] + ["perfect_day"]

    again = collector.start_session()
    _run(collector, again, n=10)
    collector.end_session(again, status="complete")
    assert _achievements(collector).count("perfect_day") == 1


def test_session_summary_still_saved(collector):
    sid = collector.start_session()
    _run(collector, sid, n=10)
    collector.end_session(sid, status="complete")
    state = collector.get_state()
    assert state["total_sessions"] == 1
    assert state["sessions"][0]["session_id"] == sid
