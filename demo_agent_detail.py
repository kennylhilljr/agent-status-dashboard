#!/usr/bin/env python3
"""Demo script to showcase the agent detail view functionality.

This script creates comprehensive demo metrics data and displays
agent detail views for multiple agents.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from agent_detail import AgentDetailRenderer, display_agent_detail
from rich.console import Console


def create_comprehensive_demo_metrics():
    """Create comprehensive demo metrics with realistic agent data."""
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
                "achievements": ["first_blood", "century_club", "top_performer"],
                "strengths": ["fast_execution", "high_success_rate", "consistent"],
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
                "achievements": ["first_blood", "perfect_record"],
                "strengths": ["perfect_accuracy", "low_cost"],
                "weaknesses": ["limited_scope"],
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
                "weaknesses": ["high_error_rate", "consistency_issues"],
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


def main():
    """Main demo function."""
    console = Console()

    print("\n" + "=" * 100)
    print("AGENT DETAIL VIEW - DEMONSTRATION")
    print("=" * 100 + "\n")

    # Create demo data
    print("Creating comprehensive demo metrics...")
    demo_data = create_comprehensive_demo_metrics()

    # Save to temporary file
    demo_file = Path(".demo_agent_detail_metrics.json")
    with open(demo_file, 'w') as f:
        json.dump(demo_data, f, indent=2)
    print(f"Demo data saved to: {demo_file}\n")

    # Display agent details
    agents_to_show = ["coding", "github", "linear"]

    for agent_name in agents_to_show:
        print("\n" + "=" * 100)
        print(f"DISPLAYING AGENT DETAIL: {agent_name.upper()}")
        print("=" * 100 + "\n")

        display_agent_detail(agent_name, demo_file)

    # Cleanup
    demo_file.unlink(missing_ok=True)

    print("\n" + "=" * 100)
    print("AGENT DETAIL VIEW DEMONSTRATION COMPLETE")
    print("=" * 100)
    print("\nUsage:")
    print("  python scripts/agent_detail.py --agent <agent_name> [--metrics-dir PATH]")
    print("\nExamples:")
    print("  python scripts/agent_detail.py --agent coding")
    print("  python scripts/agent_detail.py --agent github --metrics-dir ~/.agent_metrics")
    print("\nFeatures demonstrated:")
    print("  • Agent profile with XP, level, and streaks")
    print("  • Performance metrics (success rate, invocations, duration, tokens, cost)")
    print("  • Strengths and weaknesses identification")
    print("  • Achievements earned by the agent")
    print("  • Recent events/activities with status and metrics")
    print()


if __name__ == "__main__":
    main()
