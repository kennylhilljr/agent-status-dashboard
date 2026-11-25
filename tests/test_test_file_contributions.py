"""Created test files count as tests_written with 20 XP (issue #29)."""

import pytest

from agent_metrics_collector import (
    AgentMetricsCollector,
    _create_empty_profile,
    _created_test_file,
    _update_agent_profile,
)
from artifact_detector import ArtifactDetector


def _event(artifacts, status="success", event_id="e1"):
    return {
        "event_id": event_id,
        "agent_name": "coding",
        "session_id": "s1",
        "ticket_key": "AI-1",
        "started_at": "2026-02-14T12:00:00Z",
        "ended_at": "2026-02-14T12:05:00Z",
        # Over 5 minutes: no speed bonus, so XP is deterministic
        "duration_seconds": 400.0,
        "status": status,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "artifacts": artifacts,
        "error_message": "" if status == "success" else "boom",
        "model_used": "claude-sonnet-4-5",
    }


def _apply(artifacts, status="success"):
    profile = _create_empty_profile("coding")
    return _update_agent_profile(profile, _event(artifacts, status))


BASE_XP = 10 + 1  # base success + streak 1, no speed bonus


@pytest.mark.parametrize(
    "path",
    [
        "test_foo.py",
        "src/test_foo.py",
        "foo_test.py",
        "pkg/foo_test.go",
        "a.test.js",
        "a.test.jsx",
        "a.test.ts",
        "a.test.tsx",
        "a.spec.js",
        "a.spec.jsx",
        "a.spec.ts",
        "a.spec.tsx",
        "tests/helpers.py",
        "test/data.json",
        "web/__tests__/App.jsx",
        "a/b/tests/c/d.py",
    ],
)
def test_created_test_file_counts_and_earns_20_xp(path):
    profile = _apply([f"file:{path}:created"])
    assert profile["tests_written"] == 1
    assert profile["files_created"] == 1
    assert profile["xp"] == BASE_XP + 20


@pytest.mark.parametrize(
    "path",
    [
        "foo.py",
        "testing/foo.py",
        "mytests/foo.py",
        "tests.py",
        "contest_foo.py",
        "test_.py",
        "foo.test.py",
        "a.spec.rb",
        "attest/x.js",
    ],
)
def test_ordinary_created_file(path):
    profile = _apply([f"file:{path}:created"])
    assert profile["tests_written"] == 0
    assert profile["files_created"] == 1
    assert profile["xp"] == BASE_XP + 3


def test_modified_test_file_is_not_written():
    profile = _apply(["file:tests/test_foo.py:modified"])
    assert profile["tests_written"] == 0
    assert profile["files_modified"] == 1
    assert profile["xp"] == BASE_XP + 2


def test_path_containing_created_is_a_modification():
    # Only the final field is the action
    profile = _apply(["file:tests/created/test_foo.py:modified"])
    assert profile["tests_written"] == 0
    assert profile["files_created"] == 0
    assert profile["files_modified"] == 1
    assert profile["xp"] == BASE_XP + 2


def test_path_containing_modified_is_a_creation():
    profile = _apply(["file:src/modified/app.py:created"])
    assert profile["files_created"] == 1
    assert profile["files_modified"] == 0
    assert profile["xp"] == BASE_XP + 3


def test_legacy_file_artifact_formats_still_count():
    profile = _apply(["file:created:agent.py", "file:modified:b.py", "file:src/foo.py"])
    assert profile["files_created"] == 1
    assert profile["files_modified"] == 1
    assert profile["xp"] == BASE_XP + 3 + 2


def test_legacy_action_first_test_file():
    profile = _apply(["file:created:test_agent.py"])
    assert profile["tests_written"] == 1
    assert profile["files_created"] == 1
    assert profile["xp"] == BASE_XP + 20


