"""Achievement checking system for agent gamification.

This module provides pure functions for detecting when agents meet achievement
criteria. All functions are deterministic with no side effects, making them
easy to test and reason about.

Achievements (12 total):
1. first_blood - First successful invocation
2. century_club - 100 successful invocations
3. perfect_day - 10+ successes in one session, 0 own errors (checked when the session ends)
4. speed_demon - 5 consecutive completions under 30s
5. comeback_kid - Success immediately after 3+ consecutive errors
6. big_spender - Single invocation over $1.00
7. penny_pincher - 50+ successes at < $0.01 each
8. marathon - 100+ invocations in a single project
9. polyglot - Agent used across 5+ distinct ticket-key prefixes (e.g. AI, HS, CTX)
10. night_owl - Invocation started between 00:00-05:00 in the host's local timezone
11. streak_10 - 10 consecutive successes
12. streak_25 - 25 consecutive successes
"""

from datetime import UTC, datetime

from metrics import AgentEvent, AgentProfile


def check_first_blood(profile: AgentProfile) -> bool:
    """Check if agent has earned First Blood achievement.

    Awarded for the first successful invocation.

    Args:
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> profile = {"successful_invocations": 1, "achievements": []}
        >>> check_first_blood(profile)
        True
        >>> profile = {"successful_invocations": 0, "achievements": []}
        >>> check_first_blood(profile)
        False
        >>> profile = {"successful_invocations": 10, "achievements": ["first_blood"]}
        >>> check_first_blood(profile)
        False
    """
    return (
        profile["successful_invocations"] >= 1
        and "first_blood" not in profile["achievements"]
    )


def check_century_club(profile: AgentProfile) -> bool:
    """Check if agent has earned Century Club achievement.

    Awarded for 100 successful invocations.

    Args:
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> profile = {"successful_invocations": 100, "achievements": []}
        >>> check_century_club(profile)
        True
        >>> profile = {"successful_invocations": 99, "achievements": []}
        >>> check_century_club(profile)
        False
        >>> profile = {"successful_invocations": 150, "achievements": ["century_club"]}
        >>> check_century_club(profile)
        False
    """
    return (
        profile["successful_invocations"] >= 100
        and "century_club" not in profile["achievements"]
    )


FAILURE_STATUSES = ("error", "timeout", "blocked")


def is_perfect_day_eligible(
    successes: int, failures: int, session_status: str, profile: AgentProfile
) -> bool:
    """Decide Perfect Day from an agent's per-session outcome counts.

    Perfect Day is evaluated once, when the session ends: the agent needs at
    least 10 successful events in the session, none of its own failures in it,
    and the session must not have ended with status ``error``. Other agents'
    failures do not count.

    Args:
        successes: The agent's successful events in the session
        failures: The agent's failed (error/timeout/blocked) events in the session
        session_status: Final session status ("complete", "continue" or "error")
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> is_perfect_day_eligible(10, 0, "complete", {"achievements": []})
        True
        >>> is_perfect_day_eligible(10, 0, "continue", {"achievements": []})
        True
        >>> is_perfect_day_eligible(10, 0, "error", {"achievements": []})
        False
        >>> is_perfect_day_eligible(12, 1, "complete", {"achievements": []})
        False
        >>> is_perfect_day_eligible(9, 0, "complete", {"achievements": []})
        False
    """
    if "perfect_day" in profile["achievements"]:
        return False
    if session_status == "error":
        return False
    return successes >= 10 and failures == 0


def check_perfect_day(
    session_events: list[AgentEvent],
    agent_name: str,
    profile: AgentProfile,
    session_status: str = "complete",
) -> bool:
    """Check Perfect Day for a finished session from its event list.

    Only call this once the session has ended; ``check_all_achievements`` does
    not evaluate it per event. The collector uses ``is_perfect_day_eligible``
    with running counts so the capped event log cannot hide a failure.

    Args:
        session_events: All events of the finished session
        agent_name: Name of the agent to check
        profile: Agent's performance profile
        session_status: Final session status

    Returns:
        True if achievement should be awarded

    Examples:
        >>> events = [{"agent_name": "coding", "status": "success"} for _ in range(10)]
        >>> profile = {"achievements": []}
        >>> check_perfect_day(events, "coding", profile)
        True
        >>> events = [{"agent_name": "coding", "status": "success"} for _ in range(9)]
        >>> check_perfect_day(events, "coding", profile)
        False
        >>> events = [{"agent_name": "coding", "status": "success" if i < 10 else "error"} for i in range(11)]
        >>> check_perfect_day(events, "coding", profile)
        False
    """
    agent_events = [e for e in session_events if e["agent_name"] == agent_name]
    successes = sum(1 for e in agent_events if e["status"] == "success")
    failures = sum(1 for e in agent_events if e["status"] in FAILURE_STATUSES)
    return is_perfect_day_eligible(successes, failures, session_status, profile)


