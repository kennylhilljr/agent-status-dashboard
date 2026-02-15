#!/usr/bin/env python3
"""CLI Leaderboard View for Agent Status Dashboard.

This module provides a real-time terminal leaderboard using the rich library,
displaying agents sorted by XP with their performance metrics:
- XP (Experience Points) and Level
- Success Rate (percentage of successful invocations)
- Average Time (average duration per invocation)
- Cost (cost per successful invocation)
- Status (current activity status)

The leaderboard reads from ~/.agent_metrics/metrics.json (or .agent_metrics.json
in the current directory) and refreshes every 500ms. It gracefully handles
missing metrics files by showing an 'initializing' state.

Usage:
    python scripts/leaderboard.py [--metrics-dir PATH] [--refresh-rate MS]
    python scripts/leaderboard.py --help
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
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


class LeaderboardRenderer:
    """Renders the agent leaderboard using rich components."""

    def __init__(self, console: Console):
        """Initialize the leaderboard renderer.

        Args:
            console: Rich console instance for rendering
        """
        self.console = console

    def create_leaderboard_table(self, agents: dict) -> Table:
        """Create leaderboard table sorted by XP with all agent stats.

        Args:
            agents: Dictionary of agent profiles from DashboardState

        Returns:
            Rich Table with agents sorted by XP descending
        """
        table = Table(
            title="Agent Leaderboard (Sorted by XP)",
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("Rank", style="cyan", width=6)
        table.add_column("Agent", style="cyan", width=15)
        table.add_column("XP", style="yellow", width=8, justify="right")
        table.add_column("Level", style="green", width=12)
        table.add_column("Success Rate", style="blue", width=14, justify="right")
        table.add_column("Avg Time", style="white", width=10, justify="right")
        table.add_column("Cost/Success", style="magenta", width=13, justify="right")
        table.add_column("Status", style="cyan", width=12)

        if not agents:
            table.add_row(
                "N/A", "No agents", "0", "Intern",
                "N/A", "N/A", "N/A", "Idle"
            )
            return table

        # Sort agents by XP (descending)
        sorted_agents = sorted(
            agents.items(),
            key=lambda x: x[1].get("xp", 0),
            reverse=True
        )

        # Render each agent with rank
        for rank, (agent_name, agent_data) in enumerate(sorted_agents, start=1):
            # Extract data
            xp = agent_data.get("xp", 0)
            level = agent_data.get("level", 1)
            success_rate = agent_data.get("success_rate", 0.0)
            avg_duration = agent_data.get("avg_duration_seconds", 0.0)
            cost_per_success = agent_data.get("cost_per_success_usd", 0.0)
            last_active = agent_data.get("last_active", "")

            # Determine status based on last_active
            status = self._determine_status(last_active)

            # Format success rate as percentage
            success_rate_str = f"{success_rate * 100:.1f}%"

            # Format average time
            avg_time_str = self._format_duration(avg_duration)

            # Format cost
            cost_str = f"${cost_per_success:.4f}" if cost_per_success > 0 else "N/A"

            # Format level title
            level_title = self._get_level_title(level)

            # Color agent name based on rank
            if rank == 1:
                agent_display = f"[gold1]{agent_name}[/gold1]"
                rank_display = f"[gold1]#{rank}[/gold1]"
            elif rank == 2:
                agent_display = f"[white]{agent_name}[/white]"
                rank_display = f"[white]#{rank}[/white]"
            elif rank == 3:
                agent_display = f"[#CD7F32]{agent_name}[/#CD7F32]"
                rank_display = f"[#CD7F32]#{rank}[/#CD7F32]"
            else:
                agent_display = agent_name
                rank_display = f"#{rank}"

            table.add_row(
                rank_display,
                agent_display,
                str(xp),
                f"[cyan]{level_title}[/cyan]",
                success_rate_str,
                avg_time_str,
                cost_str,
                status
            )

        return table

    def create_leaderboard_layout(self, state: dict) -> Layout:
        """Create complete leaderboard layout with header and table.

        Args:
            state: DashboardState dictionary

        Returns:
            Rich Layout with leaderboard components
        """
        layout = Layout()

        # Split into header and body
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="leaderboard")
        )

        # Populate components
        layout["header"].update(self.create_project_header(state))
        layout["leaderboard"].update(
            Panel(
                self.create_leaderboard_table(state.get("agents", {})),
                border_style="cyan"
            )
        )

        return layout

    def create_project_header(self, state: dict) -> Panel:
        """Create project header with project name and update time.

        Args:
            state: DashboardState dictionary

        Returns:
            Rich Panel with project header
        """
        project_name = state.get("project_name", "Unknown Project")
        updated_at = state.get("updated_at", "")
        total_agents = len(state.get("agents", {}))
        total_xp = sum(a.get("xp", 0) for a in state.get("agents", {}).values())

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
        text.append(f"Total Agents: ", style="bold")
        text.append(f"{total_agents}  ", style="cyan")
        text.append(f"Total XP: ", style="bold")
        text.append(f"{total_xp}\n", style="yellow bold")
        text.append(f"Last Updated: ", style="bold")
        text.append(f"{updated_str}", style="dim")

        return Panel(text, title="Agent Leaderboard", border_style="green")

    def create_initializing_layout(self) -> Layout:
        """Create layout for initializing state when metrics file doesn't exist.

        Returns:
            Rich Layout showing initializing state
        """
        layout = Layout()

        text = Text()
        text.append("\n\n", style="")
        text.append("⏳ Initializing Leaderboard...\n\n", style="bold yellow")
        text.append("Waiting for metrics file to be created.\n", style="dim")
        text.append("The leaderboard will update automatically when agents start working.\n", style="dim")
        text.append("\n", style="")
        text.append("Expected file locations:\n", style="bold")
        text.append("  • ~/.agent_metrics/metrics.json\n", style="cyan")
        text.append("  • ./.agent_metrics.json\n", style="cyan")

        panel = Panel(text, title="Agent Leaderboard", border_style="yellow")
        layout.update(panel)

        return layout

    @staticmethod
    def _determine_status(last_active: str) -> str:
        """Determine agent status based on last activity time.

        Args:
            last_active: ISO 8601 timestamp of last activity

        Returns:
            Status string with color formatting
        """
        if not last_active:
            return "[dim]Idle[/dim]"

        try:
            last_active_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            seconds_since = (now - last_active_dt).total_seconds()

            if seconds_since < 60:
                return "[green]Active[/green]"
            else:
                return "[dim]Idle[/dim]"
        except (ValueError, TypeError):
            return "[yellow]Unknown[/yellow]"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds into human-readable duration string.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted string like "5s" or "2m 30s"
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    @staticmethod
    def _get_level_title(level: int) -> str:
        """Get the title/rank name for a level.

        Args:
            level: Level number (1-8)

        Returns:
            Title string for the level
        """
        titles = {
            1: "Intern",
            2: "Junior",
            3: "Mid-Level",
            4: "Senior",
            5: "Staff",
            6: "Principal",
            7: "Distinguished",
            8: "Fellow",
        }

        return titles.get(level, "Unknown")


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


def run_leaderboard(
    metrics_path: Path,
    refresh_rate_ms: int = DEFAULT_REFRESH_RATE_MS
) -> None:
    """Run the live terminal leaderboard.

    Args:
        metrics_path: Path to metrics.json file
        refresh_rate_ms: Refresh rate in milliseconds (default: 500ms)
    """
    console = Console()
    renderer = LeaderboardRenderer(console)
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
                    # Render leaderboard with current state
                    live.update(renderer.create_leaderboard_layout(state))

                # Sleep until next refresh
                time.sleep(refresh_rate_sec)

        except KeyboardInterrupt:
            # Clean exit on Ctrl+C
            console.print("\n[yellow]Leaderboard stopped by user.[/yellow]")


def main():
    """Main entry point for the leaderboard CLI."""
    parser = argparse.ArgumentParser(
        description="Live terminal leaderboard for agent status monitoring sorted by XP"
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
    console.print(f"[cyan]Starting Agent Leaderboard...[/cyan]")
    console.print(f"[dim]Monitoring: {metrics_path}[/dim]")
    console.print(f"[dim]Refresh rate: {args.refresh_rate}ms[/dim]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    time.sleep(1)  # Brief pause before starting live display

    # Run leaderboard
    run_leaderboard(metrics_path, args.refresh_rate)


if __name__ == "__main__":
    main()
