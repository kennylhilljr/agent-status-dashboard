#!/usr/bin/env python3
"""CLI Live Terminal Dashboard for Agent Status Monitoring.

This module provides a real-time terminal dashboard using the rich library's
Live() context manager. It displays:
- Agent status grid (name, status, current task, duration)
- Active task count
- Recent completions (last 5)
- System load indicator

The dashboard reads from ~/.agent_metrics/metrics.json (or .agent_metrics.json
in the current directory) and refreshes every 500ms. It gracefully handles
missing metrics files by showing an 'initializing' state.

Usage:
    python scripts/dashboard.py [--metrics-dir PATH] [--refresh-rate MS]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Default paths
DEFAULT_METRICS_DIR = Path.home() / ".agent_metrics"
DEFAULT_METRICS_FILE = "metrics.json"
DEFAULT_REFRESH_RATE_MS = 500


class DashboardRenderer:
    """Renders the agent status dashboard using rich components."""

    def __init__(self, console: Console):
        """Initialize the dashboard renderer.

        Args:
            console: Rich console instance for rendering
        """
        self.console = console

    def create_agent_status_table(self, agents: dict, events: list) -> Table:
        """Create agent status grid showing name, status, current task, and duration.

        Args:
            agents: Dictionary of agent profiles from DashboardState
            events: List of agent events from DashboardState

        Returns:
            Rich Table with agent status information
        """
        table = Table(title="Agent Status", show_header=True, header_style="bold magenta")
        table.add_column("Agent", style="cyan", no_wrap=True, width=15)
        table.add_column("Status", style="green", width=12)
        table.add_column("Current Task", style="white", width=30)
        table.add_column("Duration", style="yellow", width=12)

        if not agents:
            table.add_row("No agents", "Idle", "Waiting for tasks...", "N/A")
            return table

        # Build a map of agent -> most recent event
        agent_recent_events = {}
        for event in reversed(events):  # Reverse to get most recent first
            agent_name = event.get("agent_name", "")
            if agent_name not in agent_recent_events:
                agent_recent_events[agent_name] = event

        # Render each agent
        for agent_name, agent_data in sorted(agents.items()):
            # Determine status
            recent_event = agent_recent_events.get(agent_name)
            last_active = agent_data.get("last_active", "")

            # Check if agent is currently active (active within last 60 seconds)
            if last_active:
                try:
                    last_active_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    seconds_since = (now - last_active_dt).total_seconds()

                    if seconds_since < 60:
                        status = "[green]Active[/green]"
                        current_task = "Processing..."
                        if recent_event:
                            ticket = recent_event.get("ticket_key", "N/A")
                            current_task = f"{ticket[:20]}"
                        duration_str = f"{seconds_since:.1f}s ago"
                    else:
                        status = "[dim]Idle[/dim]"
                        current_task = "[dim]Waiting[/dim]"
                        duration_str = self._format_time_ago(seconds_since)
                except (ValueError, TypeError):
                    status = "[yellow]Unknown[/yellow]"
                    current_task = "[dim]N/A[/dim]"
                    duration_str = "N/A"
            else:
                status = "[dim]Idle[/dim]"
                current_task = "[dim]Never used[/dim]"
                duration_str = "N/A"

            # Format agent name with success rate indicator
            success_rate = agent_data.get("success_rate", 0.0)
            if success_rate >= 0.9:
                agent_display = f"[green]{agent_name}[/green]"
            elif success_rate >= 0.7:
                agent_display = f"[yellow]{agent_name}[/yellow]"
            else:
                agent_display = f"[red]{agent_name}[/red]"

            table.add_row(agent_display, status, current_task, duration_str)

        return table

    def create_metrics_panel(self, state: dict) -> Panel:
        """Create metrics panel showing active tasks, completions, and system load.

        Args:
            state: DashboardState dictionary

        Returns:
            Rich Panel with metrics information
        """
        agents = state.get("agents", {})
        events = state.get("events", [])
        sessions = state.get("sessions", [])

        # Calculate active task count (agents active in last 60 seconds)
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

        # Get recent completions (last 5 successful events)
        recent_completions = []
        for event in reversed(events):
            if event.get("status") == "success" and len(recent_completions) < 5:
                agent = event.get("agent_name", "unknown")
                ticket = event.get("ticket_key", "N/A")
                recent_completions.append(f"{agent}: {ticket}")

        # System load indicator (based on total sessions and total tokens)
        total_sessions = state.get("total_sessions", 0)
        total_tokens = state.get("total_tokens", 0)

        if total_tokens > 50000:
            load_indicator = "[red]High[/red]"
        elif total_tokens > 10000:
            load_indicator = "[yellow]Medium[/yellow]"
        else:
            load_indicator = "[green]Low[/green]"

        # Build metrics text
        text = Text()
        text.append("Active Tasks: ", style="bold")
        text.append(f"{active_count}\n", style="cyan")

        text.append("\nRecent Completions:\n", style="bold")
        if recent_completions:
            for completion in recent_completions:
                text.append(f"  ✓ {completion}\n", style="green")
        else:
            text.append("  [dim]No completions yet[/dim]\n")

        text.append("\nSystem Load: ", style="bold")
        text.append(load_indicator, style="")
        text.append(f" ({total_sessions} sessions, {total_tokens:,} tokens)\n")

        return Panel(text, title="Dashboard Metrics", border_style="blue")

    def create_project_header(self, state: dict) -> Panel:
        """Create project header with project name and update time.

        Args:
            state: DashboardState dictionary

        Returns:
            Rich Panel with project header
        """
        project_name = state.get("project_name", "Unknown Project")
        updated_at = state.get("updated_at", "")

        if updated_at:
            try:
                updated_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                updated_str = updated_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except (ValueError, TypeError):
                updated_str = "Unknown"
        else:
            updated_str = "Never"

        text = Text()
        text.append(f"Project: ", style="bold")
        text.append(f"{project_name}\n", style="cyan bold")
        text.append(f"Last Updated: ", style="bold")
        text.append(f"{updated_str}", style="dim")

        return Panel(text, title="Agent Status Dashboard", border_style="green")

    def create_initializing_layout(self) -> Layout:
        """Create layout for initializing state when metrics file doesn't exist.

        Returns:
            Rich Layout showing initializing state
        """
        layout = Layout()

        text = Text()
        text.append("\n\n", style="")
        text.append("⏳ Initializing...\n\n", style="bold yellow")
        text.append("Waiting for metrics file to be created.\n", style="dim")
        text.append("The dashboard will update automatically when agents start working.\n", style="dim")
        text.append("\n", style="")
        text.append("Expected file locations:\n", style="bold")
        text.append("  • ~/.agent_metrics/metrics.json\n", style="cyan")
        text.append("  • ./.agent_metrics.json\n", style="cyan")

        panel = Panel(text, title="Agent Status Dashboard", border_style="yellow")
        layout.update(panel)

        return layout

    def create_dashboard_layout(self, state: dict) -> Layout:
        """Create complete dashboard layout with all components.

        Args:
            state: DashboardState dictionary

        Returns:
            Rich Layout with all dashboard components
        """
        layout = Layout()

        # Split into header and body
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="body")
        )

        # Split body into left (agent table) and right (metrics)
        layout["body"].split_row(
            Layout(name="agents", ratio=2),
            Layout(name="metrics", ratio=1)
        )

        # Populate components
        layout["header"].update(self.create_project_header(state))
        layout["agents"].update(
            Panel(
                self.create_agent_status_table(
                    state.get("agents", {}),
                    state.get("events", [])
                ),
                border_style="cyan"
            )
        )
        layout["metrics"].update(self.create_metrics_panel(state))

        return layout

    @staticmethod
    def _format_time_ago(seconds: float) -> str:
        """Format seconds into human-readable 'time ago' string.

        Args:
            seconds: Number of seconds

        Returns:
            Formatted string like "5m ago" or "2h ago"
        """
        if seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h ago"
        else:
            return f"{int(seconds / 86400)}d ago"


class MetricsFileMonitor:
    """Monitors and loads metrics from the metrics file."""

    def __init__(self, metrics_path: Path):
        """Initialize metrics file monitor.

        Args:
            metrics_path: Path to the metrics.json file
        """
        self.metrics_path = metrics_path
        self._last_modified_time = 0.0

    def load_metrics(self) -> Optional[dict]:
        """Load metrics from file if it exists.

        Returns:
            DashboardState dictionary if file exists and is valid, None otherwise
        """
        if not self.metrics_path.exists():
            return None

        try:
            with open(self.metrics_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, IOError, OSError):
            # File is corrupted or unreadable
            return None

    def has_changed(self) -> bool:
        """Check if metrics file has been modified since last check.

        Returns:
            True if file has been modified, False otherwise
        """
        if not self.metrics_path.exists():
            return False

        try:
            current_mtime = self.metrics_path.stat().st_mtime
            if current_mtime != self._last_modified_time:
                self._last_modified_time = current_mtime
                return True
        except (IOError, OSError):
            pass

        return False


def find_metrics_file(metrics_dir: Optional[Path] = None) -> Path:
    """Find metrics file path.

    Searches in the following order:
    1. Provided metrics_dir / metrics.json
    2. ~/.agent_metrics/metrics.json
    3. ./.agent_metrics.json (current directory)

    Args:
        metrics_dir: Optional directory containing metrics.json

    Returns:
        Path to metrics file (may not exist yet)
    """
    if metrics_dir:
        return metrics_dir / DEFAULT_METRICS_FILE

    # Try ~/.agent_metrics/metrics.json
    home_metrics = DEFAULT_METRICS_DIR / DEFAULT_METRICS_FILE
    if home_metrics.exists():
        return home_metrics

    # Fall back to ./.agent_metrics.json in current directory
    return Path.cwd() / ".agent_metrics.json"


def run_dashboard(
    metrics_path: Path,
    refresh_rate_ms: int = DEFAULT_REFRESH_RATE_MS
) -> None:
    """Run the live terminal dashboard.

    Args:
        metrics_path: Path to metrics.json file
        refresh_rate_ms: Refresh rate in milliseconds (default: 500ms)
    """
    console = Console()
    renderer = DashboardRenderer(console)
    monitor = MetricsFileMonitor(metrics_path)

    refresh_rate_sec = refresh_rate_ms / 1000.0

    with Live(
        renderer.create_initializing_layout(),
        console=console,
        refresh_per_second=1.0 / refresh_rate_sec,
        screen=True
    ) as live:
        try:
            while True:
                # Load metrics
                state = monitor.load_metrics()

                if state is None:
                    # Metrics file doesn't exist or is invalid
                    live.update(renderer.create_initializing_layout())
                else:
                    # Render dashboard with current state
                    live.update(renderer.create_dashboard_layout(state))

                # Sleep until next refresh
                time.sleep(refresh_rate_sec)

        except KeyboardInterrupt:
            # Clean exit on Ctrl+C
            console.print("\n[yellow]Dashboard stopped by user.[/yellow]")


def main():
    """Main entry point for the dashboard CLI."""
    parser = argparse.ArgumentParser(
        description="Live terminal dashboard for agent status monitoring"
    )
    parser.add_argument(
        "--metrics-dir",
        type=Path,
        default=None,
        help="Directory containing metrics.json (default: ~/.agent_metrics or ./.agent_metrics.json)"
    )
    parser.add_argument(
        "--refresh-rate",
        type=int,
        default=DEFAULT_REFRESH_RATE_MS,
        help=f"Refresh rate in milliseconds (default: {DEFAULT_REFRESH_RATE_MS}ms)"
    )

    args = parser.parse_args()

    # Find metrics file
    metrics_path = find_metrics_file(args.metrics_dir)

    # Print startup information
    console = Console()
    console.print(f"[cyan]Starting Agent Status Dashboard...[/cyan]")
    console.print(f"[dim]Monitoring: {metrics_path}[/dim]")
    console.print(f"[dim]Refresh rate: {args.refresh_rate}ms[/dim]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    time.sleep(1)  # Brief pause before starting live display

    # Run dashboard
    run_dashboard(metrics_path, args.refresh_rate)


if __name__ == "__main__":
    main()
