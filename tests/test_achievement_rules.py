"""Rule semantics for night_owl, polyglot and perfect_day (issue #29).

Uses the collector's private loader for the root ``achievements.py`` because
``scripts/achievements.py`` shares the module name.
"""

import os
import time

import pytest

from agent_metrics_collector import _load_achievement_rules

rules = _load_achievement_rules()


@pytest.fixture
def host_tz():
    """Set the host timezone for one test and restore it afterwards."""
    original = os.environ.get("TZ")

    def set_tz(name):
        os.environ["TZ"] = name
        time.tzset()

    yield set_tz
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


def _night_owl(started_at, achievements=None):
    return rules.check_night_owl({"started_at": started_at}, {"achievements": achievements or []})


# --- night_owl: evaluated in host local time --------------------------------


def test_night_owl_utc_night_is_not_local_night(host_tz):
    # 02:30 UTC is 21:30 the previous day in New York (EST)
    host_tz("America/New_York")
    assert _night_owl("2026-02-14T02:30:00Z") is False


def test_night_owl_local_night_from_utc_daytime(host_tz):
    # 07:30 UTC is 02:30 in New York (EST)
    host_tz("America/New_York")
    assert _night_owl("2026-02-14T07:30:00Z") is True


@pytest.mark.parametrize(
    ("started_at", "expected"),
    [
        ("2026-02-14T04:59:59Z", False),  # 23:59:59 local, previous day
        ("2026-02-14T05:00:00Z", True),  # 00:00 local, inclusive
        ("2026-02-14T09:59:59Z", True),  # 04:59:59 local
        ("2026-02-14T10:00:00Z", False),  # 05:00 local, exclusive
    ],
)
def test_night_owl_window_boundaries(host_tz, started_at, expected):
    host_tz("America/New_York")
    assert _night_owl(started_at) is expected


def test_night_owl_naive_timestamp_is_utc(host_tz):
    host_tz("America/New_York")
    assert _night_owl("2026-02-14T07:30:00") is True
    assert _night_owl("2026-02-14T02:30:00") is False


def test_night_owl_explicit_offset(host_tz):
    host_tz("America/New_York")
    # 09:30+05:00 is 04:30 UTC, 23:30 New York
    assert _night_owl("2026-02-14T09:30:00+05:00") is False
    # 12:30+05:00 is 07:30 UTC, 02:30 New York
    assert _night_owl("2026-02-14T12:30:00+05:00") is True


def test_night_owl_follows_dst(host_tz):
    host_tz("America/New_York")
    # Winter: UTC-5, 05:30 UTC is 00:30 local
    assert _night_owl("2026-01-15T05:30:00Z") is True
    # Summer: UTC-4, 05:30 UTC is 01:30 local; 08:30 UTC is 04:30 local
    assert _night_owl("2026-07-15T08:30:00Z") is True
    # Summer: 09:30 UTC is 05:30 local
    assert _night_owl("2026-07-15T09:30:00Z") is False


def test_night_owl_utc_host(host_tz):
    host_tz("UTC")
    assert _night_owl("2026-02-14T02:30:00Z") is True
    assert _night_owl("2026-02-14T07:30:00Z") is False


@pytest.mark.parametrize("bad", ["not-a-date", "", None, 12345])
def test_night_owl_invalid_timestamp(host_tz, bad):
    host_tz("UTC")
    assert _night_owl(bad) is False


def test_night_owl_already_earned(host_tz):
    host_tz("UTC")
    assert _night_owl("2026-02-14T02:30:00Z", ["night_owl"]) is False


# --- polyglot: distinct ticket-key prefixes ---------------------------------


def _polyglot(keys, achievements=None):
    events = [{"ticket_key": k} for k in keys]
    return rules.check_polyglot(events, {"achievements": achievements or []})


def test_polyglot_five_tickets_same_prefix_fails():
    assert _polyglot([f"AI-{i}" for i in range(5)]) is False


