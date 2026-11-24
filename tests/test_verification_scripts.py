"""Regression tests for the one-off verification scripts at the repository root.

* ``run_persistence_tests.py`` must locate the repository from its own path, not
  from a hard-coded absolute directory on one developer's machine.
* The manual WebSocket scripts start a server and write metrics into the working
  directory, so default ``pytest`` collection must skip them.
"""

import builtins
import importlib
import io
import json
import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_DIR = Path(__file__).resolve().parent.parent
RUNNER = REPO_DIR / "run_persistence_tests.py"


def _run_runner(monkeypatch, tmp_path, returncode):
    """Execute the persistence runner from an unrelated cwd with I/O mocked.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        tmp_path: Unrelated working directory to run from.
        returncode: Exit code the mocked pytest subprocess reports.

    Returns:
        Tuple of (subprocess.run calls, opened paths, SystemExit code).
    """
    run_calls = []
    opened = []
    real_open = builtins.open

    def fake_run(cmd, **kwargs):
        run_calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=returncode, stdout="", stderr="")

    def fake_open(file, *args, **kwargs):
        if Path(file).name == "coverage.json":
            opened.append(Path(file))
            totals = {"covered_lines": 9, "num_statements": 10, "percent_covered": 90.0}
            return io.StringIO(json.dumps({"totals": totals}))
        return real_open(file, *args, **kwargs)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(builtins, "open", fake_open)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(RUNNER), run_name="__main__")
    return run_calls, opened, exc_info.value.code


@pytest.mark.parametrize("returncode", [0, 3])
def test_persistence_runner_uses_its_own_directory(monkeypatch, tmp_path, capsys, returncode):
    run_calls, opened, exit_code = _run_runner(monkeypatch, tmp_path, returncode)

    assert len(run_calls) == 1
    cmd, kwargs = run_calls[0]
    assert "tests/test_metrics_persistence.py" in cmd
    assert Path(kwargs["cwd"]).resolve() == REPO_DIR
    assert opened == [REPO_DIR / "coverage.json"]
    assert exit_code == returncode
    assert "Lines covered: 9 / 10" in capsys.readouterr().out


@pytest.mark.parametrize("module_name", ["test_websocket_manual", "test_websocket_simple"])
def test_manual_websocket_scripts_are_skipped_by_pytest(module_name):
    module = importlib.import_module(module_name)
    marks = module.pytestmark
    marks = marks if isinstance(marks, list) else [marks]
    skips = [mark for mark in marks if mark.name == "skip"]
    assert skips, f"{module_name} must be skipped under default pytest"
    reason = skips[0].kwargs["reason"]
    assert "manual" in reason
    assert "writes metrics" in reason
