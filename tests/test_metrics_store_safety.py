"""Regression tests: the metrics file must never be wiped or lose updates.

Covers issue #20:
- a lock timeout raises instead of producing an empty state that is saved
  over the real file;
- corrupted files are moved aside instead of being overwritten;
- MetricsStore.update() holds the lock across load, mutate and save, so
  concurrent collectors do not lose events or reuse session numbers.
"""

import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_metrics_collector import AgentMetricsCollector
from metrics_store import LockAcquisitionError, MetricsStore, _file_lock


def _record(collector: AgentMetricsCollector, session_id: str, n: int = 1) -> None:
    for _ in range(n):
        with collector.track_agent(
            "coding", "AI-1", "claude-sonnet-4-5", session_id=session_id
        ) as t:
            t.add_tokens(input_tokens=10, output_tokens=20)


@pytest.fixture
def seeded(tmp_path):
    """A metrics dir with real history (2 events, 1 session)."""
    collector = AgentMetricsCollector(project_name="p", metrics_dir=tmp_path)
    sid = collector.start_session()
    _record(collector, sid, 2)
    collector.end_session(sid)
    return tmp_path


def test_lock_timeout_raises_and_keeps_file(seeded):
    store = MetricsStore(project_name="p", metrics_dir=seeded)
    store.LOCK_TIMEOUT = 0.1
    before = store.metrics_path.read_text()

    collector = AgentMetricsCollector(project_name="p", metrics_dir=seeded)
    collector.store.LOCK_TIMEOUT = 0.1
    collector._active_sessions["s"] = {
        "session_number": 1, "session_type": "continuation", "started_at": "x",
        "agents_invoked": [], "tickets_worked": set(), "total_tokens": 0, "total_cost_usd": 0.0,
    }

    with _file_lock(store.lock_path):
        with pytest.raises(LockAcquisitionError):
            store.load()
        with pytest.raises(LockAcquisitionError):
            store.update(lambda s: None)
        with pytest.raises(LockAcquisitionError):
            collector.end_session("s")

    assert store.metrics_path.read_text() == before
    state = store.load()
    assert len(state["events"]) == 2
    assert state["total_sessions"] == 1


def test_both_files_corrupted_are_preserved_not_overwritten(seeded):
    store = MetricsStore(project_name="p", metrics_dir=seeded)
    store.metrics_path.write_text("{not json MAIN")
    store.backup_path.write_text("{not json BACKUP")

    # A collector write must not destroy the unreadable data
    collector = AgentMetricsCollector(project_name="p", metrics_dir=seeded)
    sid = collector.start_session()
    _record(collector, sid, 1)

    corrupt = sorted(p.read_text() for p in seeded.glob(".agent_metrics.json*.corrupt-*"))
    assert corrupt == ["{not json BACKUP", "{not json MAIN"]

    state = store.load()
    assert len(state["events"]) == 1


def test_main_corrupted_restored_from_backup_keeps_corrupt_copy(seeded):
    store = MetricsStore(project_name="p", metrics_dir=seeded)
    store.metrics_path.write_text("{truncated")

    state = store.load()
    assert state["total_sessions"] >= 0  # restored from a valid backup
    assert json.loads(store.metrics_path.read_text())["project_name"] == "p"
    kept = [p.read_text() for p in seeded.glob(".agent_metrics.json.corrupt-*")]
    assert kept == ["{truncated"]


def test_unreadable_file_raises_instead_of_returning_empty(seeded, monkeypatch):
    store = MetricsStore(project_name="p", metrics_dir=seeded)
    real_open = open

    def fake_open(path, *a, **kw):
        if Path(path) == store.metrics_path:
            raise PermissionError("denied")
        return real_open(path, *a, **kw)

    monkeypatch.setattr("builtins.open", fake_open)
    with pytest.raises(PermissionError):
        store.update(lambda s: s["events"].clear())
    monkeypatch.undo()
    assert len(store.load()["events"]) == 2


def test_concurrent_collectors_do_not_lose_events_or_reuse_session_numbers(tmp_path):
    """Separate collector instances (separate thread locks, like separate
    processes) only share the fcntl file lock."""
    workers, per_worker = 4, 5
    errors: list[BaseException] = []
    barrier = threading.Barrier(workers)

    def run():
        try:
            collector = AgentMetricsCollector(project_name="p", metrics_dir=tmp_path)
            sid = collector.start_session()
            barrier.wait()
            _record(collector, sid, per_worker)
            collector.end_session(sid)
        except BaseException as e:  # pragma: no cover - surfaced below
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    state = MetricsStore(project_name="p", metrics_dir=tmp_path).load()
    assert len(state["events"]) == workers * per_worker
    assert state["agents"]["coding"]["total_invocations"] == workers * per_worker
    assert state["total_tokens"] == workers * per_worker * 30
    assert state["total_sessions"] == workers
    numbers = sorted(s["session_number"] for s in state["sessions"])
    assert numbers == list(range(1, workers + 1))
