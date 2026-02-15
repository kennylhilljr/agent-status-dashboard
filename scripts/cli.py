#!/usr/bin/env python3
"""Unified Dashboard CLI with multiple modes of operation.

This module provides a comprehensive command-line interface for the Agent Status Dashboard
with support for multiple operational modes:

- DEFAULT (no flags): Show main dashboard with live updates (--refresh-rate configurable)
- --once: Run dashboard once without live updates
- --json: Output metrics as JSON instead of rich terminal UI
- --agent NAME: Show detailed view for a specific agent
- --leaderboard: Show leaderboard view sorted by XP
- --achievements: Show achievements view

Usage:
    python scripts/cli.py                          # Live dashboard
    python scripts/cli.py --once                   # Single dashboard update
    python scripts/cli.py --json                   # Output JSON metrics
    python scripts/cli.py --agent coding           # Agent detail view
    python scripts/cli.py --leaderboard            # Leaderboard view
    python scripts/cli.py --achievements           # Achievements view
    python scripts/cli.py --help                   # Show all options
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Import individual module classes
from dashboard import DashboardRenderer as DashboardRenderer_Main
from dashboard import MetricsFileMonitor
from dashboard import find_metrics_file as find_metrics_file_main
from dashboard import DEFAULT_REFRESH_RATE_MS as DASHBOARD_REFRESH_RATE_MS
from leaderboard import LeaderboardRenderer
from agent_detail import AgentDetailRenderer
from achievements import AchievementRenderer

# Default paths
DEFAULT_METRICS_DIR = Path.home() / ".agent_metrics"
DEFAULT_METRICS_FILE = "metrics.json"


class UnifiedDashboardCLI:
    """Unified CLI handler for all dashboard modes."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize the unified CLI.

        Args:
            console: Optional Rich console instance
        """
        self.console = console or Console()

    def run_live_dashboard(
        self,
        metrics_path: Path,
        refresh_rate_ms: int = DASHBOARD_REFRESH_RATE_MS
    ) -> None:
        """Run the live dashboard with continuous updates.

        Args:
            metrics_path: Path to metrics.json file
            refresh_rate_ms: Refresh rate in milliseconds
        """
        renderer = DashboardRenderer_Main(self.console)
        monitor = MetricsFileMonitor(metrics_path)
        refresh_rate_sec = refresh_rate_ms / 1000.0

        with Live(
            renderer.create_initializing_layout(),
            console=self.console,
            refresh_per_second=1.0 / refresh_rate_sec,
            screen=True
        ) as live:
            try:
                while True:
                    state = monitor.load_metrics()
                    if state is None:
                        live.update(renderer.create_initializing_layout())
                    else:
                        live.update(renderer.create_dashboard_layout(state))
                    time.sleep(refresh_rate_sec)
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Dashboard stopped by user.[/yellow]")

    def run_once_dashboard(self, metrics_path: Path) -> None:
        """Run the dashboard once without live updates.

        Args:
            metrics_path: Path to metrics.json file
        """
        renderer = DashboardRenderer_Main(self.console)
        monitor = MetricsFileMonitor(metrics_path)

        state = monitor.load_metrics()
        if state is None:
            self.console.print(renderer.create_initializing_layout())
        else:
            self.console.print(renderer.create_dashboard_layout(state))

    def run_json_output(self, metrics_path: Path) -> None:
        """Output metrics as JSON to stdout.

        Args:
            metrics_path: Path to metrics.json file
        """
        monitor = MetricsFileMonitor(metrics_path)
        state = monitor.load_metrics()

        if state is None:
            self.console.print(
                json.dumps({"error": "Metrics file not found or invalid"}, indent=2),
                soft_wrap=True
            )
        else:
            # Output raw JSON
            self.console.print(json.dumps(state, indent=2), soft_wrap=True)

    def run_agent_detail(self, metrics_path: Path, agent_name: str) -> None:
        """Show detailed view for a specific agent.

        Args:
            metrics_path: Path to metrics.json file
            agent_name: Name of the agent to display
        """
        renderer = AgentDetailRenderer(self.console)
        monitor = MetricsFileMonitor(metrics_path)

        state = monitor.load_metrics()
        if state is None:
            self.console.print("[red]Error: Metrics file not found[/red]")
            return

        agents = state.get("agents", {})
        if agent_name not in agents:
            self.console.print(f"[red]Error: Agent '{agent_name}' not found[/red]")
            self.console.print(f"[dim]Available agents: {', '.join(agents.keys())}[/dim]")
            return

        agent_data = agents[agent_name]
        renderer.render_agent_detail(agent_name, agent_data, state)

    def run_leaderboard(
        self,
        metrics_path: Path,
        refresh_rate_ms: int = DASHBOARD_REFRESH_RATE_MS,
        once: bool = False
    ) -> None:
        """Show leaderboard view.

        Args:
            metrics_path: Path to metrics.json file
            refresh_rate_ms: Refresh rate in milliseconds
            once: If True, show once and exit; if False, show live updates
        """
        renderer = LeaderboardRenderer(self.console)
        monitor = MetricsFileMonitor(metrics_path)

        if once:
            # Single update
            state = monitor.load_metrics()
            if state is None:
                self.console.print(renderer.create_initializing_layout())
            else:
                self.console.print(renderer.create_leaderboard_layout(state))
        else:
            # Live updates
            refresh_rate_sec = refresh_rate_ms / 1000.0

            with Live(
                renderer.create_initializing_layout(),
                console=self.console,
                refresh_per_second=1.0 / refresh_rate_sec,
                screen=True
            ) as live:
                try:
                    while True:
                        state = monitor.load_metrics()
                        if state is None:
                            live.update(renderer.create_initializing_layout())
                        else:
                            live.update(renderer.create_leaderboard_layout(state))
                        time.sleep(refresh_rate_sec)
                except KeyboardInterrupt:
                    self.console.print(
                        "\n[yellow]Leaderboard stopped by user.[/yellow]"
                    )

    def run_achievements(
        self,
        metrics_path: Path,
        agent_name: Optional[str] = None,
        refresh_rate_ms: int = DASHBOARD_REFRESH_RATE_MS,
        once: bool = False
    ) -> None:
        """Show achievements view.

        Args:
            metrics_path: Path to metrics.json file
            agent_name: Specific agent name or None for all agents
            refresh_rate_ms: Refresh rate in milliseconds
            once: If True, show once and exit; if False, show live updates
        """
        renderer = AchievementRenderer(self.console)
        monitor = MetricsFileMonitor(metrics_path)

        if once:
            # Single update
            state = monitor.load_metrics()
            if state is None:
                self.console.print("[red]Error: Metrics file not found[/red]")
            else:
                self._render_achievements_single(state, agent_name, renderer)
        else:
            # Live updates
            refresh_rate_sec = refresh_rate_ms / 1000.0

            with Live(
                self.console.render(Text("Initializing achievements view...",
                                         style="bold yellow")),
                console=self.console,
                refresh_per_second=1.0 / refresh_rate_sec,
                screen=True
            ) as live:
                try:
                    while True:
                        state = monitor.load_metrics()
                        if state is None:
                            live.update(Text("Initializing achievements view...",
                                             style="bold yellow"))
                        else:
                            content = self._get_achievements_content(
                                state, agent_name, renderer
                            )
                            live.update(content)
                        time.sleep(refresh_rate_sec)
                except KeyboardInterrupt:
                    self.console.print(
                        "\n[yellow]Achievements view stopped by user.[/yellow]"
                    )

    def _render_achievements_single(
        self,
        state: Dict[str, Any],
        agent_name: Optional[str],
        renderer: AchievementRenderer
    ) -> None:
        """Render achievements for single display.

        Args:
            state: Metrics state dictionary
            agent_name: Optional agent name filter
            renderer: AchievementRenderer instance
        """
        agents = state.get("agents", {})

        if agent_name:
            if agent_name not in agents:
                self.console.print(f"[red]Error: Agent '{agent_name}' not found[/red]")
                return
            agent_data = agents[agent_name]
            self.console.print(
                renderer.create_achievements_grid(agent_name, agent_data)
            )
        else:
            # Show achievements for all agents
            layout = Layout()
            layout.split_column(
                Layout(name="header", size=5),
                Layout(name="achievements")
            )

            # Header
            project_name = state.get("project_name", "Unknown Project")
            total_agents = len(agents)
            text = Text()
            text.append(f"Project: ", style="bold")
            text.append(f"{project_name}\n", style="cyan bold")
            text.append(f"Total Agents: ", style="bold")
            text.append(f"{total_agents}", style="cyan")
            layout["header"].update(
                Panel(text, title="Achievements Dashboard", border_style="green")
            )

            # Achievements grid
            achievements_text = Text()
            for name, agent_data in sorted(agents.items()):
                achievements_text.append(f"\n{name}:\n", style="bold cyan")
                achievements = agent_data.get("achievements", [])
                if achievements:
                    for ach in achievements:
                        achievements_text.append(f"  • {ach}\n", style="yellow")
                else:
                    achievements_text.append("  No achievements yet\n", style="dim")

            layout["achievements"].update(
                Panel(achievements_text, border_style="cyan")
            )
            self.console.print(layout)

    def _get_achievements_content(
        self,
        state: Dict[str, Any],
        agent_name: Optional[str],
        renderer: AchievementRenderer
    ) -> Panel:
        """Get achievements content for live display.

        Args:
            state: Metrics state dictionary
            agent_name: Optional agent name filter
            renderer: AchievementRenderer instance

        Returns:
            Rich Panel with achievements content
        """
        agents = state.get("agents", {})

        if agent_name:
            if agent_name not in agents:
                return Panel(
                    f"Agent '{agent_name}' not found",
                    border_style="red"
                )
            agent_data = agents[agent_name]
            return renderer.create_achievements_grid(agent_name, agent_data)
        else:
            # All agents
            text = Text()
            for name, agent_data in sorted(agents.items()):
                text.append(f"{name}: ", style="bold cyan")
                achievements = agent_data.get("achievements", [])
                if achievements:
                    text.append(f"{len(achievements)} achievements\n", style="yellow")
                else:
                    text.append("No achievements\n", style="dim")
            return Panel(text, title="Achievements Overview", border_style="cyan")


def main():
    """Main entry point for the unified dashboard CLI."""
    parser = argparse.ArgumentParser(
        description="Unified Agent Status Dashboard CLI with multiple modes",
        epilog="Examples:\n"
               "  %(prog)s                         # Live dashboard\n"
               "  %(prog)s --once                  # Single dashboard update\n"
               "  %(prog)s --json                  # Output JSON metrics\n"
               "  %(prog)s --agent coding          # Agent detail view\n"
               "  %(prog)s --leaderboard           # Live leaderboard\n"
               "  %(prog)s --leaderboard --once    # Single leaderboard update\n"
               "  %(prog)s --achievements          # Achievements view",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Mode arguments (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--json",
        action="store_true",
        help="Output metrics as JSON to stdout"
    )
    mode_group.add_argument(
        "--agent",
        type=str,
        metavar="NAME",
        help="Show detailed view for specific agent"
    )
    mode_group.add_argument(
        "--leaderboard",
        action="store_true",
        help="Show leaderboard view sorted by XP"
    )
    mode_group.add_argument(
        "--achievements",
        action="store_true",
        help="Show achievements view (optionally filtered by --agent)"
    )

    # Common arguments
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run without live updates (applies to dashboard, leaderboard, achievements)"
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
        default=DASHBOARD_REFRESH_RATE_MS,
        help=f"Refresh rate in milliseconds (default: {DASHBOARD_REFRESH_RATE_MS}ms, applies to live modes)"
    )

    args = parser.parse_args()

    # Find metrics file
    metrics_path = find_metrics_file_main(args.metrics_dir)

    # Create CLI instance
    console = Console()
    cli = UnifiedDashboardCLI(console)

    # Print startup info for non-JSON modes
    if not args.json:
        console.print(f"[cyan]Agent Status Dashboard CLI[/cyan]")
        console.print(f"[dim]Metrics file: {metrics_path}[/dim]")

    # Route to appropriate mode
    try:
        if args.json:
            cli.run_json_output(metrics_path)
        elif args.agent:
            cli.run_agent_detail(metrics_path, args.agent)
        elif args.leaderboard:
            cli.run_leaderboard(metrics_path, args.refresh_rate, once=args.once)
        elif args.achievements:
            cli.run_achievements(metrics_path, once=args.once)
        else:
            # Default: live dashboard (or once if --once specified)
            if args.once:
                cli.run_once_dashboard(metrics_path)
            else:
                if not args.json:
                    console.print(f"[dim]Refresh rate: {args.refresh_rate}ms[/dim]")
                    console.print("[dim]Press Ctrl+C to exit[/dim]\n")
                    time.sleep(1)
                cli.run_live_dashboard(metrics_path, args.refresh_rate)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
