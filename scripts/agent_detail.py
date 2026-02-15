#!/usr/bin/env python3
"""CLI Agent Detail/Drill-Down View for Agent Status Monitoring.

This module provides a detailed agent profile view showing:
- Agent profile (name, level, XP, rank)
- Success rate and performance stats
- Strengths and weaknesses
- Recent events/activities
- Achievements earned

The agent detail view is accessed via the --agent flag and displays comprehensive
information about a single agent by reading from the metrics file.

Usage:
    python scripts/agent_detail.py --agent <agent_name> [--metrics-dir PATH]
    python scripts/agent_detail.py --agent coding
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns

# Default paths
DEFAULT_METRICS_DIR = Path.home() / ".agent_metrics"
DEFAULT_METRICS_FILE = "metrics.json"

# Level titles
LEVEL_TITLES = {
    1: "Intern",
    2: "Junior",
    3: "Mid-Level",
    4: "Senior",
    5: "Staff",
    6: "Principal",
    7: "Distinguished",
    8: "Fellow",
}


class AgentDetailRenderer:
    """Renders detailed agent profile view using rich components."""

    def __init__(self, console: Console):
        """Initialize the agent detail renderer.

        Args:
            console: Rich console instance for rendering
        """
        self.console = console

    def get_level_title(self, level: int) -> str:
        """Get the human-readable title for an agent level.

        Args:
            level: Numeric agent level

        Returns:
            Title string (e.g., "Mid-Level") or "Unknown" if level not found
        """
        return LEVEL_TITLES.get(level, "Unknown")

    def create_profile_panel(self, agent_data: Dict[str, Any], agent_name: str) -> Panel:
        """Create agent profile panel with basic information.

        Args:
            agent_data: Agent data dictionary from metrics
            agent_name: Name of the agent

        Returns:
            Rich Panel with agent profile information
        """
        text = Text()

        # Agent name header
        text.append(f"{agent_name}\n", style="bold cyan underline")

        # Basic stats
        xp = agent_data.get("xp", 0)
        level = agent_data.get("level", 1)
        level_title = self.get_level_title(level)

        text.append("Experience (XP): ", style="bold")
        text.append(f"{xp} XP (Level {level} - {level_title})\n", style="cyan")

        # Calculate rank/percentile based on position
        text.append("Current Streak: ", style="bold")
        current_streak = agent_data.get("current_streak", 0)
        best_streak = agent_data.get("best_streak", 0)
        text.append(f"{current_streak} (Best: {best_streak})\n", style="yellow")

        return Panel(text, title="Agent Profile", border_style="cyan")

    def create_performance_panel(self, agent_data: Dict[str, Any]) -> Panel:
        """Create performance metrics panel.

        Args:
            agent_data: Agent data dictionary from metrics

        Returns:
            Rich Panel with performance statistics
        """
        text = Text()

        # Success rate
        success_rate = agent_data.get("success_rate", 0.0)
        total_invocations = agent_data.get("total_invocations", 0)
        successful_invocations = agent_data.get("successful_invocations", 0)
        failed_invocations = agent_data.get("failed_invocations", 0)

        text.append("Success Rate: ", style="bold")
        if success_rate >= 0.9:
            style = "green"
        elif success_rate >= 0.7:
            style = "yellow"
        else:
            style = "red"
        text.append(f"{success_rate * 100:.1f}%\n", style=style)

        text.append("Invocations: ", style="bold")
        text.append(f"{successful_invocations} successful, {failed_invocations} failed (Total: {total_invocations})\n", style="cyan")

        # Performance metrics
        text.append("Average Duration: ", style="bold")
        avg_duration = agent_data.get("avg_duration_seconds", 0.0)
        text.append(f"{self._format_duration(avg_duration)}\n", style="cyan")

        text.append("Tokens Per Call: ", style="bold")
        avg_tokens = agent_data.get("avg_tokens_per_call", 0.0)
        text.append(f"{avg_tokens:.0f} tokens\n", style="cyan")

        text.append("Cost Per Success: ", style="bold")
        cost = agent_data.get("cost_per_success_usd", 0.0)
        text.append(f"${cost:.4f}\n", style="cyan")

        # Total stats
        total_tokens = agent_data.get("total_tokens", 0)
        total_cost = agent_data.get("total_cost_usd", 0.0)
        total_duration = agent_data.get("total_duration_seconds", 0.0)

        text.append("\nTotal Stats:\n", style="bold underline")
        text.append(f"  • Tokens: {total_tokens:,}\n", style="dim")
        text.append(f"  • Cost: ${total_cost:.4f}\n", style="dim")
        text.append(f"  • Duration: {self._format_duration(total_duration)}\n", style="dim")

        return Panel(text, title="Performance Metrics", border_style="magenta")

    def create_strengths_weaknesses_panel(self, agent_data: Dict[str, Any]) -> Panel:
        """Create strengths and weaknesses panel.

        Args:
            agent_data: Agent data dictionary from metrics

        Returns:
            Rich Panel with strengths and weaknesses
        """
        text = Text()

        strengths = agent_data.get("strengths", [])
        weaknesses = agent_data.get("weaknesses", [])

        # Strengths
        text.append("Strengths:\n", style="bold green")
        if strengths:
            for strength in strengths:
                # Convert snake_case to Title Case
                display_name = " ".join(word.capitalize() for word in strength.split("_"))
                text.append(f"  ✓ {display_name}\n", style="green")
        else:
            text.append("  [dim]None identified[/dim]\n")

        text.append("\nWeaknesses:\n", style="bold red")
        if weaknesses:
            for weakness in weaknesses:
                # Convert snake_case to Title Case
                display_name = " ".join(word.capitalize() for word in weakness.split("_"))
                text.append(f"  ✗ {display_name}\n", style="red")
        else:
            text.append("  [dim]None identified[/dim]\n")

        return Panel(text, title="Strengths & Weaknesses", border_style="yellow")

    def create_achievements_panel(self, agent_data: Dict[str, Any]) -> Panel:
        """Create achievements panel.

        Args:
            agent_data: Agent data dictionary from metrics

        Returns:
            Rich Panel with achievements
        """
        text = Text()

        achievements = agent_data.get("achievements", [])

        if achievements:
            for achievement in achievements:
                # Convert snake_case to Title Case
                display_name = " ".join(word.capitalize() for word in achievement.split("_"))
                text.append(f"  🏆 {display_name}\n", style="yellow")
        else:
            text.append("  [dim]No achievements earned yet[/dim]\n")

        text.append(f"\nTotal Achievements: {len(achievements)}", style="dim")

        return Panel(text, title="Achievements", border_style="yellow")

    def create_recent_events_table(self, events: List[Dict[str, Any]], agent_name: str, limit: int = 10) -> Table:
        """Create table of recent events for this agent.

        Args:
            events: List of all events from metrics
            agent_name: Name of agent to filter for
            limit: Maximum number of events to show

        Returns:
            Rich Table with recent events
        """
        table = Table(title=f"Recent Events ({agent_name})", show_header=True, header_style="bold magenta")
        table.add_column("Time", style="dim", width=20)
        table.add_column("Ticket", style="cyan", width=12)
        table.add_column("Status", style="white", width=10)
        table.add_column("Tokens", style="yellow", width=10)
        table.add_column("Duration", style="green", width=12)

        # Filter events for this agent and get most recent
        agent_events = [e for e in events if e.get("agent_name") == agent_name]
        agent_events = agent_events[-limit:] if len(agent_events) > limit else agent_events
        agent_events = list(reversed(agent_events))  # Most recent first

        if not agent_events:
            table.add_row("No events", "N/A", "N/A", "N/A", "N/A")
            return table

        now = datetime.now(timezone.utc)
        for event in agent_events:
            # Format time
            started_at = event.get("started_at", "")
            if started_at:
                try:
                    event_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    time_ago = self._format_time_ago((now - event_dt).total_seconds())
                    time_str = time_ago
                except (ValueError, TypeError):
                    time_str = "Unknown"
            else:
                time_str = "Unknown"

            # Status with color
            status = event.get("status", "unknown").upper()
            if status == "SUCCESS":
                status_str = f"[green]{status}[/green]"
            elif status == "ERROR":
                status_str = f"[red]{status}[/red]"
            else:
                status_str = f"[yellow]{status}[/yellow]"

            ticket = event.get("ticket_key", "N/A")
            tokens = event.get("total_tokens", 0)
            duration = event.get("duration_seconds", 0)

            table.add_row(
                time_str,
                ticket,
                status_str,
                f"{tokens:,}",
                f"{self._format_duration(duration)}"
            )

        return table

    def create_detail_view(self, agent_data: Dict[str, Any], agent_name: str, events: List[Dict[str, Any]]) -> Panel:
        """Create complete agent detail view.

        Args:
            agent_data: Agent data dictionary
            agent_name: Name of the agent
            events: List of all events

        Returns:
            Rich Panel with complete agent detail view
        """
        # Create profile and performance panels side by side
        profile_panel = self.create_profile_panel(agent_data, agent_name)
        performance_panel = self.create_performance_panel(agent_data)

        # Create achievements and strengths panels
        achievements_panel = self.create_achievements_panel(agent_data)
        strengths_panel = self.create_strengths_weaknesses_panel(agent_data)

        # Combine panels for display
        columns = Columns([profile_panel, performance_panel])

        # Build the main view text
        text = Text()
        text.append(str(columns))

        return Panel(text, title=f"Agent Detail: {agent_name}", border_style="blue")

    def render_agent_detail(
        self,
        agent_name: str,
        agent_data: Dict[str, Any],
        state: Dict[str, Any]
    ) -> None:
        """Render and display complete agent detail view.

        Args:
            agent_name: Name of the agent
            agent_data: Agent data dictionary from metrics
            state: Complete metrics state dictionary
        """
        events = state.get("events", [])

        # Create and display panels
        self.console.print()
        self.console.print(self.create_profile_panel(agent_data, agent_name))
        self.console.print()
        self.console.print(self.create_performance_panel(agent_data))
        self.console.print()

        # Strengths and achievements in columns
        strengths_panel = self.create_strengths_weaknesses_panel(agent_data)
        achievements_panel = self.create_achievements_panel(agent_data)
        self.console.print(Columns([strengths_panel, achievements_panel]))
        self.console.print()

        # Recent events table
        self.console.print(self.create_recent_events_table(events, agent_name))
        self.console.print()

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds into human-readable duration string.

        Args:
            seconds: Number of seconds

        Returns:
            Formatted string like "5m 30s" or "1h 30m"
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            mins = int(seconds) // 60
            secs = int(seconds) % 60
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds) // 3600
            remaining = int(seconds) % 3600
            mins = remaining // 60
            return f"{hours}h {mins}m"

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


def display_agent_detail(
    agent_name: str,
    metrics_path: Path
) -> None:
    """Display detailed view for a specific agent.

    Args:
        agent_name: Name of agent to display
        metrics_path: Path to metrics.json file
    """
    console = Console()
    renderer = AgentDetailRenderer(console)
    monitor = MetricsFileMonitor(metrics_path)

    # Load metrics
    state = monitor.load_metrics()

    if state is None:
        console.print("[red]Error: Could not load metrics file[/red]")
        console.print(f"[dim]Expected file at: {metrics_path}[/dim]")
        return

    # Find agent in metrics
    agents = state.get("agents", {})
    if agent_name not in agents:
        console.print(f"[red]Error: Agent '{agent_name}' not found[/red]")
        console.print(f"[dim]Available agents: {', '.join(sorted(agents.keys()))}[/dim]")
        return

    agent_data = agents[agent_name]
    events = state.get("events", [])

    # Create and display panels
    console.print()
    console.print(renderer.create_profile_panel(agent_data, agent_name))
    console.print()
    console.print(renderer.create_performance_panel(agent_data))
    console.print()

    # Strengths and achievements in columns
    strengths_panel = renderer.create_strengths_weaknesses_panel(agent_data)
    achievements_panel = renderer.create_achievements_panel(agent_data)
    console.print(Columns([strengths_panel, achievements_panel]))
    console.print()

    # Recent events table
    console.print(renderer.create_recent_events_table(events, agent_name))
    console.print()


def main():
    """Main entry point for the agent detail CLI."""
    parser = argparse.ArgumentParser(
        description="Display detailed profile for a specific agent"
    )
    parser.add_argument(
        "--agent",
        type=str,
        required=True,
        help="Name of the agent to display (e.g., 'coding', 'github', 'linear')"
    )
    parser.add_argument(
        "--metrics-dir",
        type=Path,
        default=None,
        help="Directory containing metrics.json (default: ~/.agent_metrics or ./.agent_metrics.json)"
    )

    args = parser.parse_args()

    # Find metrics file
    metrics_path = find_metrics_file(args.metrics_dir)

    # Display agent detail
    display_agent_detail(args.agent, metrics_path)


if __name__ == "__main__":
    main()