@pytest.mark.parametrize(
    ("artifact", "created", "modified"),
    [
        ("file:created:test_agent.py:modified", 0, 1),
        ("file:created:test_agent.py:deleted", 0, 0),
        ("file:modified:src/a.py:created", 1, 0),
        ("file:C:/repo/tests/test_a.py:created", 1, 0),
        ("file:created:modified", 0, 1),
        ("file:created:deleted", 0, 0),
    ],
)
def test_colon_paths_use_trailing_action(artifact, created, modified):
    profile = _apply([artifact])
    assert profile["files_created"] == created
    assert profile["files_modified"] == modified


def test_unknown_action_is_not_a_creation():
    profile = _apply(["file:src/created/report.py:deleted", "file:tests/test_x.py:deleted"])
    assert profile["files_created"] == 0
    assert profile["files_modified"] == 0
    assert profile["tests_written"] == 0
    assert profile["xp"] == BASE_XP


def test_tests_run_artifact_is_not_a_test_written():
    profile = _apply(["tests_run:15"])
    assert profile["tests_written"] == 0


def test_duplicates_in_one_event_count_once():
    profile = _apply(
        [
            "file:tests/test_foo.py:created",
            "file:tests/test_foo.py:created",
            "file:tests/./test_foo.py:created",
        ]
    )
    assert profile["tests_written"] == 1
    assert profile["files_created"] == 1
    assert profile["xp"] == BASE_XP + 20


def test_mixed_files():
    profile = _apply(
        [
            "file:src/app.py:created",
            "file:tests/test_app.py:created",
            "file:src/util.py:modified",
            "commit:abc1234",
        ]
    )
    assert profile["tests_written"] == 1
    assert profile["files_created"] == 2
    assert profile["files_modified"] == 1
    assert profile["commits_made"] == 1
    assert profile["xp"] == BASE_XP + 3 + 20 + 2 + 5


def test_failed_event_counts_but_earns_no_xp():
    profile = _apply(["file:tests/test_foo.py:created"], status="error")
    assert profile["tests_written"] == 1
    assert profile["xp"] == 0


def test_created_test_file_parser():
    assert _created_test_file("file:tests/test_a.py:created") == "tests/test_a.py"
    assert _created_test_file("file:tests/test_a.py:modified") is None
    assert _created_test_file("file:test_a.py") is None
    assert _created_test_file("commit:test_a.py:created") is None
    assert _created_test_file("file::created") is None
    assert _created_test_file("file:tests/../src/app.py:created") is None
    assert _created_test_file("file:src/../tests/test_a.py:created") == "tests/test_a.py"


def test_detector_output_through_track_agent(tmp_path):
    detector = ArtifactDetector()
    artifacts = detector.detect_artifacts(
        "coding", "Created file test_widget.py and created src/widget.py"
    )
    assert "file:test_widget.py:created" in artifacts

    collector = AgentMetricsCollector(project_name="p", metrics_dir=tmp_path)
    with collector.track_agent("coding", "AI-1", "claude-sonnet-4-5") as tracker:
        for artifact in artifacts:
            tracker.add_artifact(artifact)

    profile = collector.get_state()["agents"]["coding"]
    assert profile["tests_written"] == 1


def test_historical_state_unchanged_until_new_event(tmp_path):
    collector = AgentMetricsCollector(project_name="p", metrics_dir=tmp_path)
    with collector.track_agent("coding", "AI-1", "claude-sonnet-4-5") as tracker:
        tracker.add_artifact("file:src/a.py:modified")
    state = collector.get_state()
    state["agents"]["coding"]["tests_written"] = 7
    state["agents"]["coding"]["xp"] = 500
    collector.store.save(state)

    reloaded = AgentMetricsCollector(project_name="p", metrics_dir=tmp_path).get_state()
    assert reloaded["agents"]["coding"]["tests_written"] == 7
    assert reloaded["agents"]["coding"]["xp"] == 500

    with collector.track_agent("coding", "AI-2", "claude-sonnet-4-5") as tracker:
        tracker.add_artifact("file:tests/test_a.py:created")
    assert collector.get_state()["agents"]["coding"]["tests_written"] == 8
