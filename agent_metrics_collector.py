"""AgentMetricsCollector - Core collector for tracking agent delegations.

This module provides the AgentMetricsCollector class which:
- Manages session lifecycle (start_session, end_session)
- Provides track_agent() context manager for tracking agent delegations
- Records AgentEvent objects with automatic token/cost/duration calculation
- Integrates with MetricsStore for persistence
- Handles both success and failure cases gracefully

Usage:
    collector = AgentMetricsCollector(project_name="my-project")

    # Start a session
    session_id = collector.start_session(session_type="initializer")

    # Track an agent delegation
    with collector.track_agent("coding", "AI-46", "claude-sonnet-4-5") as tracker:
        # Do work...
        tracker.add_tokens(input_tokens=1000, output_tokens=2000)
        tracker.add_artifact("file:agent_metrics_collector.py")

    # End the session
    collector.end_session(session_id, status="complete")
"""

import contextlib
import importlib.util
import logging
import posixpath
import re
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from metrics import AgentEvent, AgentProfile, DashboardState, SessionSummary
from metrics_store import MetricsStore
from strengths_weaknesses import (
    calculate_agent_percentiles,
    calculate_rolling_window_stats,
    detect_strengths,
    detect_weaknesses,
)
from xp_calculations import (
    calculate_level_from_xp,
    calculate_total_xp_for_success,
    calculate_xp_for_contribution_type,
)

logger = logging.getLogger(__name__)


def _load_achievement_rules():
    """Load the root ``achievements.py`` under a private module name.

    ``scripts/achievements.py`` (the CLI renderer) shares the module name
    ``achievements``. Callers that put ``scripts/`` on ``sys.path`` would get the
    wrong module from a plain import, and a plain import here would shadow theirs.

    Returns:
        The loaded achievement rules module
    """
    name = "_agent_metrics_achievement_rules"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / "achievements.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_achievement_rules = _load_achievement_rules()
check_all_achievements = _achievement_rules.check_all_achievements
is_perfect_day_eligible = _achievement_rules.is_perfect_day_eligible
_FAILURE_STATUSES = _achievement_rules.FAILURE_STATUSES

# Model pricing (USD per 1000 tokens)
MODEL_PRICING = {
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5": {"input": 0.0008, "output": 0.004},
    "claude-sonnet-3-5": {"input": 0.003, "output": 0.015},
}

# Pricing used when a model is not in MODEL_PRICING (Sonnet rates)
DEFAULT_PRICING = {"input": 0.003, "output": 0.015}

# Models already warned about, so an unpriced model logs once per process
_warned_unpriced_models: set[str] = set()

# Artifact prefix + keyword -> (profile counter, XP contribution type or None).
# The keyword must equal the artifact's status field ("pr:<id>:merged", or the
# legacy "pr:merged:<id>"); see _artifact_status. It is never a substring match.
# "file:" artifacts are parsed structurally in _update_agent_profile instead.
_ARTIFACT_RULES: list[tuple[str, str | None, str, str | None]] = [
    ("commit:", None, "commits_made", "commit"),
    ("pr:", "created", "prs_created", "pr_created"),
    ("pr:", "merged", "prs_merged", "pr_merged"),
    ("issue:", "created", "issues_created", "issue_created"),
    ("issue:", "completed", "issues_completed", "ticket_completed"),
    ("message:", None, "messages_sent", None),
    ("review:", None, "reviews_completed", None),
]
_ARTIFACT_STATUSES = frozenset(k for _, k, _, _ in _ARTIFACT_RULES if k is not None)


# Newly created files that count as tests_written (20 XP instead of file_created XP)
_TEST_FILE_SUFFIXES = (
    "_test.py",
    "_test.go",
    ".test.js",
    ".test.jsx",
    ".test.ts",
    ".test.tsx",
    ".spec.js",
    ".spec.jsx",
    ".spec.ts",
    ".spec.tsx",
)
_TEST_DIRS = {"tests", "test", "__tests__"}