def check_speed_demon(recent_events: list[AgentEvent], profile: AgentProfile) -> bool:
    """Check if agent has earned Speed Demon achievement.

    Awarded for 5 consecutive completions under 30 seconds.

    Args:
        recent_events: List of recent events (chronological order, most recent last)
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> events = [{"status": "success", "duration_seconds": 25.0} for _ in range(5)]
        >>> profile = {"achievements": []}
        >>> check_speed_demon(events, profile)
        True
        >>> events = [{"status": "success", "duration_seconds": 35.0} for _ in range(5)]
        >>> check_speed_demon(events, profile)
        False
        >>> events = [{"status": "success", "duration_seconds": 25.0} for _ in range(4)]
        >>> check_speed_demon(events, profile)
        False
    """
    if "speed_demon" in profile["achievements"]:
        return False

    if len(recent_events) < 5:
        return False

    # Check last 5 events
    last_five = recent_events[-5:]

    # All must be successful and under 30 seconds
    return all(
        e["status"] == "success" and e["duration_seconds"] < 30
        for e in last_five
    )


def check_comeback_kid(recent_events: list[AgentEvent], profile: AgentProfile) -> bool:
    """Check if agent has earned Comeback Kid achievement.

    Awarded for success immediately after 3+ consecutive errors.

    Args:
        recent_events: List of recent events (chronological order, most recent last)
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> events = [
        ...     {"status": "error"},
        ...     {"status": "error"},
        ...     {"status": "error"},
        ...     {"status": "success"}
        ... ]
        >>> profile = {"achievements": []}
        >>> check_comeback_kid(events, profile)
        True
        >>> events = [{"status": "error"}, {"status": "error"}, {"status": "success"}]
        >>> check_comeback_kid(events, profile)
        False
    """
    if "comeback_kid" in profile["achievements"]:
        return False

    if len(recent_events) < 4:
        return False

    # Last event must be a success
    if recent_events[-1]["status"] != "success":
        return False

    # Count consecutive errors before the success
    error_count = 0
    for event in reversed(recent_events[:-1]):
        if event["status"] in ["error", "timeout", "blocked"]:
            error_count += 1
        else:
            break

    return error_count >= 3


def check_big_spender(event: AgentEvent, profile: AgentProfile) -> bool:
    """Check if agent has earned Big Spender achievement.

    Awarded for a single invocation costing over $1.00.

    Args:
        event: The current agent event
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> event = {"estimated_cost_usd": 1.50}
        >>> profile = {"achievements": []}
        >>> check_big_spender(event, profile)
        True
        >>> event = {"estimated_cost_usd": 0.99}
        >>> check_big_spender(event, profile)
        False
    """
    return (
        event["estimated_cost_usd"] > 1.00
        and "big_spender" not in profile["achievements"]
    )


def check_penny_pincher(all_events: list[AgentEvent], profile: AgentProfile) -> bool:
    """Check if agent has earned Penny Pincher achievement.

    Awarded for 50+ successful invocations with cost < $0.01 each.

    Args:
        all_events: List of all events for this agent
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> events = [{"status": "success", "estimated_cost_usd": 0.005} for _ in range(50)]
        >>> profile = {"achievements": []}
        >>> check_penny_pincher(events, profile)
        True
        >>> events = [{"status": "success", "estimated_cost_usd": 0.005} for _ in range(49)]
        >>> check_penny_pincher(events, profile)
        False
        >>> events = [{"status": "success", "estimated_cost_usd": 0.02} for _ in range(50)]
        >>> check_penny_pincher(events, profile)
        False
    """
    if "penny_pincher" in profile["achievements"]:
        return False

    cheap_successes = [
        e for e in all_events
        if e["status"] == "success" and e["estimated_cost_usd"] < 0.01
    ]

    return len(cheap_successes) >= 50


def check_marathon(profile: AgentProfile) -> bool:
    """Check if agent has earned Marathon Runner achievement.

    Awarded for 100+ invocations in a single project.

    Args:
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> profile = {"total_invocations": 100, "achievements": []}
        >>> check_marathon(profile)
        True
        >>> profile = {"total_invocations": 99, "achievements": []}
        >>> check_marathon(profile)
        False
    """
    return (
        profile["total_invocations"] >= 100
        and "marathon" not in profile["achievements"]
    )