def test_polyglot_four_prefixes_fails():
    assert _polyglot(["AI-1", "HS-2", "CTX-3", "OPS-4", "AI-5", "HS-6"]) is False


def test_polyglot_five_prefixes_succeeds():
    assert _polyglot(["AI-1", "HS-2", "CTX-3", "OPS-4", "WEB-5"]) is True


def test_polyglot_ignores_malformed_keys():
    keys = ["AI-1", "HS-2", "CTX-3", "OPS-4", "", "   ", "NOPREFIX", "-7", "WEB-", None]
    assert _polyglot(keys) is False


def test_polyglot_already_earned():
    assert _polyglot(["AI-1", "HS-2", "CTX-3", "OPS-4", "WEB-5"], ["polyglot"]) is False


def test_ticket_key_prefix():
    assert rules.ticket_key_prefix("AI-12") == "AI"
    assert rules.ticket_key_prefix(" HS-3 ") == "HS"
    assert rules.ticket_key_prefix("CTX-3-b") == "CTX"
    assert rules.ticket_key_prefix("AI") == ""
    assert rules.ticket_key_prefix("-5") == ""
    assert rules.ticket_key_prefix("AI-") == ""


# --- perfect_day: not evaluated per event -----------------------------------


def _profile(**overrides):
    profile = {
        "agent_name": "coding",
        "successful_invocations": 10,
        "total_invocations": 10,
        "current_streak": 10,
        "achievements": ["first_blood", "streak_10"],
    }
    profile.update(overrides)
    return profile


def test_check_all_achievements_never_awards_perfect_day():
    events = [
        {
            "event_id": str(i),
            "agent_name": "coding",
            "status": "success",
            "estimated_cost_usd": 0.5,
            "duration_seconds": 60.0,
            "ticket_key": "AI-1",
            "started_at": "2026-02-14T12:00:00Z",
        }
        for i in range(10)
    ]
    earned = rules.check_all_achievements(_profile(), events[-1], events, events)
    assert "perfect_day" not in earned


@pytest.mark.parametrize(
    ("successes", "failures", "status", "expected"),
    [
        (10, 0, "complete", True),
        (10, 0, "continue", True),
        (10, 0, "error", False),
        (9, 0, "complete", False),
        (15, 1, "complete", False),
    ],
)
def test_is_perfect_day_eligible(successes, failures, status, expected):
    assert rules.is_perfect_day_eligible(successes, failures, status, _profile()) is expected


def test_perfect_day_not_awarded_twice():
    profile = _profile(achievements=["perfect_day"])
    assert rules.is_perfect_day_eligible(10, 0, "complete", profile) is False


def test_check_perfect_day_ignores_other_agents_failures():
    events = [{"agent_name": "coding", "status": "success"} for _ in range(10)]
    events.append({"agent_name": "github", "status": "error"})
    assert rules.check_perfect_day(events, "coding", {"achievements": []}) is True
    assert rules.check_perfect_day(events, "coding", {"achievements": []}, "error") is False


def test_check_perfect_day_late_failure():
    events = [{"agent_name": "coding", "status": "success"} for _ in range(10)]
    events.append({"agent_name": "coding", "status": "timeout"})
    assert rules.check_perfect_day(events, "coding", {"achievements": []}) is False


# --- descriptions ------------------------------------------------------------


def test_descriptions_match_new_rules():
    from scripts import achievements as cli

    for desc in (
        rules.get_achievement_description("polyglot"),
        cli.ACHIEVEMENT_DESCRIPTIONS["polyglot"],
    ):
        assert "prefix" in desc
    for desc in (
        rules.get_achievement_description("night_owl"),
        cli.ACHIEVEMENT_DESCRIPTIONS["night_owl"],
    ):
        assert "local" in desc
    for desc in (
        rules.get_achievement_description("perfect_day"),
        cli.ACHIEVEMENT_DESCRIPTIONS["perfect_day"],
    ):
        assert "session end" in desc