def _is_test_file_path(path: str) -> bool:
    """Return True if ``path`` looks like a test file.

    Matches ``test_*.py``, ``*_test.py``, ``*_test.go``, ``*.test.{js,jsx,ts,tsx}``,
    ``*.spec.{js,jsx,ts,tsx}``, or any file under a ``tests/``, ``test/`` or
    ``__tests__/`` directory.

    Args:
        path: File path from a ``file:<path>:created`` artifact

    Returns:
        True if the path is a test file
    """
    parts = [part for part in path.replace("\\", "/").split("/") if part]
    if not parts:
        return False
    name = parts[-1]
    if name.startswith("test_") and name.endswith(".py") and len(name) > len("test_.py"):
        return True
    if any(name.endswith(suffix) and len(name) > len(suffix) for suffix in _TEST_FILE_SUFFIXES):
        return True
    return any(part in _TEST_DIRS for part in parts[:-1])


_FILE_ACTION_RE = re.compile(r"^[a-z_]+$")


def _parse_file_artifact(artifact: str) -> tuple[str, str | None]:
    """Split a ``file:`` artifact into (path, action).

    Accepts ``file:<path>:<action>`` (the artifact detector's format),
    ``file:created:<path>`` / ``file:modified:<path>`` (legacy, action first)
    and ``file:<path>`` (no action). The action is a whole field, never a
    substring of the path. A trailing lowercase word field is always taken
    as the action; the legacy form is used only otherwise.

    Args:
        artifact: Artifact string starting with ``file:``

    Returns:
        (path, action); action is None when the artifact has no action field
    """
    rest = artifact[len("file:") :]
    # A trailing action-shaped field wins (detector format)
    path, sep, action = rest.rpartition(":")
    if sep and path and _FILE_ACTION_RE.match(action):
        return path, action
    # Legacy action-first format
    head, sep, tail = rest.partition(":")
    if sep and head in ("created", "modified") and tail:
        return tail, head
    return rest, None


def _artifact_status(artifact: str) -> str | None:
    """Return the status field of a ``<kind>:<id>:<status>`` artifact.

    The detector format puts the status last (``pr:#7:merged``); the legacy
    format puts it first (``pr:created:#7``). As with ``file:`` artifacts, a
    trailing status-shaped field wins and the legacy form is used only
    otherwise. The status is a whole field, never a substring of the id.
    Artifacts with fewer than three fields (``commit:abc123``) have none.

    Args:
        artifact: Artifact string such as ``pr:12:created``

    Returns:
        The status field, or None when the artifact has none
    """
    if artifact.count(":") < 2:
        return None
    status = artifact.rsplit(":", 1)[1]
    if _FILE_ACTION_RE.match(status):
        return status
    legacy = artifact.split(":", 2)[1]
    if legacy in _ARTIFACT_STATUSES:
        return legacy
    return None


def _normalize_file_path(path: str) -> str:
    """Normalize an artifact path so equivalent spellings compare equal.

    Args:
        path: File path from an artifact

    Returns:
        Normalized POSIX-style path
    """
    return posixpath.normpath(path.replace("\\", "/"))


def _created_test_file(artifact: str) -> str | None:
    """Return the normalized path if ``artifact`` records a newly created test file.

    Args:
        artifact: Artifact string

    Returns:
        The test file path, or None if the artifact is not a created test file
    """
    if not artifact.startswith("file:"):
        return None
    path, action = _parse_file_artifact(artifact)
    if action != "created" or not path:
        return None
    # Normalize first so "tests/../src/app.py" is classified as "src/app.py"
    normalized = _normalize_file_path(path)
    if not _is_test_file_path(normalized):
        return None
    return normalized


