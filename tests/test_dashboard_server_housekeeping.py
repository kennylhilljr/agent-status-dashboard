"""Regression tests for dashboard_server error handling and event-loop safety.

Covers:
- 500 responses never echo exception text (file paths, lock errors) to clients
- MetricsStore.load() runs off the event loop, so a slow or locked metrics file
  does not stall other requests
- The WebSocket broadcast re-reads the metrics file only when it changed
- Local metrics state (a .bak that recovery could restore over live data, the
  lock file) is neither tracked nor committable
"""

import asyncio
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from dashboard_server import DashboardServer

SECRET = "/very/private/path/.agent_metrics.lock"


def _seed_state(store):
    """Save a state with one agent, so it is not an empty state."""
    state = store.load()
    state["agents"]["seed_agent"] = {"agent_name": "seed_agent"}
    store.save(state)


@pytest.fixture
def server(tmp_path):
    """DashboardServer backed by a temporary, non-empty metrics file."""
    srv = DashboardServer(project_name="housekeeping", metrics_dir=tmp_path, port=0)
    _seed_state(srv.store)
    return srv


@pytest.fixture
async def client(server):
    """aiohttp test client for the server's app."""
    async with TestClient(TestServer(server.app)) as c:
        yield c


def _raise_secret(*_args, **_kwargs):
    raise OSError(f"Could not acquire lock on {SECRET} within 10.0s")


@pytest.mark.parametrize("path", ["/api/metrics", "/api/agents/some_agent", "/health"])
async def test_500_does_not_leak_exception_text(server, client, monkeypatch, path):
    monkeypatch.setattr(server.store, "load", _raise_secret)
    monkeypatch.setattr(server.store, "get_stats", _raise_secret)

    resp = await client.get(path)
    body = await resp.text()

    assert resp.status == 500
    assert SECRET not in body
    assert "Could not acquire lock" not in body
    assert "OSError" not in body
    data = json.loads(body)
    assert data["message"] == "Internal server error"


async def test_slow_load_does_not_block_event_loop(server, client, monkeypatch):
    real_load = server.store.load
    started = threading.Event()
    finished = threading.Event()

    def slow_load():
        # Blocks like a writer holding the fcntl lock
        started.set()
        time.sleep(0.5)
        finished.set()
        return real_load()

    monkeypatch.setattr(server.store, "load", slow_load)

    request = asyncio.ensure_future(client.get("/api/metrics"))
    deadline = time.monotonic() + 5
    while not started.is_set() and time.monotonic() < deadline:
        await asyncio.sleep(0.001)
    assert started.is_set()

    # The loop got control back while load() was still running. If load()
    # ran on the loop, it would already have finished by now.
    assert not finished.is_set(), "MetricsStore.load() blocked the event loop"

    resp = await request
    assert resp.status == 200


async def test_broadcast_rereads_only_when_file_changes(server, monkeypatch):
    calls = 0
    real_load = server.store.load

    def counting_load():
        nonlocal calls
        calls += 1
        return real_load()

    monkeypatch.setattr(server.store, "load", counting_load)

    first = await server._serialized_state()
    for _ in range(5):
        assert await server._serialized_state() == first
    assert calls == 1

    state = real_load()
    state["total_sessions"] = 42
    server.store.save(state)

    changed = await server._serialized_state()
    assert calls == 2
    assert json.loads(changed)["total_sessions"] == 42


async def test_lock_timeout_fallback_is_not_cached(server, monkeypatch):
    real_load = server.store.load
    real = await server._serialized_state()
    server._broadcast_cache = None

    # On lock timeout, load() returns a fresh empty state instead of the file.
    monkeypatch.setattr(server.store, "load", server.store._create_empty_state)
    empty = json.loads(await server._serialized_state())
    assert empty["agents"] == {}

    # Once the lock is free again, the unchanged file must be re-read.
    monkeypatch.setattr(server.store, "load", real_load)
    assert await server._serialized_state() == real


async def test_broadcast_message_is_valid_json(server):
    message = json.loads(server._metrics_message(await server._serialized_state()))
    assert message["type"] == "metrics_update"
    assert message["timestamp"].endswith("Z")
    assert message["data"]["project_name"] == "housekeeping"


async def test_broadcast_reaches_clients_without_reloading(server, monkeypatch):
    # Set before the app starts: the broadcast loop reads the interval as it sleeps.
    server.broadcast_interval = 0.05
    calls = 0
    real_load = server.store.load

    def counting_load():
        nonlocal calls
        calls += 1
        return real_load()

    monkeypatch.setattr(server.store, "load", counting_load)

    async with TestClient(TestServer(server.app)) as client:
        async with client.ws_connect("/ws") as ws:
            for _ in range(4):
                msg = await ws.receive_json(timeout=2)
                assert msg["type"] == "metrics_update"
                assert msg["data"]["project_name"] == "housekeeping"

    assert calls == 1


REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_STATE_FILES = [
    ".agent_metrics.json",
    ".agent_metrics.json.bak",
    ".agent_metrics.lock",
    ".claude_settings.json",
    ".coverage",
    "coverage.json",
]


@pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists(),
    reason="needs a git checkout",
)
@pytest.mark.parametrize("name", LOCAL_STATE_FILES)
def test_local_state_is_untracked_and_ignored(name):
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", name],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert tracked.returncode != 0, f"{name} is tracked by git"

    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", name],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert ignored.returncode == 0, f"{name} is not covered by .gitignore"
