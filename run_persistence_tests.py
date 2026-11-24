#!/usr/bin/env python3
"""Run metrics persistence tests with coverage."""

import json
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent

# Run pytest with coverage
result = subprocess.run(
    [
        sys.executable, "-m", "pytest",
        "tests/test_metrics_persistence.py",
        "-v",
        "--cov=metrics_store",
        "--cov-report=html",
        "--cov-report=json",
        "--tb=short"
    ],
    capture_output=True,
    text=True,
    cwd=REPO_DIR,
)

print(result.stdout)
print(result.stderr)

# Try to parse coverage JSON
try:
    with open(REPO_DIR / "coverage.json") as f:
        coverage_data = json.load(f)
        print("\n\n=== COVERAGE SUMMARY ===")
        if "totals" in coverage_data:
            totals = coverage_data["totals"]
            covered = totals.get("covered_lines", 0)
            statements = totals.get("num_statements", 0)
            print(f"Lines covered: {covered} / {statements}")
            print(f"Coverage percentage: {totals.get('percent_covered', 0):.1f}%")
except Exception as e:
    print(f"Could not parse coverage: {e}")

sys.exit(result.returncode)