class AgentTracker:
    """Context manager helper for tracking a single agent delegation.

    This is yielded by track_agent() and allows the caller to:
    - Add token counts
    - Add artifacts produced
    - The tracker automatically records the event on exit
    """

    def __init__(
        self,
        event_id: str,
        agent_name: str,
        session_id: str,
        ticket_key: str,
        model_used: str,
        started_at: str,
        start_time: float | None = None,
    ):
        """Initialize tracker.

        Args:
            event_id: Unique event identifier
            agent_name: Name of the agent
            session_id: Parent session ID
            ticket_key: Linear ticket key
            model_used: Model identifier
            started_at: ISO 8601 start timestamp
            start_time: Epoch seconds (time.time()) when the work began; defaults to now
        """
        self.event_id = event_id
        self.agent_name = agent_name
        self.session_id = session_id
        self.ticket_key = ticket_key
        self.model_used = model_used
        self.started_at = started_at
        self.start_time = time.time() if start_time is None else start_time

        # Accumulated data
        self.input_tokens = 0
        self.output_tokens = 0
        self.artifacts: list[str] = []
        self.error_message = ""
        self.status: Literal["success", "error", "timeout", "blocked"] = "success"

    def add_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Add token counts to this event.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def add_artifact(self, artifact: str) -> None:
        """Add an artifact to this event.

        Artifacts are strings like:
        - "file:src/foo.py"
        - "commit:abc123"
        - "pr:#42"
        - "issue:AI-12"

        Args:
            artifact: Artifact identifier
        """
        self.artifacts.append(artifact)

    def set_error(self, error_message: str) -> None:
        """Mark this event as an error.

        Args:
            error_message: Error description
        """
        self.status = "error"
        self.error_message = error_message

    def finalize(self) -> AgentEvent:
        """Finalize the event and return the AgentEvent object.

        Returns:
            Complete AgentEvent with all fields populated
        """
        ended_at = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        duration_seconds = time.time() - self.start_time

        # Calculate cost
        total_tokens = self.input_tokens + self.output_tokens
        estimated_cost_usd = _calculate_cost(
            self.model_used,
            self.input_tokens,
            self.output_tokens
        )

        event: AgentEvent = {
            "event_id": self.event_id,
            "agent_name": self.agent_name,
            "session_id": self.session_id,
            "ticket_key": self.ticket_key,
            "started_at": self.started_at,
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "status": self.status,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "artifacts": self.artifacts,
            "error_message": self.error_message,
            "model_used": self.model_used,
        }

        return event


