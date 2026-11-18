#!/usr/bin/env python3
"""
Verification Gate Test - End-to-End Feature Verification
Tests all completed CLI dashboard features to ensure no regressions.
"""

import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path

# ANSI color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def run_command(cmd, description):
    """Run a command and return success status and output."""
    print(f"\n{BLUE}▶ Testing: {description}{RESET}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        success = result.returncode == 0
        output = result.stdout if result.stdout else result.stderr

        if success:
            print(f"{GREEN}✓ PASS{RESET}")
        else:
            print(f"{RED}✗ FAIL{RESET}")
            print(f"Error: {result.stderr[:200]}")

        return success, output
    except subprocess.TimeoutExpired:
        print(f"{RED}✗ FAIL - Timeout{RESET}")
        return False, "Command timed out"
    except Exception as e:
        print(f"{RED}✗ FAIL - Exception: {e}{RESET}")
        return False, str(e)

def save_evidence(test_name, output, base_dir):
    """Save test output as evidence."""
    evidence_file = base_dir / f"{test_name}_evidence.txt"
    evidence_file.write_text(output)
    return evidence_file

def validate_json(output):
    """Validate that output is valid JSON."""
    try:
        json.loads(output)
        return True
    except json.JSONDecodeError:
        return False

def main():
    """Run all verification tests."""
    print(f"\n{YELLOW}{'='*80}{RESET}")
    print(f"{YELLOW}VERIFICATION GATE - Feature Regression Testing{RESET}")
    print(f"{YELLOW}{'='*80}{RESET}")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create evidence directory
    evidence_dir = Path(__file__).parent / "verification_evidence"
    evidence_dir.mkdir(exist_ok=True)

    tests = []

    # Test 1: CLI Dashboard --once mode
    success, output = run_command(
        "python scripts/cli.py --once",
        "CLI Dashboard (--once mode)"
    )
    tests.append({
        "name": "CLI Dashboard --once",
        "status": "PASS" if success else "FAIL",
        "evidence": save_evidence("dashboard_once", output, evidence_dir),
        "validation": "Dashboard renders with agent status table" if "Agent Status" in output else "Missing expected content"
    })

    # Test 2: CLI JSON output mode
    success, output = run_command(
        "python scripts/cli.py --json",
        "CLI JSON Output (--json mode)"
    )
    json_valid = validate_json(output)
    tests.append({
        "name": "CLI JSON Output",
        "status": "PASS" if (success and json_valid) else "FAIL",
        "evidence": save_evidence("json_output", output, evidence_dir),
        "validation": "Valid JSON output" if json_valid else "Invalid JSON"
    })

    # Test 3: CLI Leaderboard mode
    success, output = run_command(
        "python scripts/cli.py --leaderboard --once",
        "CLI Leaderboard (--leaderboard mode)"
    )
    tests.append({
        "name": "CLI Leaderboard",
        "status": "PASS" if success else "FAIL",
        "evidence": save_evidence("leaderboard", output, evidence_dir),
        "validation": "Leaderboard renders with agent rankings" if "Agent Leaderboard" in output else "Missing expected content"
    })

    # Test 4: CLI Achievements mode
    success, output = run_command(
        "python scripts/cli.py --achievements --once",
        "CLI Achievements (--achievements mode)"
    )
    tests.append({
        "name": "CLI Achievements",
        "status": "PASS" if success else "FAIL",
        "evidence": save_evidence("achievements", output, evidence_dir),
        "validation": "Achievements dashboard renders" if "Achievements Dashboard" in output else "Missing expected content"
    })

    # Test 5: CLI Agent Detail mode
    success, output = run_command(
        "python scripts/cli.py --agent coding --once",
        "CLI Agent Detail (--agent mode)"
    )
    tests.append({
        "name": "CLI Agent Detail",
        "status": "PASS" if success else "FAIL",
        "evidence": save_evidence("agent_detail", output, evidence_dir),
        "validation": "Agent profile renders with metrics" if "Agent Profile" in output and "Performance Metrics" in output else "Missing expected content"
    })

    # Test 6: Metrics Collection System
    success, output = run_command(
        "python test_metrics_import.py",
        "Metrics Collection System"
    )
    tests.append({
        "name": "Metrics Collection",
        "status": "PASS" if success and "agents" in output else "FAIL",
        "evidence": save_evidence("metrics_system", output, evidence_dir),
        "validation": "MetricsStore operational" if success else "Metrics system error"
    })

    # Generate summary report
    print(f"\n{YELLOW}{'='*80}{RESET}")
    print(f"{YELLOW}TEST SUMMARY{RESET}")
    print(f"{YELLOW}{'='*80}{RESET}")

    passed = sum(1 for t in tests if t["status"] == "PASS")
    total = len(tests)

    for test in tests:
        status_color = GREEN if test["status"] == "PASS" else RED
        print(f"{status_color}{test['status']}{RESET} - {test['name']}")
        print(f"      Validation: {test['validation']}")
        print(f"      Evidence: {test['evidence']}")

    print(f"\n{YELLOW}Results: {passed}/{total} tests passed{RESET}")

    # Generate HTML report
    html_report = generate_html_report(tests, passed, total)
    report_file = evidence_dir / "verification_report.html"
    report_file.write_text(html_report)
    print(f"\n{BLUE}Full Report: {report_file}{RESET}")

    # Exit with appropriate code
    if passed == total:
        print(f"\n{GREEN}{'='*80}{RESET}")
        print(f"{GREEN}✓ ALL TESTS PASSED - No regressions detected{RESET}")
        print(f"{GREEN}{'='*80}{RESET}")
        sys.exit(0)
    else:
        print(f"\n{RED}{'='*80}{RESET}")
        print(f"{RED}✗ SOME TESTS FAILED - Regressions detected!{RESET}")
        print(f"{RED}{'='*80}{RESET}")
        sys.exit(1)

def generate_html_report(tests, passed, total):
    """Generate HTML verification report."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    test_rows = ""
    for test in tests:
        status_class = "pass" if test["status"] == "PASS" else "fail"
        status_symbol = "✓" if test["status"] == "PASS" else "✗"
        test_rows += f"""
        <tr class="{status_class}">
            <td><strong>{status_symbol} {test['name']}</strong></td>
            <td>{test['status']}</td>
            <td>{test['validation']}</td>
            <td><code>{test['evidence'].name}</code></td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Verification Gate Test Report</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 1200px;
                margin: 40px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
            }}
            .summary {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .summary-card {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .summary-card h3 {{
                margin: 0 0 10px 0;
                color: #666;
                font-size: 14px;
            }}
            .summary-card .value {{
                font-size: 32px;
                font-weight: bold;
                color: #333;
            }}
            table {{
                width: 100%;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            th {{
                background: #667eea;
                color: white;
                padding: 15px;
                text-align: left;
            }}
            td {{
                padding: 12px 15px;
                border-bottom: 1px solid #eee;
            }}
            tr.pass {{
                background: #f0fdf4;
            }}
            tr.fail {{
                background: #fef2f2;
            }}
            .pass-rate {{
                font-size: 48px;
                font-weight: bold;
                color: {('#10b981' if passed == total else '#ef4444')};
            }}
            code {{
                background: #f3f4f6;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔒 Verification Gate Test Report</h1>
            <p>End-to-End Feature Regression Testing</p>
            <p><strong>Timestamp:</strong> {timestamp}</p>
        </div>

        <div class="summary">
            <div class="summary-card">
                <h3>Tests Run</h3>
                <div class="value">{total}</div>
            </div>
            <div class="summary-card">
                <h3>Passed</h3>
                <div class="value" style="color: #10b981;">{passed}</div>
            </div>
            <div class="summary-card">
                <h3>Failed</h3>
                <div class="value" style="color: #ef4444;">{total - passed}</div>
            </div>
            <div class="summary-card">
                <h3>Pass Rate</h3>
                <div class="pass-rate">{(passed/total*100):.0f}%</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Feature</th>
                    <th>Status</th>
                    <th>Validation</th>
                    <th>Evidence</th>
                </tr>
            </thead>
            <tbody>
                {test_rows}
            </tbody>
        </table>

        <div style="margin-top: 30px; padding: 20px; background: white; border-radius: 8px;">
            <h2>Tested Features</h2>
            <ul>
                <li><strong>CLI Dashboard --once:</strong> Main dashboard display with agent status table</li>
                <li><strong>CLI JSON Output:</strong> JSON export functionality for programmatic access</li>
                <li><strong>CLI Leaderboard:</strong> Agent ranking system sorted by XP</li>
                <li><strong>CLI Achievements:</strong> Achievement tracking and display system</li>
                <li><strong>CLI Agent Detail:</strong> Detailed drill-down view for individual agents</li>
                <li><strong>Metrics Collection:</strong> Core metrics storage and retrieval system</li>
            </ul>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    main()