def ticket_key_prefix(ticket_key: str) -> str:
    """Return the project prefix of a ticket key, or "" if it has none.

    Args:
        ticket_key: Ticket key such as "AI-12"

    Returns:
        The part before the first "-" (e.g. "AI"), or "" for keys without a
        nonempty prefix and suffix

    Examples:
        >>> ticket_key_prefix("AI-12")
        'AI'
        >>> ticket_key_prefix("CTX-3-b")
        'CTX'
        >>> ticket_key_prefix("AI")
        ''
        >>> ticket_key_prefix("-5")
        ''
    """
    if not isinstance(ticket_key, str):
        return ""
    prefix, sep, suffix = ticket_key.strip().partition("-")
    if not sep or not prefix.strip() or not suffix.strip():
        return ""
    return prefix.strip()


def check_polyglot(all_events: list[AgentEvent], profile: AgentProfile) -> bool:
    """Check if agent has earned Polyglot achievement.

    Awarded when the agent has worked tickets with 5+ distinct ticket-key
    prefixes (the project part before "-", e.g. AI, HS, CTX).

    Args:
        all_events: List of all events for this agent
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> events = [{"ticket_key": f"{p}-1"} for p in ["AI", "HS", "CTX", "OPS", "WEB"]]
        >>> profile = {"achievements": []}
        >>> check_polyglot(events, profile)
        True
        >>> events = [{"ticket_key": f"AI-{i}"} for i in range(5)]
        >>> check_polyglot(events, profile)
        False
    """
    if "polyglot" in profile["achievements"]:
        return False

    prefixes = {ticket_key_prefix(e.get("ticket_key", "")) for e in all_events}
    prefixes.discard("")

    return len(prefixes) >= 5