def _calculate_cost(model_used: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated cost in USD for token usage.

    Args:
        model_used: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in USD
    """
    pricing = MODEL_PRICING.get(model_used)
    if pricing is None:
        # Unknown model: fall back to Sonnet rates, but say so, because the
        # resulting cost is only an estimate for non-Claude models.
        if model_used not in _warned_unpriced_models:
            _warned_unpriced_models.add(model_used)
            logger.warning(
                "No pricing for model %r; estimating cost with default Sonnet rates. "
                "Add it to MODEL_PRICING for accurate cost totals.",
                model_used,
            )
        pricing = DEFAULT_PRICING

    # Cost per 1000 tokens
    input_cost = (input_tokens / 1000.0) * pricing["input"]
    output_cost = (output_tokens / 1000.0) * pricing["output"]

    return input_cost + output_cost


def _create_empty_profile(agent_name: str) -> AgentProfile:
    """Create an empty AgentProfile for a new agent.

    Args:
        agent_name: Name of the agent

    Returns:
        Empty AgentProfile with all counters at zero
    """
    now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"

    profile: AgentProfile = {
        "agent_name": agent_name,
        "total_invocations": 0,
        "successful_invocations": 0,
        "failed_invocations": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "total_duration_seconds": 0.0,
        "commits_made": 0,
        "prs_created": 0,
        "prs_merged": 0,
        "files_created": 0,
        "files_modified": 0,
        "lines_added": 0,
        "lines_removed": 0,
        "tests_written": 0,
        "issues_created": 0,
        "issues_completed": 0,
        "messages_sent": 0,
        "reviews_completed": 0,
        "success_rate": 0.0,
        "avg_duration_seconds": 0.0,
        "avg_tokens_per_call": 0.0,
        "cost_per_success_usd": 0.0,
        "xp": 0,
        "level": 1,
        "current_streak": 0,
        "best_streak": 0,
        "achievements": [],
        "strengths": [],
        "weaknesses": [],
        "recent_events": [],
        "last_error": "",
        "last_active": now,
    }

    return profile


def _update_agent_profile(
    profile: AgentProfile,
    event: AgentEvent,
    all_events: list[AgentEvent] | None = None,
) -> AgentProfile:
    """Update an agent profile with a new event.

    Updates counters, derived metrics, streaks, XP, level and achievements.

    Args:
        profile: Existing agent profile
        event: New event to incorporate
        all_events: Full event log (may already include ``event``). Used for
            achievements that look at history; if None, only ``event`` is used.
            The store caps this log, so history-based achievements only see
            retained events (they can be missed for sparse agents, never
            awarded wrongly from missing data).

    Returns:
        Updated agent profile
    """
    # A previous invocation failed iff there was one and the streak is broken
    previous_status = (
        "error"
        if profile["total_invocations"] > 0 and profile["current_streak"] == 0
        else "success"
    )

    # Update counters
    profile["total_invocations"] += 1

    if event["status"] == "success":
        profile["successful_invocations"] += 1
        profile["current_streak"] += 1
        if profile["current_streak"] > profile["best_streak"]:
            profile["best_streak"] = profile["current_streak"]
    else:
        profile["failed_invocations"] += 1
        profile["current_streak"] = 0
        profile["last_error"] = event["error_message"]

    profile["total_tokens"] += event["total_tokens"]
    profile["total_cost_usd"] += event["estimated_cost_usd"]
    profile["total_duration_seconds"] += event["duration_seconds"]

    # Update artifact counters based on artifacts (first matching rule wins).
    # A newly created test file counts as tests_written and earns test_written
    # XP instead of file_created XP; repeats of it within one event count once.
    contribution_xp = 0
    seen_test_files: set[str] = set()
    for artifact in event["artifacts"]:
        test_file = _created_test_file(artifact)
        if test_file is not None:
            if test_file not in seen_test_files:
                seen_test_files.add(test_file)
                profile["files_created"] += 1
                profile["tests_written"] = profile.get("tests_written", 0) + 1
                contribution_xp += calculate_xp_for_contribution_type("test_written")
            continue
        if artifact.startswith("file:"):
            # Match the parsed action field, never a substring of the path
            _, action = _parse_file_artifact(artifact)
            if action == "created":
                profile["files_created"] += 1
                contribution_xp += calculate_xp_for_contribution_type("file_created")
            elif action == "modified":
                profile["files_modified"] += 1
                contribution_xp += calculate_xp_for_contribution_type("file_modified")
            continue
        status = _artifact_status(artifact)
        for prefix, keyword, counter, contribution in _ARTIFACT_RULES:
            if artifact.startswith(prefix) and (keyword is None or status == keyword):
                profile[counter] += 1
                if contribution is not None:
                    contribution_xp += calculate_xp_for_contribution_type(contribution)
                break

    # Update derived metrics
    if profile["total_invocations"] > 0:
        profile["success_rate"] = profile["successful_invocations"] / profile["total_invocations"]
        profile["avg_duration_seconds"] = profile["total_duration_seconds"] / profile["total_invocations"]
        profile["avg_tokens_per_call"] = profile["total_tokens"] / profile["total_invocations"]

    if profile["successful_invocations"] > 0:
        profile["cost_per_success_usd"] = profile["total_cost_usd"] / profile["successful_invocations"]

    # Update recent events (keep last 20)
    profile["recent_events"].append(event["event_id"])
    if len(profile["recent_events"]) > 20:
        profile["recent_events"] = profile["recent_events"][-20:]

    profile["last_active"] = event["ended_at"]

    # XP and level (only successful invocations earn XP)
    if event["status"] == "success":
        profile["xp"] += calculate_total_xp_for_success(
            duration_seconds=event["duration_seconds"],
            current_streak=profile["current_streak"],
            previous_status=previous_status,
            contribution_xp=contribution_xp,
        )
    profile["level"] = calculate_level_from_xp(profile["xp"])

    # Achievements
    events = list(all_events) if all_events is not None else []
    if not any(e["event_id"] == event["event_id"] for e in events):
        events.append(event)
    agent_events = [e for e in events if e["agent_name"] == event["agent_name"]]
    session_events = [e for e in events if e["session_id"] == event["session_id"]]
    for achievement_id in check_all_achievements(profile, event, agent_events, session_events):
        if achievement_id not in profile["achievements"]:
            profile["achievements"].append(achievement_id)

    return profile


def _refresh_strengths_weaknesses(
    state: DashboardState, window_size: int = 20, min_events: int = 5
) -> None:
    """Recompute strengths and weaknesses for every agent, in place.

    Percentiles are relative across agents, so all profiles are refreshed. An
    agent with fewer than ``min_events`` events still in the (capped) event log
    keeps its previous values instead of being cleared because its history aged out.

    Args:
        state: Dashboard state to update
        window_size: Size of the rolling window per agent
        min_events: Minimum retained events needed to re-detect
    """
    percentiles = calculate_agent_percentiles(state, window_size, min_events)
    for agent_name, profile in state["agents"].items():
        stats = calculate_rolling_window_stats(state["events"], agent_name, window_size)
        if stats["event_count"] < min_events:
            continue
        profile["strengths"] = detect_strengths(agent_name, stats, percentiles, min_events)
        profile["weaknesses"] = detect_weaknesses(agent_name, stats, percentiles, min_events)


class AgentMetricsCollector:
    """Core collector class for tracking agent delegations.

    Manages session lifecycle and provides a context manager for tracking
    individual agent invocations. Integrates with MetricsStore for persistence.

    Usage:
        collector = AgentMetricsCollector(project_name="my-project")

        session_id = collector.start_session(session_type="initializer")

        with collector.track_agent("coding", "AI-46", "claude-sonnet-4-5") as tracker:
            # Do work
            tracker.add_tokens(input_tokens=1000, output_tokens=2000)
            tracker.add_artifact("file:agent_metrics_collector.py")

        collector.end_session(session_id, status="complete")
    """

    def __init__(self, project_name: str, metrics_dir: Path | None = None):
        """Initialize the collector.

        Args:
            project_name: Name of the project
            metrics_dir: Directory to store metrics files (default: current directory)
        """
        self.project_name = project_name
        self.store = MetricsStore(project_name=project_name, metrics_dir=metrics_dir)

        # Active session tracking
        self._active_sessions: dict[str, dict] = {}

    def start_session(
        self,
        session_type: Literal["initializer", "continuation"] = "initializer"
    ) -> str:
        """Start a new session.

        Args:
            session_type: Type of session ("initializer" or "continuation")

        Returns:
            Session ID (UUID)
        """
        session_id = str(uuid.uuid4())
        started_at = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"

        # Provisional session number; end_session() assigns the final one
        # under the store lock so concurrent collectors cannot collide.
        state = self.store.load()
        session_number = state["total_sessions"] + 1

        # Track session info
        self._active_sessions[session_id] = {
            "session_number": session_number,
            "session_type": session_type,
            "started_at": started_at,
            "agents_invoked": [],
            "tickets_worked": set(),
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            # agent_name -> {"successes": n, "failures": n}, for Perfect Day.
            # Counted here so the capped event log cannot hide a failure.
            "agent_outcomes": {},
        }

        return session_id

    def end_session(
        self,
        session_id: str,
        status: Literal["continue", "error", "complete"] = "complete"
    ) -> None:
        """End an active session.

        Args:
            session_id: Session ID to end
            status: Final status of the session

        Raises:
            ValueError: If session_id is not an active session
        """
        if session_id not in self._active_sessions:
            raise ValueError(f"Session {session_id} is not an active session")

        session_info = self._active_sessions[session_id]
        ended_at = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"

        # Create session summary
        session_summary: SessionSummary = {
            "session_id": session_id,
            "session_number": session_info["session_number"],
            "session_type": session_info["session_type"],
            "started_at": session_info["started_at"],
            "ended_at": ended_at,
            "status": status,
            "agents_invoked": session_info["agents_invoked"],
            "total_tokens": session_info["total_tokens"],
            "total_cost_usd": session_info["total_cost_usd"],
            "tickets_worked": list(session_info["tickets_worked"]),
        }

        agent_outcomes = session_info.get("agent_outcomes", {})

        # Add session under one lock. The session number is assigned here,
        # from the persisted counter, so concurrent collectors cannot collide.
        # Perfect Day depends on the whole session, so it is awarded here.
        def add_session(state: DashboardState) -> None:
            session_summary["session_number"] = state["total_sessions"] + 1
            state["sessions"].append(session_summary)
            state["total_sessions"] += 1
            for agent_name, outcome in agent_outcomes.items():
                profile = state["agents"].get(agent_name)
                if profile is None:
                    continue
                if is_perfect_day_eligible(
                    outcome["successes"], outcome["failures"], status, profile
                ):
                    profile["achievements"].append("perfect_day")

        self.store.update(add_session)

        # Remove from active sessions
        del self._active_sessions[session_id]

    @contextlib.contextmanager
    def track_agent(
        self,
        agent_name: str,
        ticket_key: str,
        model_used: str,
        session_id: str | None = None,
        start_time: float | None = None,
    ):
        """Context manager for tracking an agent delegation.

        Usage:
            with collector.track_agent("coding", "AI-46", "claude-sonnet-4-5") as tracker:
                # Do work
                tracker.add_tokens(input_tokens=1000, output_tokens=2000)
                tracker.add_artifact("file:foo.py")

        The context manager:
        - Tracks start/end timestamps automatically
        - Accepts token counts and artifacts via the tracker
        - Records the event on exit (both success and exception)
        - Handles exceptions gracefully

        Args:
            agent_name: Name of the agent (e.g., "coding", "github", "linear")
            ticket_key: Linear ticket key (e.g., "AI-46")
            model_used: Model identifier (e.g., "claude-sonnet-4-5")
            session_id: Optional session ID (if None, creates a temporary session)
            start_time: Epoch seconds (time.time()) when the delegation actually began;
                defaults to now. Use it when the work started before this call.

        Yields:
            AgentTracker instance for adding tokens and artifacts
        """
        # Generate event ID and timestamps
        event_id = str(uuid.uuid4())
        if start_time is None:
            start_time = time.time()
        started_at = datetime.fromtimestamp(start_time, UTC).replace(tzinfo=None).isoformat() + "Z"

        # Use provided session or create temporary one
        temp_session = session_id is None
        if temp_session:
            session_id = self.start_session(session_type="continuation")

        # Create tracker
        tracker = AgentTracker(
            event_id=event_id,
            agent_name=agent_name,
            session_id=session_id,
            ticket_key=ticket_key,
            model_used=model_used,
            started_at=started_at,
            start_time=start_time,
        )

        try:
            # Yield tracker to caller
            yield tracker

        except Exception as e:
            # Mark as error but don't suppress the exception
            tracker.set_error(str(e))
            raise

        finally:
            # Always record the event (success or failure)
            event = tracker.finalize()
            self._record_event(event, session_id)

            # End temporary session
            if temp_session:
                self.end_session(session_id, status="complete")

    def _record_event(self, event: AgentEvent, session_id: str) -> None:
        """Record an event to the metrics store.

        Updates:
        - Global event log
        - Agent profile for this agent
        - Session tracking (if session is active)
        - Global counters

        Args:
            event: Event to record
            session_id: Session ID for this event
        """
        def apply_event(state: DashboardState) -> None:
            state["events"].append(event)

            # Update or create agent profile
            if event["agent_name"] not in state["agents"]:
                state["agents"][event["agent_name"]] = _create_empty_profile(event["agent_name"])

            profile = state["agents"][event["agent_name"]]
            state["agents"][event["agent_name"]] = _update_agent_profile(
                profile, event, state["events"]
            )
            # Apply the store's event cap first so strengths are computed from the
            # same history that will be persisted.
            if len(state["events"]) > self.store.MAX_EVENTS:
                state["events"] = state["events"][-self.store.MAX_EVENTS :]
            _refresh_strengths_weaknesses(state)

            # Update global counters
            state["total_tokens"] += event["total_tokens"]
            state["total_cost_usd"] += event["estimated_cost_usd"]
            state["total_duration_seconds"] += event["duration_seconds"]

        # Load, mutate and save under one lock so concurrent writers don't
        # lose events, and a lock timeout raises instead of saving an
        # empty state over the real file.
        self.store.update(apply_event)

        # Update active session tracking
        if session_id in self._active_sessions:
            session_info = self._active_sessions[session_id]
            if event["agent_name"] not in session_info["agents_invoked"]:
                session_info["agents_invoked"].append(event["agent_name"])
            session_info["tickets_worked"].add(event["ticket_key"])
            session_info["total_tokens"] += event["total_tokens"]
            session_info["total_cost_usd"] += event["estimated_cost_usd"]
            outcome = session_info.setdefault("agent_outcomes", {}).setdefault(
                event["agent_name"], {"successes": 0, "failures": 0}
            )
            if event["status"] == "success":
                outcome["successes"] += 1
            elif event["status"] in _FAILURE_STATUSES:
                outcome["failures"] += 1

    def get_state(self) -> DashboardState:
        """Get the current dashboard state.

        Returns:
            Current DashboardState
        """
        return self.store.load()
