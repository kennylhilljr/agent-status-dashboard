#!/usr/bin/env python3
"""Demo script to visualize the dashboard output.

This script creates a sample metrics file and demonstrates what the dashboard
would look like when rendering that data. Since we can't take an actual terminal
screenshot without the rich library installed, this creates a text-based
representation of what the dashboard displays.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def create_demo_metrics_file():
    """Create a demo metrics file with realistic data."""
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(seconds=45)).isoformat()
    old = (now - timedelta(hours=1)).isoformat()

    demo_data = {
        "version": 1,
        "project_name": "Agent Status Dashboard Demo",
        "created_at": "2026-02-14T00:00:00Z",
        "updated_at": now.isoformat(),
        "total_sessions": 12,
        "total_tokens": 45000,
        "total_cost_usd": 0.45,
        "total_duration_seconds": 1200.0,
        "agents": {
            "coding": {
                "agent_name": "coding",
                "total_invocations": 20,
                "successful_invocations": 19,
                "failed_invocations": 1,
                "total_tokens": 30000,
                "total_cost_usd": 0.30,
                "total_duration_seconds": 800.0,
                "commits_made": 5,
                "prs_created": 2,
                "prs_merged": 1,
                "files_created": 15,
                "files_modified": 8,
                "lines_added": 450,
                "lines_removed": 120,
                "tests_written": 10,
                "issues_created": 0,
                "issues_completed": 3,
                "messages_sent": 0,
                "reviews_completed": 0,
                "success_rate": 0.95,
                "avg_duration_seconds": 40.0,
                "avg_tokens_per_call": 1500.0,
                "cost_per_success_usd": 0.0158,
                "xp": 950,
                "level": 3,
                "current_streak": 19,
                "best_streak": 19,
                "achievements": ["first_blood", "century_club"],
                "strengths": ["fast_execution", "high_success_rate"],
                "weaknesses": [],
                "recent_events": ["evt-1", "evt-2", "evt-3"],
                "last_error": "",
                "last_active": recent,
            },
            "github": {
                "agent_name": "github",
                "total_invocations": 8,
                "successful_invocations": 8,
                "failed_invocations": 0,
                "total_tokens": 10000,
                "total_cost_usd": 0.10,
                "total_duration_seconds": 200.0,
                "commits_made": 5,
                "prs_created": 3,
                "prs_merged": 2,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "success_rate": 1.0,
                "avg_duration_seconds": 25.0,
                "avg_tokens_per_call": 1250.0,
                "cost_per_success_usd": 0.0125,
                "xp": 800,
                "level": 2,
                "current_streak": 8,
                "best_streak": 8,
                "achievements": ["first_blood"],
                "strengths": ["perfect_accuracy", "low_cost"],
                "weaknesses": [],
                "recent_events": ["evt-4"],
                "last_error": "",
                "last_active": old,
            },
            "linear": {
                "agent_name": "linear",
                "total_invocations": 5,
                "successful_invocations": 3,
                "failed_invocations": 2,
                "total_tokens": 5000,
                "total_cost_usd": 0.05,
                "total_duration_seconds": 200.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 5,
                "issues_completed": 3,
                "messages_sent": 0,
                "reviews_completed": 0,
                "success_rate": 0.6,
                "avg_duration_seconds": 40.0,
                "avg_tokens_per_call": 1000.0,
                "cost_per_success_usd": 0.0167,
                "xp": 300,
                "level": 1,
                "current_streak": 1,
                "best_streak": 2,
                "achievements": [],
                "strengths": [],
                "weaknesses": ["high_error_rate"],
                "recent_events": ["evt-5", "evt-6"],
                "last_error": "API timeout",
                "last_active": recent,
            },
        },
        "events": [
            {
                "event_id": "evt-1",
                "agent_name": "coding",
                "session_id": "sess-1",
                "ticket_key": "AI-54",
                "started_at": recent,
                "ended_at": recent,
                "duration_seconds": 35.0,
                "status": "success",
                "input_tokens": 2000,
                "output_tokens": 3000,
                "total_tokens": 5000,
                "estimated_cost_usd": 0.05,
                "artifacts": ["file:scripts/dashboard.py", "file:tests/test_dashboard.py"],
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
            },
            {
                "event_id": "evt-2",
                "agent_name": "coding",
                "session_id": "sess-1",
                "ticket_key": "AI-53",
                "started_at": recent,
                "ended_at": recent,
                "duration_seconds": 28.0,
                "status": "success",
                "input_tokens": 1500,
                "output_tokens": 2500,
                "total_tokens": 4000,
                "estimated_cost_usd": 0.04,
                "artifacts": ["file:artifact_detector.py"],
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
            },
            {
                "event_id": "evt-3",
                "agent_name": "coding",
                "session_id": "sess-2",
                "ticket_key": "AI-52",
                "started_at": recent,
                "ended_at": recent,
                "duration_seconds": 42.0,
                "status": "success",
                "input_tokens": 1800,
                "output_tokens": 2200,
                "total_tokens": 4000,
                "estimated_cost_usd": 0.04,
                "artifacts": ["file:token_tracker.py"],
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
            },
            {
                "event_id": "evt-4",
                "agent_name": "github",
                "session_id": "sess-1",
                "ticket_key": "AI-54",
                "started_at": old,
                "ended_at": old,
                "duration_seconds": 15.0,
                "status": "success",
                "input_tokens": 500,
                "output_tokens": 500,
                "total_tokens": 1000,
                "estimated_cost_usd": 0.01,
                "artifacts": ["commit:abc123", "pr:created:#54"],
                "error_message": "",
                "model_used": "claude-haiku-4-5",
            },
            {
                "event_id": "evt-5",
                "agent_name": "linear",
                "session_id": "sess-2",
                "ticket_key": "AI-55",
                "started_at": recent,
                "ended_at": recent,
                "duration_seconds": 30.0,
                "status": "success",
                "input_tokens": 400,
                "output_tokens": 600,
                "total_tokens": 1000,
                "estimated_cost_usd": 0.01,
                "artifacts": ["issue:AI-55"],
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
            },
            {
                "event_id": "evt-6",
                "agent_name": "linear",
                "session_id": "sess-3",
                "ticket_key": "AI-56",
                "started_at": recent,
                "ended_at": recent,
                "duration_seconds": 25.0,
                "status": "error",
                "input_tokens": 300,
                "output_tokens": 200,
                "total_tokens": 500,
                "estimated_cost_usd": 0.005,
                "artifacts": [],
                "error_message": "API timeout",
                "model_used": "claude-sonnet-4-5",
            },
        ],
        "sessions": [
            {
                "session_id": "sess-1",
                "session_number": 1,
                "session_type": "initializer",
                "started_at": recent,
                "ended_at": recent,
                "status": "complete",
                "agents_invoked": ["coding", "github"],
                "total_tokens": 10000,
                "total_cost_usd": 0.10,
                "tickets_worked": ["AI-54"],
            },
            {
                "session_id": "sess-2",
                "session_number": 2,
                "session_type": "continuation",
                "started_at": recent,
                "ended_at": recent,
                "status": "complete",
                "agents_invoked": ["coding", "linear"],
                "total_tokens": 8000,
                "total_cost_usd": 0.08,
                "tickets_worked": ["AI-52", "AI-55"],
            },
        ],
    }

    return demo_data


def render_text_dashboard(data):
    """Render a text-based version of what the dashboard would display."""
    print("=" * 100)
    print("AGENT STATUS DASHBOARD - DEMO VISUALIZATION")
    print("=" * 100)
    print()

    # Header
    print("╔" + "═" * 98 + "╗")
    print(f"║ Project: {data['project_name']:<84} ║")
    print(f"║ Last Updated: {data['updated_at']:<81} ║")
    print("╚" + "═" * 98 + "╝")
    print()

    # Agent Status Table
    print("┌─────────────────────────────────────────── AGENT STATUS ───────────────────────────────────────────┐")
    print("│ Agent           │ Status       │ Current Task                   │ Duration      │")
    print("├─────────────────┼──────────────┼────────────────────────────────┼───────────────┤")

    agents = data.get("agents", {})
    events = data.get("events", {})

    for agent_name, agent_data in sorted(agents.items()):
        success_rate = agent_data.get("success_rate", 0.0)
        last_active = agent_data.get("last_active", "")

        # Determine status
        if last_active:
            try:
                last_active_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                seconds_since = (now - last_active_dt).total_seconds()

                if seconds_since < 60:
                    status = "Active ●"
                    task = "Processing..."
                    duration = f"{seconds_since:.1f}s ago"
                else:
                    status = "Idle"
                    task = "Waiting"
                    if seconds_since < 3600:
                        duration = f"{int(seconds_since / 60)}m ago"
                    else:
                        duration = f"{int(seconds_since / 3600)}h ago"
            except (ValueError, TypeError):
                status = "Unknown"
                task = "N/A"
                duration = "N/A"
        else:
            status = "Idle"
            task = "Never used"
            duration = "N/A"

        # Color code agent name based on success rate
        if success_rate >= 0.9:
            agent_display = f"{agent_name} ✓"
        elif success_rate >= 0.7:
            agent_display = f"{agent_name} ~"
        else:
            agent_display = f"{agent_name} ✗"

        print(f"│ {agent_display:<15} │ {status:<12} │ {task:<30} │ {duration:<13} │")

    print("└─────────────────┴──────────────────────────────────────────────────────────────────────────────┘")
    print()

    # Dashboard Metrics
    print("┌──────────────────────── DASHBOARD METRICS ─────────────────────────┐")

    # Active tasks count
    active_count = 0
    now = datetime.now(timezone.utc)
    for agent_data in agents.values():
        last_active = agent_data.get("last_active", "")
        if last_active:
            try:
                last_active_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
                if (now - last_active_dt).total_seconds() < 60:
                    active_count += 1
            except (ValueError, TypeError):
                pass

    print(f"│ Active Tasks: {active_count}")
    print("│")
    print("│ Recent Completions:")

    # Recent completions (last 5 successful events)
    recent_completions = []
    for event in reversed(data.get("events", [])):
        if event.get("status") == "success" and len(recent_completions) < 5:
            agent = event.get("agent_name", "unknown")
            ticket = event.get("ticket_key", "N/A")
            recent_completions.append(f"  ✓ {agent}: {ticket}")

    if recent_completions:
        for completion in recent_completions:
            print(f"│ {completion}")
    else:
        print("│   No completions yet")

    print("│")

    # System load
    total_tokens = data.get("total_tokens", 0)
    total_sessions = data.get("total_sessions", 0)

    if total_tokens > 50000:
        load = "High ●●●"
    elif total_tokens > 10000:
        load = "Medium ●●"
    else:
        load = "Low ●"

    print(f"│ System Load: {load} ({total_sessions} sessions, {total_tokens:,} tokens)")
    print("└────────────────────────────────────────────────────────────────────┘")
    print()

    print("=" * 100)
    print("This is a text representation of the rich terminal dashboard.")
    print("The actual dashboard uses the 'rich' library for beautiful, live-updating terminal UI.")
    print("=" * 100)


def main():
    """Main demo function."""
    print("\n🎯 Agent Status Dashboard - Demo\n")

    # Create demo data
    print("Creating demo metrics data...")
    demo_data = create_demo_metrics_file()

    # Save to file for reference
    demo_file = Path(".agent_metrics_demo.json")
    with open(demo_file, 'w') as f:
        json.dump(demo_data, f, indent=2)
    print(f"✓ Saved demo data to {demo_file}")
    print()

    # Render text dashboard
    render_text_dashboard(demo_data)

    print()
    print("📝 To run the actual dashboard (requires 'rich' library):")
    print("   python scripts/dashboard.py")
    print()
    print("📊 The dashboard monitors:")
    print("   • Agent status grid (name, status, current task, duration)")
    print("   • Active task count")
    print("   • Recent completions (last 5)")
    print("   • System load indicator")
    print()
    print("🔄 Refreshes every 500ms by default")
    print("📁 Reads from ~/.agent_metrics/metrics.json or ./.agent_metrics.json")
    print()


if __name__ == "__main__":
    main()
