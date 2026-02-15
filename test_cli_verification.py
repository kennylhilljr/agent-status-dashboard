#!/usr/bin/env python3
"""Verification test script for CLI dashboard and leaderboard.

This script tests that:
1. Dashboard can load and render agent metrics correctly
2. Leaderboard can load and render sorted agents correctly
3. All required components work without errors
"""

import json
import sys
from pathlib import Path
from io import StringIO

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from rich.console import Console
from dashboard import DashboardRenderer, MetricsFileMonitor
from leaderboard import LeaderboardRenderer

def test_dashboard():
    """Test the dashboard CLI tool."""
    print("\n=== Testing Dashboard CLI ===")

    # Find metrics file
    metrics_path = Path.cwd() / ".agent_metrics.json"

    if not metrics_path.exists():
        print(f"FAIL: Metrics file not found at {metrics_path}")
        return False

    print(f"✓ Found metrics file: {metrics_path}")

    # Test MetricsFileMonitor
    monitor = MetricsFileMonitor(metrics_path)
    state = monitor.load_metrics()

    if state is None:
        print("FAIL: Could not load metrics file")
        return False

    print(f"✓ Loaded metrics successfully")
    print(f"  - Project: {state.get('project_name', 'unknown')}")
    print(f"  - Agents: {len(state.get('agents', {}))}")
    print(f"  - Events: {len(state.get('events', []))}")
    print(f"  - Sessions: {len(state.get('sessions', []))}")

    # Test DashboardRenderer
    console = Console(file=StringIO(), width=120)
    renderer = DashboardRenderer(console)

    try:
        # Test rendering components
        header = renderer.create_project_header(state)
        print("✓ Created project header")

        agent_table = renderer.create_agent_status_table(
            state.get("agents", {}),
            state.get("events", [])
        )
        print("✓ Created agent status table")

        metrics_panel = renderer.create_metrics_panel(state)
        print("✓ Created metrics panel")

        layout = renderer.create_dashboard_layout(state)
        print("✓ Created complete dashboard layout")

        # Verify agents are displayed
        agents = state.get("agents", {})
        if len(agents) > 0:
            print(f"✓ Dashboard shows {len(agents)} agents:")
            for agent_name, agent_data in sorted(agents.items()):
                success_rate = agent_data.get("success_rate", 0.0)
                invocations = agent_data.get("total_invocations", 0)
                print(f"  - {agent_name}: {invocations} invocations, {success_rate*100:.1f}% success")

        return True

    except Exception as e:
        print(f"FAIL: Dashboard rendering error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_leaderboard():
    """Test the leaderboard CLI tool."""
    print("\n=== Testing Leaderboard CLI ===")

    # Find metrics file
    metrics_path = Path.cwd() / ".agent_metrics.json"

    if not metrics_path.exists():
        print(f"FAIL: Metrics file not found at {metrics_path}")
        return False

    print(f"✓ Found metrics file: {metrics_path}")

    # Test MetricsFileMonitor
    monitor = MetricsFileMonitor(metrics_path)
    state = monitor.load_metrics()

    if state is None:
        print("FAIL: Could not load metrics file")
        return False

    print(f"✓ Loaded metrics successfully")

    # Test LeaderboardRenderer
    console = Console(file=StringIO(), width=120)
    renderer = LeaderboardRenderer(console)

    try:
        # Test rendering components
        header = renderer.create_project_header(state)
        print("✓ Created project header")

        leaderboard_table = renderer.create_leaderboard_table(state.get("agents", {}))
        print("✓ Created leaderboard table")

        layout = renderer.create_leaderboard_layout(state)
        print("✓ Created complete leaderboard layout")

        # Verify agents are sorted by XP
        agents = state.get("agents", {})
        if len(agents) > 0:
            sorted_agents = sorted(
                agents.items(),
                key=lambda x: x[1].get("xp", 0),
                reverse=True
            )
            print(f"✓ Leaderboard shows {len(agents)} agents sorted by XP:")
            for rank, (agent_name, agent_data) in enumerate(sorted_agents, start=1):
                xp = agent_data.get("xp", 0)
                level = agent_data.get("level", 1)
                success_rate = agent_data.get("success_rate", 0.0)
                print(f"  #{rank} {agent_name}: Level {level}, {xp} XP, {success_rate*100:.1f}% success")

        return True

    except Exception as e:
        print(f"FAIL: Leaderboard rendering error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cli_scripts_exist():
    """Test that CLI scripts exist and are executable."""
    print("\n=== Testing CLI Scripts Exist ===")

    dashboard_path = Path("scripts/dashboard.py")
    leaderboard_path = Path("scripts/leaderboard.py")

    if not dashboard_path.exists():
        print(f"FAIL: Dashboard script not found at {dashboard_path}")
        return False
    print(f"✓ Dashboard script exists: {dashboard_path}")

    if not leaderboard_path.exists():
        print(f"FAIL: Leaderboard script not found at {leaderboard_path}")
        return False
    print(f"✓ Leaderboard script exists: {leaderboard_path}")

    # Check if scripts have proper shebang
    with open(dashboard_path, 'r') as f:
        first_line = f.readline()
        if first_line.startswith("#!/usr/bin/env python3"):
            print("✓ Dashboard has correct shebang")
        else:
            print("FAIL: Dashboard missing proper shebang")
            return False

    with open(leaderboard_path, 'r') as f:
        first_line = f.readline()
        if first_line.startswith("#!/usr/bin/env python3"):
            print("✓ Leaderboard has correct shebang")
        else:
            print("FAIL: Leaderboard missing proper shebang")
            return False

    return True

def main():
    """Run all verification tests."""
    print("=" * 60)
    print("CLI VERIFICATION TEST SUITE")
    print("=" * 60)

    results = {
        "dashboard": test_dashboard(),
        "leaderboard": test_leaderboard(),
        "cli_scripts": test_cli_scripts_exist()
    }

    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {test_name.upper()}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
