#!/usr/bin/env python3
"""CLI Achievement Display for Agent Status Dashboard.

This module provides a real-time terminal achievement view using the rich library,
displaying agent achievements with emoji icons, unlock status, descriptions, and
progress indicators. Achievements are sorted by unlock status (unlocked first)
and provide visual feedback on agent accomplishments.

Supported Achievements (12 total):
1. first_blood (🩸) - First successful invocation
2. century_club (💯) - 100 successful invocations
3. perfect_day (✨) - 10+ invocations in one session, 0 errors
4. speed_demon (⚡) - 5 consecutive completions under 30s
5. comeback_kid (🔥) - Success immediately after 3+ consecutive errors
6. big_spender (💰) - Single invocation over $1.00
7. penny_pincher (🪙) - 50+ successes at < $0.01 each
8. marathon (🏃) - 100+ invocations in a single project
9. polyglot (🌍) - Agent used across 5+ different ticket types
10. night_owl (🌙) - Invocation between 00:00-05:00 local time
11. streak_10 (🔥) - 10 consecutive successes
12. streak_25 (⭐) - 25 consecutive successes

Usage:
    python scripts/achievements.py [--agent AGENT_NAME] [--metrics-dir PATH] [--refresh-rate MS]
    python scripts/achievements.py --help
    python scripts/achievements.py --agent coding
    python scripts/achievements.py --all
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Tuple

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

# Achievement definitions with emoji icons and descriptions
ACHIEVEMENT_ICONS = {
    "first_blood": "🩸",
    "century_club": "💯",
    "perfect_day": "✨",
    "speed_demon": "⚡",
    "comeback_kid": "🔥",
    "big_spender": "💰",
    "penny_pincher": "🪙",
    "marathon": "🏃",
    "polyglot": "🌍",
    "night_owl": "🌙",
    "streak_10": "🔥",
    "streak_25": "⭐",
}

ACHIEVEMENT_NAMES = {
    "first_blood": "First Blood",
    "century_club": "Century Club",
    "perfect_day": "Perfect Day",
    "speed_demon": "Speed Demon",
    "comeback_kid": "Comeback Kid",
    "big_spender": "Big Spender",
    "penny_pincher": "Penny Pincher",
    "marathon": "Marathon Runner",
    "polyglot": "Polyglot",
    "night_owl": "Night Owl",
    "streak_10": "On Fire",
    "streak_25": "Unstoppable",
}

ACHIEVEMENT_DESCRIPTIONS = {
    "first_blood": "First successful invocation",
    "century_club": "100 successful invocations",
    "perfect_day": "10+ invocations in one session, 0 errors",
    "speed_demon": "5 consecutive completions under 30s",
    "comeback_kid": "Success immediately after 3+ consecutive errors",
    "big_spender": "Single invocation over $1.00",
    "penny_pincher": "50+ successes at < $0.01 each",
    "marathon": "100+ invocations in a single project",
    "polyglot": "Agent used across 5+ different ticket types",
    "night_owl": "Invocation between 00:00-05:00 local time",
    "streak_10": "10 consecutive successes",
    "streak_25": "25 consecutive successes",
}


class AchievementRenderer:
    """Renders achievement displays using rich components."""

    def __init__(self, console: Console):
        """Initialize the achievement renderer.

        Args:
            console: Rich console instance for rendering
        """
        self.console = console

    def create_achievements_grid(self, agent_name: str, agent_data: Dict) -> Panel:
        """Create a grid display of all achievements for an agent.

        Args:
            agent_name: Name of the agent
            agent_data: Agent data dictionary from metrics

        Returns:
            Rich Panel with achievement grid display
        """
        achievements = agent_data.get("achievements", [])
        total_xp = agent_data.get("xp", 0)

        text = Text()
        text.append(f"Agent: ", style="bold")
        text.append(f"{agent_name}\n", style="cyan bold")
        text.append(f"XP: ", style="bold")
        text.append(f"{total_xp}\n", style="yellow bold")
        text.append("\n", style="")

        # Get all possible achievements
        all_achievement_ids = list(ACHIEVEMENT_ICONS.keys())

        # Create two lists: unlocked and locked
        unlocked = sorted([a for a in achievements if a in ACHIEVEMENT_ICONS])
        locked = sorted([a for a in all_achievement_ids if a not in unlocked])

        # Display unlocked achievements
        if unlocked:
            text.append("Unlocked Achievements\n", style="bold green")
            text.append("=" * 50 + "\n", style="dim green")
            for achievement_id in unlocked:
                icon = ACHIEVEMENT_ICONS[achievement_id]
                name = ACHIEVEMENT_NAMES[achievement_id]
                description = ACHIEVEMENT_DESCRIPTIONS[achievement_id]
                text.append(f"{icon} ", style="")
                text.append(f"{name}\n", style="bold yellow")
                text.append(f"   {description}\n", style="dim")
            text.append("\n", style="")
        else:
            text.append("No achievements unlocked yet.\n", style="dim yellow")
            text.append("\n", style="")

        # Display locked achievements
        if locked:
            text.append("Locked Achievements\n", style="bold dim")
            text.append("=" * 50 + "\n", style="dim")
            for achievement_id in locked:
                icon = ACHIEVEMENT_ICONS[achievement_id]
                name = ACHIEVEMENT_NAMES[achievement_id]
                description = ACHIEVEMENT_DESCRIPTIONS[achievement_id]
                text.append(f"🔒 ", style="dim")
                text.append(f"{name}\n", style="dim")
                text.append(f"   {description}\n", style="dim")
            text.append("\n", style="")

        # Summary
        text.append("Summary\n", style="bold cyan")
        text.append("=" * 50 + "\n", style="dim cyan")
        text.append(f"Unlocked: {len(unlocked)}/12\n", style="green")
        text.append(f"Progress: ", style="")
        progress_bar = self._create_progress_bar(len(unlocked), 12)
        text.append(f"{progress_bar}\n", style="cyan")

        return Panel(text, title=f"Achievements - {agent_name}", border_style="cyan")

    def create_all_agents_achievements(self, agents: Dict[str, Dict]) -> Panel:
        """Create achievement summary for all agents.

        Args:
            agents: Dictionary of all agent data

        Returns:
            Rich Panel with all agents' achievements
        """
        text = Text()
        text.append("Agent Achievement Summary\n", style="bold cyan")
        text.append("=" * 60 + "\n\n", style="dim cyan")

        # Sort agents by number of achievements (descending)
        agent_list = [
            (name, data.get("achievements", []), data.get("xp", 0))
            for name, data in agents.items()
        ]
        agent_list.sort(key=lambda x: len(x[1]), reverse=True)

        for agent_name, achievements, xp in agent_list:
            unlocked = len([a for a in achievements if a in ACHIEVEMENT_ICONS])
            progress_bar = self._create_progress_bar(unlocked, 12)

            text.append(f"{agent_name:<15} ", style="cyan bold")
            text.append(f"[XP: {xp:<4}] ", style="yellow")
            text.append(f"{progress_bar} ", style="cyan")
            text.append(f"({unlocked}/12)\n", style="green")

            # Show last 3 achievements for this agent
            if achievements:
                recent = sorted(achievements)[-3:]
                for ach in recent:
                    icon = ACHIEVEMENT_ICONS.get(ach, "🏆")
                    name = ACHIEVEMENT_NAMES.get(ach, ach)
                    text.append(f"  {icon} {name}\n", style="dim yellow")

        return Panel(text, title="All Agents", border_style="cyan")

    def create_achievement_detail(self, achievement_id: str) -> Panel:
        """Create detailed information about a specific achievement.

        Args:
            achievement_id: ID of the achievement to display

        Returns:
            Rich Panel with achievement details
        """
        if achievement_id not in ACHIEVEMENT_ICONS:
            return Panel(
                Text("Unknown achievement", style="red"),
                title="Achievement Details",
                border_style="red"
            )

        text = Text()
        icon = ACHIEVEMENT_ICONS[achievement_id]
        name = ACHIEVEMENT_NAMES[achievement_id]
        description = ACHIEVEMENT_DESCRIPTIONS[achievement_id]

        text.append(f"{icon} {name}\n", style="bold yellow")
        text.append("=" * 50 + "\n", style="dim")
        text.append(f"\nCondition:\n", style="bold")
        text.append(f"{description}\n", style="white")
        text.append(f"\nAchievement ID: {achievement_id}\n", style="dim")

        return Panel(text, title="Achievement Details", border_style="yellow")

    def create_initializing_layout(self) -> Layout:
        """Create layout for initializing state when metrics file doesn't exist.

        Returns:
            Rich Layout showing initializing state
        """
        layout = Layout()

        text = Text()
        text.append("\n\n", style="")
        text.append("⏳ Initializing Achievement View...\n\n", style="bold yellow")
        text.append("Waiting for metrics file to be created.\n", style="dim")
        text.append("Achievements will be displayed once agents start working.\n", style="dim")
        text.append("\n", style="")
        text.append("Expected file locations:\n", style="bold")
        text.append("  • ~/.agent_metrics/metrics.json\n", style="cyan")
        text.append("  • ./.agent_metrics.json\n", style="cyan")

        panel = Panel(text, title="Achievement View", border_style="yellow")
        layout.update(panel)

        return layout

    @staticmethod
    def _create_progress_bar(current: int, total: int, width: int = 20) -> str:
        """Create a visual progress bar.

        Args:
            current: Current progress value
            total: Total value
            width: Width of the progress bar

        Returns:
            ASCII progress bar string
        """
        filled = int((current / total) * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"


class MetricsFileMonitor:
    """Monitors and loads metrics from the metrics file."""

    def __init__(self, metrics_path: Path):
        """Initialize metrics file monitor.

        Args:
            metrics_path: Path to the metrics.json file
        """
        self.metrics_path = metrics_path
        self._last_modified_time = 0.0

    def load_metrics(self) -> Optional[Dict]:
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


def display_agent_achievements(
    agent_name: str,
    metrics_path: Path,
    refresh_rate_ms: int = DEFAULT_REFRESH_RATE_MS
) -> None:
    """Display achievements for a specific agent.

    Args:
        agent_name: Name of the agent to display
        metrics_path: Path to metrics.json file
        refresh_rate_ms: Refresh rate in milliseconds
    """
    console = Console()
    renderer = AchievementRenderer(console)
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
                state = monitor.load_metrics()

                if state is None:
                    live.update(renderer.create_initializing_layout())
                else:
                    agents = state.get("agents", {})
                    if agent_name not in agents:
                        text = Text(
                            f"Agent '{agent_name}' not found in metrics.\n"
                            f"Available agents: {', '.join(agents.keys())}",
                            style="red"
                        )
                        live.update(Panel(text, border_style="red"))
                    else:
                        panel = renderer.create_achievements_grid(
                            agent_name,
                            agents[agent_name]
                        )
                        live.update(panel)

                time.sleep(refresh_rate_sec)

        except KeyboardInterrupt:
            console.print("\n[yellow]Achievement view stopped by user.[/yellow]")


def display_all_agents_achievements(
    metrics_path: Path,
    refresh_rate_ms: int = DEFAULT_REFRESH_RATE_MS
) -> None:
    """Display achievement summary for all agents.

    Args:
        metrics_path: Path to metrics.json file
        refresh_rate_ms: Refresh rate in milliseconds
    """
    console = Console()
    renderer = AchievementRenderer(console)
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
                state = monitor.load_metrics()

                if state is None:
                    live.update(renderer.create_initializing_layout())
                else:
                    agents = state.get("agents", {})
                    if not agents:
                        text = Text("No agents found in metrics.", style="yellow")
                        live.update(Panel(text, border_style="yellow"))
                    else:
                        panel = renderer.create_all_agents_achievements(agents)
                        live.update(panel)

                time.sleep(refresh_rate_sec)

        except KeyboardInterrupt:
            console.print("\n[yellow]Achievement view stopped by user.[/yellow]")


def main():
    """Main entry point for the achievements CLI."""
    parser = argparse.ArgumentParser(
        description="Display achievement badges with emoji icons and unlock status"
    )
    parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Display achievements for a specific agent"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Display achievement summary for all agents"
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
    console.print(f"[cyan]Starting Achievement Display...[/cyan]")
    console.print(f"[dim]Monitoring: {metrics_path}[/dim]")
    console.print(f"[dim]Refresh rate: {args.refresh_rate}ms[/dim]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    time.sleep(1)  # Brief pause before starting live display

    # Determine which view to show
    if args.agent:
        display_agent_achievements(args.agent, metrics_path, args.refresh_rate)
    elif args.all:
        display_all_agents_achievements(metrics_path, args.refresh_rate)
    else:
        # Default: show all agents
        display_all_agents_achievements(metrics_path, args.refresh_rate)


if __name__ == "__main__":
    main()
