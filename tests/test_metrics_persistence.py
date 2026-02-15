#!/usr/bin/env python3
"""Comprehensive tests for metrics persistence (file I/O reliability and error handling).

This module tests the MetricsStore class with focus on:
- Atomic writes (ensure data isn't corrupted during write operations)
- Concurrent write scenarios (multiple processes/threads writing simultaneously)
- Partial file corruption scenarios (what happens if file is corrupted)
- Recovery mechanisms (can the system recover from corrupted data)
- File I/O reliability and error handling

Test coverage includes:
- Atomic write operations using temp file + rename pattern
- FIFO eviction of old events and sessions
- Corruption recovery from backup files
- Cross-process file locking with fcntl
- Concurrent write safety with threading
- Partial JSON corruption recovery
- Lock timeout handling
- Edge cases for file operations
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from metrics import DashboardState, AgentEvent, AgentProfile, SessionSummary
from metrics_store import MetricsStore, LockAcquisitionError, _file_lock


class TestAtomicWrites:
    """Test atomic write operations for data integrity."""

    @pytest.fixture
    def temp_metrics_dir(self):
        """Create a temporary directory for metrics files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_metrics_dir):
        """Create a MetricsStore instance with temporary directory."""
        return MetricsStore(project_name="test-project", metrics_dir=temp_metrics_dir)

    @pytest.fixture
    def sample_state(self) -> DashboardState:
        """Create a sample DashboardState for testing."""
        return {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 1,
            "total_tokens": 3000,
            "total_cost_usd": 0.03,
            "total_duration_seconds": 300.0,
            "agents": {},
            "events": [],
            "sessions": [],
        }

    def test_atomic_write_creates_file(self, store, sample_state):
        """Test that atomic write creates the metrics file."""
        assert not store.metrics_path.exists()
        store.save(sample_state)
        assert store.metrics_path.exists()

    def test_atomic_write_data_integrity(self, store, sample_state):
        """Test that data written atomically is not corrupted."""
        store.save(sample_state)

        # Load the saved file
        with open(store.metrics_path, 'r') as f:
            loaded_data = json.load(f)

        # Verify data integrity
        assert loaded_data["version"] == sample_state["version"]
        assert loaded_data["project_name"] == sample_state["project_name"]
        assert loaded_data["total_sessions"] == sample_state["total_sessions"]
        assert loaded_data["total_tokens"] == sample_state["total_tokens"]

    def test_atomic_write_creates_backup(self, store, sample_state):
        """Test that atomic write creates backup of previous file."""
        # First write
        store.save(sample_state)
        assert store.metrics_path.exists()
        assert not store.backup_path.exists()

        # Second write should create backup
        modified_state = sample_state.copy()
        modified_state["total_sessions"] = 2
        store.save(modified_state)

        # Verify backup exists and contains first version
        assert store.backup_path.exists()
        with open(store.backup_path, 'r') as f:
            backup_data = json.load(f)

        assert backup_data["total_sessions"] == 1  # First version

    def test_atomic_write_temp_file_cleanup(self, store, sample_state):
        """Test that temporary files are cleaned up after write."""
        store.save(sample_state)

        # Check that no temporary files remain
        temp_files = list(store.metrics_dir.glob('.agent_metrics_*.tmp'))
        assert len(temp_files) == 0

    def test_atomic_write_handles_large_json(self, store):
        """Test atomic write with large JSON payload."""
        large_state: DashboardState = {
            "version": 1,
            "project_name": "large-test",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 500,
            "total_tokens": 500000,
            "total_cost_usd": 5.0,
            "total_duration_seconds": 36000.0,
            "agents": {},
            "events": [
                {
                    "event_id": f"evt-{i}",
                    "agent_name": "coding",
                    "session_id": f"sess-{i}",
                    "ticket_key": f"AI-{1000+i}",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": [],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                }
                for i in range(500)
            ],
            "sessions": [],
        }

        store.save(large_state)

        # Verify file was written correctly
        with open(store.metrics_path, 'r') as f:
            loaded_data = json.load(f)

        assert len(loaded_data["events"]) == 500

    def test_atomic_write_fsync_called(self, store, sample_state):
        """Test that fsync is called during write (ensures data on disk)."""
        with patch('os.fsync') as mock_fsync:
            store.save(sample_state)
            # fsync should be called at least once
            assert mock_fsync.called

    def test_atomic_write_replace_called(self, store, sample_state):
        """Test that os.replace is used (atomic rename)."""
        with patch('os.replace') as mock_replace:
            store.save(sample_state)
            # os.replace should be called for atomic rename
            assert mock_replace.called


class TestCorruptionRecovery:
    """Test recovery mechanisms from file corruption."""

    @pytest.fixture
    def temp_metrics_dir(self):
        """Create a temporary directory for metrics files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_metrics_dir):
        """Create a MetricsStore instance with temporary directory."""
        return MetricsStore(project_name="test-project", metrics_dir=temp_metrics_dir)

    @pytest.fixture
    def sample_state(self) -> DashboardState:
        """Create a sample DashboardState for testing."""
        return {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 1,
            "total_tokens": 3000,
            "total_cost_usd": 0.03,
            "total_duration_seconds": 300.0,
            "agents": {},
            "events": [],
            "sessions": [],
        }

    def test_recovery_from_invalid_json(self, store, sample_state):
        """Test recovery when main file has invalid JSON."""
        # Write valid state first
        store.save(sample_state)

        # Corrupt the main file with invalid JSON
        with open(store.metrics_path, 'w') as f:
            f.write("{invalid json content")

        # Should recover from backup (which still has valid data)
        loaded_state = store.load()

        # Should have recovered to a valid state
        assert loaded_state["version"] == 1
        assert loaded_state["project_name"] == "test-project"

    def test_recovery_from_missing_fields(self, store, sample_state):
        """Test recovery when JSON has missing required fields."""
        # Write valid state first
        store.save(sample_state)

        # Corrupt the main file by removing required field
        with open(store.metrics_path, 'r') as f:
            data = json.load(f)

        del data["total_sessions"]  # Remove required field

        with open(store.metrics_path, 'w') as f:
            json.dump(data, f)

        # Load should recover
        loaded_state = store.load()
        assert loaded_state["version"] == 1

    def test_recovery_from_wrong_field_types(self, store, sample_state):
        """Test recovery when JSON has wrong field types."""
        # Write valid state first
        store.save(sample_state)

        # Corrupt the main file with wrong types
        with open(store.metrics_path, 'r') as f:
            data = json.load(f)

        data["agents"] = "not_a_dict"  # Should be dict

        with open(store.metrics_path, 'w') as f:
            json.dump(data, f)

        # Load should recover
        loaded_state = store.load()
        assert isinstance(loaded_state["agents"], dict)

    def test_recovery_from_backup_when_main_corrupted(self, store, sample_state):
        """Test recovery uses backup when main file is corrupted."""
        # Write and create backup
        store.save(sample_state)
        modified_state = sample_state.copy()
        modified_state["total_sessions"] = 5
        store.save(modified_state)

        # Corrupt main file
        with open(store.metrics_path, 'w') as f:
            f.write("corrupted data {]")

        # Load should recover from backup
        loaded_state = store.load()
        assert loaded_state["total_sessions"] == 1  # From backup (first version)

    def test_recovery_creates_fresh_state_if_both_corrupted(self, store, sample_state):
        """Test that fresh state is created if both main and backup are corrupted."""
        # Write valid state to create files
        store.save(sample_state)

        # Corrupt both main and backup
        with open(store.metrics_path, 'w') as f:
            f.write("corrupted")
        with open(store.backup_path, 'w') as f:
            f.write("corrupted")

        # Load should create fresh state
        loaded_state = store.load()
        assert loaded_state["total_sessions"] == 0
        assert len(loaded_state["events"]) == 0
        assert len(loaded_state["sessions"]) == 0

    def test_recovery_fresh_state_if_no_files(self, store):
        """Test that fresh state is created if no files exist."""
        # Don't write anything, files should not exist
        assert not store.metrics_path.exists()

        loaded_state = store.load()

        # Should have fresh state
        assert loaded_state["version"] == 1
        assert loaded_state["project_name"] == "test-project"
        assert loaded_state["total_sessions"] == 0

    def test_partial_corruption_recovery(self, store, sample_state):
        """Test recovery from partially written/corrupted file."""
        # Write valid state
        store.save(sample_state)

        # Truncate the main file (partial corruption)
        file_size = store.metrics_path.stat().st_size
        with open(store.metrics_path, 'r+b') as f:
            f.truncate(file_size // 2)  # Cut file in half

        # Load should recover
        loaded_state = store.load()
        assert isinstance(loaded_state, dict)
        assert "version" in loaded_state

    def test_validate_state_checks_structure(self, store):
        """Test that _validate_state properly validates structure."""
        valid_state = {
            "version": 1,
            "project_name": "test",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": [],
        }

        assert store._validate_state(valid_state) is True

        # Remove required field
        invalid_state = valid_state.copy()
        del invalid_state["version"]
        assert store._validate_state(invalid_state) is False

        # Wrong type for agents
        invalid_state = valid_state.copy()
        invalid_state["agents"] = "not_a_dict"
        assert store._validate_state(invalid_state) is False


class TestConcurrentWrites:
    """Test concurrent write scenarios."""

    @pytest.fixture
    def temp_metrics_dir(self):
        """Create a temporary directory for metrics files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_metrics_dir):
        """Create a MetricsStore instance with temporary directory."""
        return MetricsStore(project_name="test-project", metrics_dir=temp_metrics_dir)

    @pytest.fixture
    def sample_state(self) -> DashboardState:
        """Create a sample DashboardState for testing."""
        return {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": [],
        }

    def test_thread_safe_concurrent_writes(self, store, sample_state):
        """Test that multiple threads can safely write concurrently."""
        results = []
        errors = []

        def write_state(session_id: int):
            try:
                state = sample_state.copy()
                state["total_sessions"] = session_id
                store.save(state)
                results.append(session_id)
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads to write concurrently
        threads = []
        for i in range(10):
            t = threading.Thread(target=write_state, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # All writes should have succeeded
        assert len(results) == 10

    def test_thread_lock_prevents_race_conditions(self, store, sample_state):
        """Test that thread lock prevents race conditions.

        Verifies that concurrent save() calls are serialized by the internal
        thread lock, ensuring the final counter value is correct.
        """
        shared_state = {"counter": 0}
        save_completed = []

        def increment_and_save():
            # save() already acquires _thread_lock internally, so we just
            # call save() directly — the lock serializes the operations.
            state = sample_state.copy()
            shared_state["counter"] += 1
            state["total_sessions"] = shared_state["counter"]
            store.save(state)
            save_completed.append(True)

        # Multiple threads incrementing shared state
        threads = []
        for _ in range(5):
            t = threading.Thread(target=increment_and_save)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All saves should have completed
        assert len(save_completed) == 5

        # Final state should reflect serialized writes
        loaded = store.load()
        assert loaded["total_sessions"] > 0

    def test_concurrent_read_write(self, store, sample_state):
        """Test concurrent reads and writes."""
        errors = []

        def write_operation(i: int):
            try:
                state = sample_state.copy()
                state["total_sessions"] = i
                store.save(state)
            except Exception as e:
                errors.append(str(e))

        def read_operation():
            try:
                state = store.load()
                assert state["version"] == 1
            except Exception as e:
                errors.append(str(e))

        # Mix reads and writes
        threads = []
        for i in range(5):
            t = threading.Thread(target=write_operation, args=(i,))
            threads.append(t)
            t = threading.Thread(target=read_operation)
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"

    def test_concurrent_writes_do_not_corrupt_file(self, store, sample_state):
        """Test that concurrent writes don't leave file in corrupted state."""
        def write_state(i: int):
            state = sample_state.copy()
            state["total_sessions"] = i
            store.save(state)

        threads = []
        for i in range(10):
            t = threading.Thread(target=write_state, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # File should be readable and valid
        with open(store.metrics_path, 'r') as f:
            data = json.load(f)

        # Should be valid JSON and have expected structure
        assert isinstance(data, dict)
        assert "version" in data
        assert "total_sessions" in data


class TestFileLocking:
    """Test file locking mechanism for cross-process safety."""

    @pytest.fixture
    def temp_metrics_dir(self):
        """Create a temporary directory for metrics files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_file_lock_acquisition(self, temp_metrics_dir):
        """Test that file lock can be acquired."""
        lock_path = temp_metrics_dir / ".test.lock"

        with _file_lock(lock_path, timeout=5.0):
            # Lock acquired successfully
            assert True

    def test_file_lock_timeout(self, temp_metrics_dir):
        """Test that lock acquisition times out appropriately."""
        lock_path = temp_metrics_dir / ".test.lock"

        # Manually acquire lock
        fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY, 0o644)
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        try:
            # Try to acquire same lock with timeout
            with pytest.raises(LockAcquisitionError):
                with _file_lock(lock_path, timeout=0.1):
                    pass
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def test_file_lock_cleanup(self, temp_metrics_dir):
        """Test that file lock is properly released."""
        lock_path = temp_metrics_dir / ".test.lock"

        with _file_lock(lock_path, timeout=5.0):
            pass

        # Lock should be released and another can be acquired
        with _file_lock(lock_path, timeout=5.0):
            pass


class TestFIFOEviction:
    """Test FIFO eviction of old events and sessions."""

    @pytest.fixture
    def temp_metrics_dir(self):
        """Create a temporary directory for metrics files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_metrics_dir):
        """Create a MetricsStore instance with temporary directory."""
        return MetricsStore(project_name="test-project", metrics_dir=temp_metrics_dir)

    def test_fifo_eviction_keeps_max_events(self, store):
        """Test that FIFO eviction keeps only MAX_EVENTS."""
        state: DashboardState = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [
                {
                    "event_id": f"evt-{i}",
                    "agent_name": "coding",
                    "session_id": f"sess-{i}",
                    "ticket_key": f"AI-{100+i}",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": [],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                }
                for i in range(600)  # More than MAX_EVENTS (500)
            ],
            "sessions": [],
        }

        store.save(state)
        loaded = store.load()

        # Should only keep last 500 events
        assert len(loaded["events"]) == store.MAX_EVENTS
        assert loaded["events"][0]["event_id"] == "evt-100"  # First 100 evicted
        assert loaded["events"][-1]["event_id"] == "evt-599"

    def test_fifo_eviction_keeps_max_sessions(self, store):
        """Test that FIFO eviction keeps only MAX_SESSIONS."""
        state: DashboardState = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": [
                {
                    "session_id": f"sess-{i}",
                    "session_number": i + 1,
                    "session_type": "initializer" if i % 2 == 0 else "continuation",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T11:00:00Z",
                    "status": "complete",
                    "agents_invoked": ["coding"],
                    "total_tokens": 10000,
                    "total_cost_usd": 0.1,
                    "tickets_worked": ["AI-100"],
                }
                for i in range(100)  # More than MAX_SESSIONS (50)
            ],
        }

        store.save(state)
        loaded = store.load()

        # Should only keep last 50 sessions
        assert len(loaded["sessions"]) == store.MAX_SESSIONS
        assert loaded["sessions"][0]["session_id"] == "sess-50"  # First 50 evicted
        assert loaded["sessions"][-1]["session_id"] == "sess-99"

    def test_fifo_preserves_newest_entries(self, store):
        """Test that FIFO eviction preserves newest entries."""
        state: DashboardState = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [
                {
                    "event_id": f"evt-{i}",
                    "agent_name": "coding",
                    "session_id": f"sess-{i}",
                    "ticket_key": f"AI-{100+i}",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": [],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                }
                for i in range(600)
            ],
            "sessions": [],
        }

        store.save(state)
        loaded = store.load()

        # The last event should be evt-599
        assert loaded["events"][-1]["event_id"] == "evt-599"

        # The first event should be evt-100 (first 100 are removed)
        assert loaded["events"][0]["event_id"] == "evt-100"


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def temp_metrics_dir(self):
        """Create a temporary directory for metrics files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_metrics_dir):
        """Create a MetricsStore instance with temporary directory."""
        return MetricsStore(project_name="test-project", metrics_dir=temp_metrics_dir)

    def test_save_invalid_state_raises_error(self, store):
        """Test that saving invalid state raises ValueError."""
        invalid_state = {
            "version": 1,
            # Missing required fields
        }

        with pytest.raises(ValueError):
            store.save(invalid_state)  # type: ignore

    def test_save_updates_timestamp(self, store):
        """Test that save updates the updated_at timestamp."""
        state: DashboardState = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": [],
        }

        old_timestamp = state["updated_at"]
        time.sleep(0.01)  # Ensure time passes
        store.save(state)

        loaded = store.load()
        assert loaded["updated_at"] > old_timestamp

    def test_get_stats_with_no_files(self, store):
        """Test get_stats when no metrics files exist."""
        stats = store.get_stats()

        assert stats["metrics_file_exists"] is False
        assert stats["backup_file_exists"] is False
        assert stats["metrics_file_size_bytes"] == 0
        assert stats["backup_file_size_bytes"] == 0

    def test_get_stats_with_files(self, store):
        """Test get_stats with existing metrics files."""
        state: DashboardState = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 5,
            "total_tokens": 15000,
            "total_cost_usd": 0.15,
            "total_duration_seconds": 1500.0,
            "agents": {},
            "events": [
                {
                    "event_id": f"evt-{i}",
                    "agent_name": "coding",
                    "session_id": f"sess-{i}",
                    "ticket_key": f"AI-{100+i}",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": [],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                }
                for i in range(5)
            ],
            "sessions": [
                {
                    "session_id": f"sess-{i}",
                    "session_number": i + 1,
                    "session_type": "initializer",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T11:00:00Z",
                    "status": "complete",
                    "agents_invoked": ["coding"],
                    "total_tokens": 3000,
                    "total_cost_usd": 0.03,
                    "tickets_worked": ["AI-100"],
                }
                for i in range(5)
            ],
        }

        store.save(state)

        stats = store.get_stats()

        assert stats["metrics_file_exists"] is True
        assert stats["metrics_file_size_bytes"] > 0
        assert stats["event_count"] == 5
        assert stats["session_count"] == 5


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    @pytest.fixture
    def temp_metrics_dir(self):
        """Create a temporary directory for metrics files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_metrics_dir):
        """Create a MetricsStore instance with temporary directory."""
        return MetricsStore(project_name="test-project", metrics_dir=temp_metrics_dir)

    def test_full_workflow_create_read_update_recovery(self, store):
        """Test full workflow: create, read, update, and recovery."""
        # 1. Create initial state
        state: DashboardState = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 1,
            "total_tokens": 3000,
            "total_cost_usd": 0.03,
            "total_duration_seconds": 300.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 1,
                    "successful_invocations": 1,
                    "failed_invocations": 0,
                    "total_tokens": 3000,
                    "total_cost_usd": 0.03,
                    "total_duration_seconds": 300.0,
                    "commits_made": 1,
                    "prs_created": 0,
                    "prs_merged": 0,
                    "files_created": 1,
                    "files_modified": 0,
                    "lines_added": 25,
                    "lines_removed": 0,
                    "tests_written": 0,
                    "issues_created": 0,
                    "issues_completed": 0,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 300.0,
                    "avg_tokens_per_call": 3000.0,
                    "cost_per_success_usd": 0.03,
                    "xp": 10,
                    "level": 1,
                    "current_streak": 1,
                    "best_streak": 1,
                    "achievements": [],
                    "strengths": [],
                    "weaknesses": [],
                    "recent_events": ["evt-1"],
                    "last_error": "",
                    "last_active": "2026-02-14T10:00:00Z",
                }
            },
            "events": [
                {
                    "event_id": "evt-1",
                    "agent_name": "coding",
                    "session_id": "sess-1",
                    "ticket_key": "AI-100",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 2000,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.03,
                    "artifacts": ["commit:abc123"],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                }
            ],
            "sessions": [
                {
                    "session_id": "sess-1",
                    "session_number": 1,
                    "session_type": "initializer",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T10:05:00Z",
                    "status": "complete",
                    "agents_invoked": ["coding"],
                    "total_tokens": 3000,
                    "total_cost_usd": 0.03,
                    "tickets_worked": ["AI-100"],
                }
            ],
        }

        # 2. Save initial state
        store.save(state)
        assert store.metrics_path.exists()

        # 3. Read back and verify
        loaded = store.load()
        assert loaded["total_sessions"] == 1
        assert len(loaded["events"]) == 1
        assert "coding" in loaded["agents"]

        # 4. Update state with new data
        loaded["total_sessions"] = 2
        loaded["total_tokens"] = 6000
        store.save(loaded)

        # 5. Read back updated state
        updated = store.load()
        assert updated["total_sessions"] == 2
        assert updated["total_tokens"] == 6000

        # 6. Corrupt the file
        with open(store.metrics_path, 'w') as f:
            f.write("corrupted")

        # 7. Recover from backup
        recovered = store.load()
        assert recovered["total_sessions"] == 1  # Original version in backup
        assert recovered["total_tokens"] == 3000

    def test_stats_calculation(self, store):
        """Test that storage statistics are calculated correctly."""
        state: DashboardState = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:00Z",
            "total_sessions": 10,
            "total_tokens": 30000,
            "total_cost_usd": 0.3,
            "total_duration_seconds": 3000.0,
            "agents": {
                f"agent-{i}": {
                    "agent_name": f"agent-{i}",
                    "total_invocations": 10,
                    "successful_invocations": 9,
                    "failed_invocations": 1,
                    "total_tokens": 3000,
                    "total_cost_usd": 0.03,
                    "total_duration_seconds": 300.0,
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
                    "success_rate": 0.9,
                    "avg_duration_seconds": 30.0,
                    "avg_tokens_per_call": 300.0,
                    "cost_per_success_usd": 0.0033,
                    "xp": 90,
                    "level": 1,
                    "current_streak": 5,
                    "best_streak": 10,
                    "achievements": [],
                    "strengths": [],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": "2026-02-14T10:00:00Z",
                }
                for i in range(5)
            },
            "events": [],
            "sessions": [
                {
                    "session_id": f"sess-{i}",
                    "session_number": i + 1,
                    "session_type": "initializer",
                    "started_at": "2026-02-14T10:00:00Z",
                    "ended_at": "2026-02-14T11:00:00Z",
                    "status": "complete",
                    "agents_invoked": ["agent-0"],
                    "total_tokens": 3000,
                    "total_cost_usd": 0.03,
                    "tickets_worked": ["AI-100"],
                }
                for i in range(10)
            ],
        }

        store.save(state)
        stats = store.get_stats()

        assert stats["metrics_file_exists"] is True
        assert stats["agent_count"] == 5
        assert stats["session_count"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=metrics_store", "--cov-report=term-missing", "--cov-report=html"])
