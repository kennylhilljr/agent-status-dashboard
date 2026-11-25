"""MetricsStore - JSON persistence layer for Agent Status Dashboard.

This module provides the MetricsStore class which handles:
- Loading/saving DashboardState to/from .agent_metrics.json
- Atomic writes using write-then-rename pattern (write to temp file, then rename)
- FIFO eviction: keep last 500 events, last 50 sessions
- Corruption recovery: if JSON is invalid, restore from .bak file; if both are
  invalid, move them aside (*.corrupt-<timestamp>) and start fresh
- update(fn): read-modify-write under a single lock so concurrent writers
  cannot lose updates
- Cross-process safe operations using fcntl file locking

The MetricsStore integrates with the TypedDict types from metrics.py and provides
a reliable persistence layer for the dashboard's metrics data.
"""

import contextlib
import fcntl
import json
import os
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from metrics import DashboardState

T = TypeVar("T")


class LockAcquisitionError(Exception):
    """Raised when file lock cannot be acquired within timeout."""
    pass


@contextlib.contextmanager
def _file_lock(lock_path: Path, timeout: float = 10.0):
    """Context manager for cross-process file locking using fcntl.

    Uses exclusive non-blocking locks with retry logic to prevent race conditions.

    Args:
        lock_path: Path to lock file
        timeout: Maximum time to wait for lock in seconds

    Yields:
        None when lock is acquired

    Raises:
        LockAcquisitionError: If lock cannot be acquired within timeout
    """
    lock_fd = None
    try:
        # Open lock file (create if doesn't exist)
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY, 0o644)

        # Try to acquire lock with retry logic
        start_time = time.time()
        while True:
            try:
                # Try to acquire exclusive non-blocking lock
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break  # Lock acquired
            except OSError as e:
                # Lock is held by another process
                if time.time() - start_time >= timeout:
                    raise LockAcquisitionError(
                        f"Could not acquire lock on {lock_path} within {timeout}s"
                    ) from e
                time.sleep(0.01)  # Wait 10ms before retry

        yield  # Lock is held, execute protected code

    finally:
        # Always release lock and close file descriptor
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass  # Ignore errors during unlock
            try:
                os.close(lock_fd)
            except OSError:
                pass  # Ignore errors during close