def check_night_owl(event: AgentEvent, profile: AgentProfile) -> bool:
    """Check if agent has earned Night Owl achievement.

    Awarded for an invocation started between 00:00 (inclusive) and 05:00
    (exclusive) in the host's local timezone. ``started_at`` is stored in UTC;
    naive timestamps are treated as UTC and converted to local time.

    Args:
        event: The current agent event
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> from datetime import datetime
        >>> local_2am = datetime(2026, 2, 14, 2, 30).astimezone()
        >>> check_night_owl({"started_at": local_2am.isoformat()}, {"achievements": []})
        True
        >>> local_noon = datetime(2026, 2, 14, 12, 30).astimezone()
        >>> check_night_owl({"started_at": local_noon.isoformat()}, {"achievements": []})
        False
    """
    if "night_owl" in profile["achievements"]:
        return False

    try:
        timestamp = event["started_at"]
        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1] + "+00:00"
        dt = datetime.fromisoformat(timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        local = dt.astimezone()
    except (ValueError, AttributeError, TypeError, KeyError, OverflowError, OSError):
        return False

    return 0 <= local.hour < 5


def check_streak_10(profile: AgentProfile) -> bool:
    """Check if agent has earned On Fire (streak_10) achievement.

    Awarded for 10 consecutive successful invocations.

    Args:
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> profile = {"current_streak": 10, "achievements": []}
        >>> check_streak_10(profile)
        True
        >>> profile = {"current_streak": 9, "achievements": []}
        >>> check_streak_10(profile)
        False
    """
    return (
        profile["current_streak"] >= 10
        and "streak_10" not in profile["achievements"]
    )


def check_streak_25(profile: AgentProfile) -> bool:
    """Check if agent has earned Unstoppable (streak_25) achievement.

    Awarded for 25 consecutive successful invocations.

    Args:
        profile: Agent's performance profile

    Returns:
        True if achievement should be awarded

    Examples:
        >>> profile = {"current_streak": 25, "achievements": []}
        >>> check_streak_25(profile)
        True
        >>> profile = {"current_streak": 24, "achievements": []}
        >>> check_streak_25(profile)
        False
    """
    return (
        profile["current_streak"] >= 25
        and "streak_25" not in profile["achievements"]
    )


def check_all_achievements(
    profile: AgentProfile,
    current_event: AgentEvent,
    all_agent_events: list[AgentEvent],
    session_events: list[AgentEvent],
) -> list[str]:
    """Check all achievement conditions and return newly earned achievements.

    This is the main function that should be called after each agent invocation
    to detect and award new achievements. Perfect Day is not checked here: it
    depends on the whole session, so it is evaluated when the session ends
    (see ``is_perfect_day_eligible``).

    Args:
        profile: Agent's current performance profile
        current_event: The event that just completed
        all_agent_events: All historical events for this agent
        session_events: All events in the current session (unused; kept for
            backward compatibility)

    Returns:
        List of achievement IDs that were just earned (not already in profile)

    Examples:
        >>> profile = {
        ...     "agent_name": "coding",
        ...     "successful_invocations": 1,
        ...     "total_invocations": 1,
        ...     "current_streak": 1,
        ...     "achievements": []
        ... }
        >>> event = {"agent_name": "coding", "status": "success", "estimated_cost_usd": 0.01}
        >>> check_all_achievements(profile, event, [event], [event])
        ['first_blood']
    """
    newly_earned = []

    # Check each achievement
    if check_first_blood(profile):
        newly_earned.append("first_blood")

    if check_century_club(profile):
        newly_earned.append("century_club")

    if check_speed_demon(all_agent_events, profile):
        newly_earned.append("speed_demon")

    if check_comeback_kid(all_agent_events, profile):
        newly_earned.append("comeback_kid")

    if check_big_spender(current_event, profile):
        newly_earned.append("big_spender")

    if check_penny_pincher(all_agent_events, profile):
        newly_earned.append("penny_pincher")

    if check_marathon(profile):
        newly_earned.append("marathon")

    if check_polyglot(all_agent_events, profile):
        newly_earned.append("polyglot")

    if check_night_owl(current_event, profile):
        newly_earned.append("night_owl")

    if check_streak_10(profile):
        newly_earned.append("streak_10")

    if check_streak_25(profile):
        newly_earned.append("streak_25")

    return newly_earned


def get_achievement_name(achievement_id: str) -> str:
    """Get the display name for an achievement ID.

    Args:
        achievement_id: Achievement identifier

    Returns:
        Human-readable achievement name

    Raises:
        ValueError: If achievement_id is unknown

    Examples:
        >>> get_achievement_name("first_blood")
        'First Blood'
        >>> get_achievement_name("century_club")
        'Century Club'
        >>> get_achievement_name("unknown")
        Traceback (most recent call last):
            ...
        ValueError: Unknown achievement ID: unknown
    """
    names = {
        "first_blood": "First Blood",
        "century_club": "Century Club",
        "perfect_day": "Perfect Day",
        "speed_demon": "Speed Demon",
        "comeback_kid": "Comeback Kid",
        "big_spender": "Big Spender",
        "penny_pincher": "Penny Pincher",
        "marathon": "Marathon Runner",
        "polyglot": "Polyglot",
        "night_owl": "Night Owl",
        "streak_10": "On Fire",
        "streak_25": "Unstoppable",
    }

    if achievement_id not in names:
        raise ValueError(f"Unknown achievement ID: {achievement_id}")

    return names[achievement_id]


def get_achievement_description(achievement_id: str) -> str:
    """Get the description for an achievement ID.

    Args:
        achievement_id: Achievement identifier

    Returns:
        Achievement description/condition

    Raises:
        ValueError: If achievement_id is unknown

    Examples:
        >>> get_achievement_description("first_blood")
        'First successful invocation'
        >>> get_achievement_description("century_club")
        '100 successful invocations'
    """
    descriptions = {
        "first_blood": "First successful invocation",
        "century_club": "100 successful invocations",
        "perfect_day": "10+ successes in one session, 0 own errors (checked at session end)",
        "speed_demon": "5 consecutive completions under 30s",
        "comeback_kid": "Success immediately after 3+ consecutive errors",
        "big_spender": "Single invocation over $1.00",
        "penny_pincher": "50+ successes at < $0.01 each",
        "marathon": "100+ invocations in a single project",
        "polyglot": "Agent used across 5+ distinct ticket-key prefixes",
        "night_owl": "Invocation between 00:00-05:00 host local time",
        "streak_10": "10 consecutive successes",
        "streak_25": "25 consecutive successes",
    }

    if achievement_id not in descriptions:
        raise ValueError(f"Unknown achievement ID: {achievement_id}")

    return descriptions[achievement_id]


def get_all_achievement_ids() -> list[str]:
    """Get list of all valid achievement IDs.

    Returns:
        List of all achievement identifiers

    Examples:
        >>> ids = get_all_achievement_ids()
        >>> len(ids)
        12
        >>> "first_blood" in ids
        True
    """
    return [
        "first_blood",
        "century_club",
        "perfect_day",
        "speed_demon",
        "comeback_kid",
        "big_spender",
        "penny_pincher",
        "marathon",
        "polyglot",
        "night_owl",
        "streak_10",
        "streak_25",
    ]
