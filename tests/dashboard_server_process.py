"""Start dashboard_server.py on a free port for browser tests.

Shared by the Playwright test modules. Not a test module itself.
"""

import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOST = '127.0.0.1'
_START_ATTEMPTS = 3
_READY_TIMEOUT_SECONDS = 15


def _free_port() -> int:
    """Ask the OS for a currently unused TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def _stop(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    process.stdout.close()


def _wait_until_ready(process: subprocess.Popen, port: int) -> bool:
    """Poll /health until it answers. False if the server exited first."""
    deadline = time.monotonic() + _READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f'http://{HOST}:{port}/health', timeout=1) as resp:
                if resp.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"dashboard_server.py did not become ready within {_READY_TIMEOUT_SECONDS}s")


@contextmanager
def dashboard_server(
    metrics_dir: Path,
    extra_args: tuple[str, ...] = (),
    env_for_port: Callable[[int], dict[str, str]] | None = None,
) -> Iterator[int]:
    """Run dashboard_server.py against metrics_dir and yield the port it listens on.

    The port is picked just before launch; if another process takes it first and
    the server exits, a new port is tried, up to a few times. The server is always
    stopped on exit.
    """
    output = ''
    for _ in range(_START_ATTEMPTS):
        port = _free_port()
        process = subprocess.Popen(
            [
                sys.executable,
                str(REPO_ROOT / 'dashboard_server.py'),
                '--host', HOST,
                '--port', str(port),
                '--metrics-dir', str(metrics_dir),
                *extra_args,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=metrics_dir,
            env=env_for_port(port) if env_for_port else None,
        )
        try:
            ready = _wait_until_ready(process, port)
        except BaseException:
            _stop(process)
            raise
        if ready:
            try:
                yield port
            finally:
                _stop(process)
            return
        output = process.stdout.read().decode(errors='replace')
        _stop(process)
    raise RuntimeError(
        f"dashboard_server.py exited before becoming ready ({_START_ATTEMPTS} attempts):\n{output}"
    )