class MetricsStore:
    """Thread-safe and cross-process-safe JSON persistence layer for dashboard metrics.

    Manages loading, saving, and maintaining the .agent_metrics.json file with:
    - Atomic writes to prevent data corruption during writes
    - FIFO eviction to cap storage at 500 events and 50 sessions
    - Automatic backup and recovery from corrupted JSON files
    - Cross-process safe operations via fcntl file locking
    - Comprehensive exception handling

    Usage:
        store = MetricsStore(project_name="my-project")
        state = store.load()  # read-only use

        def bump(state):
            state["total_sessions"] += 1

        store.update(bump)  # read-modify-write under one lock
    """

    # FIFO limits
    MAX_EVENTS = 500
    MAX_SESSIONS = 50

    # File paths
    METRICS_FILE = ".agent_metrics.json"
    BACKUP_FILE = ".agent_metrics.json.bak"
    LOCK_FILE = ".agent_metrics.lock"

    # Lock timeout (seconds)
    LOCK_TIMEOUT = 10.0

    def __init__(self, project_name: str, metrics_dir: Path | None = None):
        """Initialize MetricsStore.

        Args:
            project_name: Name of the project for the dashboard
            metrics_dir: Directory to store metrics files (default: current directory)
        """
        self.project_name = project_name
        self.metrics_dir = Path(metrics_dir) if metrics_dir else Path.cwd()
        self.metrics_path = self.metrics_dir / self.METRICS_FILE
        self.backup_path = self.metrics_dir / self.BACKUP_FILE
        self.lock_path = self.metrics_dir / self.LOCK_FILE

        # Thread lock for in-process synchronization
        self._thread_lock = threading.Lock()

    def _create_empty_state(self) -> DashboardState:
        """Create a fresh empty DashboardState.

        Returns:
            A new DashboardState with initialized fields and zero counters
        """
        now = datetime.utcnow().isoformat() + "Z"

        return {
            "version": 1,
            "project_name": self.project_name,
            "created_at": now,
            "updated_at": now,
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": [],
        }

    def _apply_fifo_eviction(self, state: DashboardState) -> DashboardState:
        """Apply FIFO eviction to keep storage bounded.

        Keeps only the last MAX_EVENTS events and MAX_SESSIONS sessions.
        Older entries are removed in FIFO order.

        Args:
            state: DashboardState to apply eviction to

        Returns:
            Modified state with eviction applied
        """
        # Evict old events (keep last MAX_EVENTS)
        if len(state["events"]) > self.MAX_EVENTS:
            state["events"] = state["events"][-self.MAX_EVENTS:]

        # Evict old sessions (keep last MAX_SESSIONS)
        if len(state["sessions"]) > self.MAX_SESSIONS:
            state["sessions"] = state["sessions"][-self.MAX_SESSIONS:]

        return state

    def _validate_state(self, data: dict) -> bool:
        """Validate that loaded data has required DashboardState structure.

        Args:
            data: Dictionary loaded from JSON file

        Returns:
            True if data has all required fields, False otherwise
        """
        required_fields = [
            "version", "project_name", "created_at", "updated_at",
            "total_sessions", "total_tokens", "total_cost_usd", "total_duration_seconds",
            "agents", "events", "sessions"
        ]

        for field in required_fields:
            if field not in data:
                return False

        # Type checks for critical fields
        if not isinstance(data["agents"], dict):
            return False
        if not isinstance(data["events"], list):
            return False
        if not isinstance(data["sessions"], list):
            return False

        return True

    def _read_state_file(self, path: Path) -> dict | None:
        """Read and validate a state file.

        Returns:
            The parsed state, or None if the file is not valid JSON or does not
            have the DashboardState structure.

        Raises:
            OSError: If the file exists but cannot be read (for example a
                permissions error). Callers must not treat this as "no data".
        """
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if isinstance(data, dict) and self._validate_state(data):
            return data
        return None

    def _quarantine(self, path: Path, keep_original: bool = False) -> Path:
        """Preserve a corrupted file under a new, unused name.

        Uses a hard link, which never overwrites an existing file, so earlier
        quarantined copies are kept. With keep_original=False the original
        name is then removed.

        Returns:
            The path the corrupted bytes are preserved at.
        """
        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        n = 0
        while True:
            suffix = f".corrupt-{stamp}" + (f"-{n}" if n else "")
            target = path.with_name(path.name + suffix)
            try:
                os.link(path, target)
                break
            except FileExistsError:
                n += 1
        if not keep_original:
            os.unlink(path)
        return target

    def _load_locked(self) -> DashboardState:
        """Load state from disk. Caller must hold both locks.

        Returns an empty state only when there is no usable data on disk. If
        the main file is missing or corrupted, it is restored from a valid
        backup. If both are
        corrupted, they are moved aside (``*.corrupt-<timestamp>``) before a
        fresh state is returned, so a later save() cannot destroy them.

        Raises:
            OSError: If a metrics file exists but cannot be read.
        """
        if not self.metrics_path.exists():
            # A valid backup without a main file (e.g. the main file was
            # deleted) is restored rather than replaced by an empty state,
            # since the next save would otherwise overwrite that backup.
            if self.backup_path.exists():
                backup = self._read_state_file(self.backup_path)
                if backup is not None:
                    self._atomic_write(self.metrics_path, backup)
                    return backup  # type: ignore
                self._quarantine(self.backup_path)
            return self._create_empty_state()

        data = self._read_state_file(self.metrics_path)
        if data is not None:
            return data  # type: ignore

        # Main file is corrupted, try backup
        if self.backup_path.exists():
            backup = self._read_state_file(self.backup_path)
            if backup is not None:
                # Keep a copy of the corrupted main file for inspection, then
                # replace it atomically, so the main file is never missing.
                self._quarantine(self.metrics_path, keep_original=True)
                self._atomic_write(self.metrics_path, backup)
                return backup  # type: ignore
            self._quarantine(self.backup_path)

        # Both unusable: preserve the corrupted file, start fresh
        self._quarantine(self.metrics_path)
        return self._create_empty_state()

    def _save_locked(self, state: DashboardState) -> None:
        """Validate, evict and atomically write state. Caller must hold both locks."""
        if not self._validate_state(state):
            raise ValueError("Invalid DashboardState structure - cannot save")

        state["updated_at"] = datetime.utcnow().isoformat() + "Z"
        state = self._apply_fifo_eviction(state)

        # Create atomic backup of existing file before overwriting
        if self.metrics_path.exists():
            self._atomic_backup(self.metrics_path, self.backup_path)

        self._atomic_write(self.metrics_path, state)

    def load(self) -> DashboardState:
        """Load DashboardState from disk with corruption recovery.

        Returns an empty state only when no metrics file exists (corrupted
        files are restored from backup or moved aside first; see
        _load_locked).

        Raises:
            LockAcquisitionError: If the file lock cannot be acquired. This is
                deliberately not turned into an empty state, because callers
                that save the result would overwrite the real file.
            OSError: If a metrics file exists but cannot be read.
        """
        with self._thread_lock:
            with _file_lock(self.lock_path, self.LOCK_TIMEOUT):
                return self._load_locked()

    def update(self, fn: Callable[[DashboardState], T]) -> T:
        """Atomically load, mutate and save state under one lock.

        ``fn`` receives the current state and mutates it in place. Its return
        value is returned from update(). Use this instead of load() + save()
        for read-modify-write, so concurrent writers cannot lose updates.

        Raises:
            LockAcquisitionError: If the file lock cannot be acquired.
        """
        with self._thread_lock:
            with _file_lock(self.lock_path, self.LOCK_TIMEOUT):
                state = self._load_locked()
                result = fn(state)
                self._save_locked(state)
                return result

    def _atomic_write(self, target_path: Path, data: dict) -> None:
        """Atomically write data to target file using temp file + rename.

        Args:
            target_path: Final destination path
            data: Dictionary to write as JSON
        """
        # Write to temporary file first (atomic write pattern)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.metrics_dir,
            prefix='.agent_metrics_',
            suffix='.tmp'
        )

        try:
            # Write JSON to temp file
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # Ensure data is written to disk

            # Atomically rename temp file to target
            # On POSIX systems, rename is atomic
            os.replace(temp_path, target_path)

        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    def _atomic_backup(self, source_path: Path, backup_path: Path) -> None:
        """Atomically create backup using temp file + rename pattern.

        Args:
            source_path: File to backup
            backup_path: Final backup destination
        """
        if not source_path.exists():
            return

        # Read source file
        with open(source_path, encoding='utf-8') as src:
            backup_data = json.load(src)

        # Write to temp file then rename atomically
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.metrics_dir,
            prefix='.agent_metrics_bak_',
            suffix='.tmp'
        )

        try:
            # Write backup to temp file
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # Ensure backup is flushed to disk

            # Atomically rename temp file to backup path
            os.replace(temp_path, backup_path)

        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    def save(self, state: DashboardState) -> None:
        """Save DashboardState to disk with atomic write.

        Uses write-then-rename pattern to ensure atomicity:
        1. Validate state structure before writing
        2. Apply FIFO eviction to keep storage bounded
        3. Create atomic backup of existing file
        4. Write to temporary file
        5. Atomically rename temp file to main file

        This ensures that the main file is never in a partially-written state.

        Args:
            state: DashboardState to save

        Raises:
            ValueError: If state validation fails
            LockAcquisitionError: If lock cannot be acquired
        """
        with self._thread_lock:
            with _file_lock(self.lock_path, self.LOCK_TIMEOUT):
                self._save_locked(state)

    def get_stats(self) -> dict:
        """Get storage statistics.

        Returns:
            Dictionary with file sizes, event count, session count, etc.
        """
        stats = {
            "metrics_file_exists": self.metrics_path.exists(),
            "backup_file_exists": self.backup_path.exists(),
            "metrics_file_size_bytes": 0,
            "backup_file_size_bytes": 0,
            "event_count": 0,
            "session_count": 0,
            "agent_count": 0,
        }

        if self.metrics_path.exists():
            stats["metrics_file_size_bytes"] = self.metrics_path.stat().st_size

        if self.backup_path.exists():
            stats["backup_file_size_bytes"] = self.backup_path.stat().st_size

        # Load state to get counts
        try:
            state = self.load()
            stats["event_count"] = len(state["events"])
            stats["session_count"] = len(state["sessions"])
            stats["agent_count"] = len(state["agents"])
        except Exception:
            pass

        return stats
