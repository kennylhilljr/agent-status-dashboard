#!/usr/bin/env python3
"""Run metrics persistence tests with coverage."""

import subprocess
import sys
import json

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
    cwd="/Users/bkh223/Documents/GitHub/agent-engineers/generations/agent-status-dashboard"
)

print(result.stdout)
print(result.stderr)

# Try to parse coverage JSON
try:
    with open("/Users/bkh223/Documents/GitHub/agent-engineers/generations/agent-status-dashboard/coverage.json") as f:
        coverage_data = json.load(f)
        print("\n\n=== COVERAGE SUMMARY ===")
        if "totals" in coverage_data:
            totals = coverage_data["totals"]
            print(f"Lines covered: {totals.get('num_statements', 0)} / {totals.get('num_statements', 0)}")
            print(f"Coverage percentage: {totals.get('percent_covered', 0):.1f}%")
except Exception as e:
    print(f"Could not parse coverage: {e}")

sys.exit(result.returncode)
