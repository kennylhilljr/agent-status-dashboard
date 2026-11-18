"""Checks that the GitHub Actions workflow and the README's local commands agree."""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
README = REPO_ROOT / "README.MD"

INSTALL = "python3 -m pip install --require-hashes -r requirements.txt"
PIP_CHECK = "python3 -m pip check"
LINT = "ruff check ."
TEST = "python3 -m pytest"
CI_BROWSER = "python3 -m playwright install --with-deps chromium"
LOCAL_BROWSER = "python3 -m playwright install chromium"


class _ActionsLoader(yaml.SafeLoader):
    """SafeLoader that keeps the workflow's ``on`` key a string.

    PyYAML follows YAML 1.1 and would otherwise read ``on``/``off`` as booleans.
    Only scalars starting with ``o``/``O`` lose the bool resolver, so ``true`` and
    ``false`` still load as booleans.
    """


_ActionsLoader.yaml_implicit_resolvers = {
    key: (
        [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
        if key in "oO"
        else list(resolvers)
    )
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _workflow() -> dict:
    return yaml.load(WORKFLOW.read_text(), Loader=_ActionsLoader)


def _job() -> dict:
    jobs = _workflow()["jobs"]
    assert len(jobs) == 1
    return next(iter(jobs.values()))


def _run_commands() -> list[str]:
    return [step["run"].strip() for step in _job()["steps"] if "run" in step]


def _uses(prefix: str) -> dict:
    steps = [step for step in _job()["steps"] if step.get("uses", "").startswith(prefix)]
    assert len(steps) == 1, prefix
    return steps[0]


def test_triggers_on_pull_request_and_push_to_main():
    triggers = _workflow()["on"]
    assert "pull_request" in triggers
    assert triggers["push"]["branches"] == ["main"]


def test_permissions_are_read_only():
    assert _workflow()["permissions"] == {"contents": "read"}
    assert "permissions" not in _job()


def test_runs_on_ubuntu_with_python_311():
    job = _job()
    assert job["runs-on"] == "ubuntu-latest"
    assert job["strategy"]["matrix"]["python-version"] == ["3.11"]
    setup = _uses("actions/setup-python@")
    assert setup["with"]["python-version"] == "${{ matrix.python-version }}"


def test_third_party_actions_are_pinned_to_commit_shas():
    text = WORKFLOW.read_text()
    uses = re.findall(r"uses:\s*(\S+)(.*)", text)
    assert uses
    for ref, comment in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref), ref
        assert re.search(r"#\s*v\d+\.\d+\.\d+", comment), ref


def test_caches_only_pip_downloads_keyed_on_the_lock():
    setup = _uses("actions/setup-python@")
    assert setup["with"]["cache"] == "pip"
    assert setup["with"]["cache-dependency-path"] == "requirements.txt"
    assert not [step for step in _job()["steps"] if "actions/cache" in step.get("uses", "")]


def test_installs_locked_dependencies_and_browser_before_checks():
    commands = _run_commands()
    assert commands == [INSTALL, PIP_CHECK, CI_BROWSER, LINT, TEST]


def test_lint_and_test_failures_are_fatal():
    for step in _job()["steps"]:
        assert "continue-on-error" not in step
        if "run" in step:
            assert "|| true" not in step["run"]
    assert "continue-on-error" not in _job()


def test_no_secrets_or_credentials_are_used():
    text = WORKFLOW.read_text()
    assert "secrets." not in text
    assert "API_KEY" not in text
    assert "TOKEN" not in text
    checkout = _uses("actions/checkout@")
    assert checkout["with"]["persist-credentials"] is False


def test_readme_documents_the_same_commands():
    readme = README.read_text()
    for command in (INSTALL, PIP_CHECK, LOCAL_BROWSER, CI_BROWSER, LINT, TEST):
        assert command in readme, command
