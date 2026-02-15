# CLAUDE.md

This file provides context for AI assistants working on this codebase.

## Project Overview

This is a **multi-agent autonomous software engineering harness** built on the Claude Agent SDK (`claude-agent-sdk`). It uses an orchestrator pattern to delegate work to specialized sub-agents (Linear, Coding, GitHub, Slack) that independently manage projects, write code, coordinate version control, and communicate progress.

**Language:** Python 3 (async)
**Framework:** Claude Agent SDK + Arcade MCP Gateway
**License:** MIT

## Repository Structure

```
├── agent.py                    # Core agent session loop logic
├── client.py                   # Claude SDK client configuration
├── security.py                 # Bash command security hooks (allowlist-based)
├── progress.py                 # Progress tracking via .linear_project.json
├── prompts.py                  # Prompt template loading utilities
├── agents/
│   ├── __init__.py             # Exports agent definitions and orchestrator
│   ├── definitions.py          # 13 agent definitions with per-agent model config
│   └── orchestrator.py         # Orchestrator session runner
├── bridges/                    # External AI provider bridges
│   ├── openai_bridge.py        # ChatGPT integration (Codex OAuth + Session Token)
│   ├── gemini_bridge.py        # Gemini integration (CLI OAuth + API key + Vertex AI)
│   ├── groq_bridge.py          # Groq integration (LPU inference)
│   ├── kimi_bridge.py          # KIMI/Moonshot integration (OpenAI-compatible)
│   ├── windsurf_bridge.py      # Windsurf integration (CLI/Docker)
│   └── *_INTEGRATION.md        # Per-provider setup docs
├── daemon/                     # Scalable ticket processing daemon
│   ├── control_plane.py        # HTTP control plane (port 9100)
│   ├── worker_pool.py          # Typed worker pool manager
│   ├── ticket_router.py        # Complexity-based ticket routing
│   └── worktree.py             # Git worktree isolation
├── scripts/
│   ├── autonomous_agent_demo.py # Main entry point / CLI
│   ├── daemon.py               # Simple ticket polling daemon
│   ├── daemon_v2.py            # Scalable daemon with worker pools
│   ├── arcade_config.py        # Arcade MCP gateway config and tool definitions
│   ├── authorize_arcade.py     # OAuth authorization flow for Arcade services
│   ├── chatgpt_cli.py          # Standalone ChatGPT CLI
│   ├── gemini_cli.py           # Standalone Gemini CLI
│   ├── groq_cli.py             # Standalone Groq CLI
│   ├── kimi_cli.py             # Standalone KIMI CLI
│   ├── windsurf_cli.py         # Standalone Windsurf CLI
│   ├── test_security.py        # Security hook test suite
│   └── ...                     # Other utilities
├── prompts/
│   ├── orchestrator_prompt.md  # Orchestrator system prompt
│   ├── *_agent_prompt.md       # Per-agent system prompts (13 total)
│   ├── initializer_task.md     # First-run initialization task template
│   └── continuation_task.md    # Continuation session task template
├── specs/                      # Application specifications
│   ├── app_spec.txt            # Default application specification
│   └── *.txt                   # Additional spec templates
├── pyproject.toml              # Ruff linter/formatter config
├── requirements.txt            # Pinned Python dependencies
├── .env.example                # Environment variable template
└── .gitignore                  # Git ignore rules
```

## Architecture

The system uses an **orchestrator pattern** with 13 specialized agents:

```
ORCHESTRATOR (haiku by default)
├── Workflow Agents
│   ├── LINEAR (haiku)          — Issue/project management in Linear
│   ├── CODING (sonnet)         — Code implementation + Playwright browser testing
│   ├── CODING_FAST (haiku)     — Simple changes (copy, CSS, config, tests)
│   ├── GITHUB (haiku)          — Git operations, branches, PRs
│   ├── PR_REVIEWER (sonnet)    — Automated code review and merge
│   ├── PR_REVIEWER_FAST (haiku) — Quick PR review for low-risk changes
│   ├── OPS (haiku)             — Batch operations (Linear + Slack + GitHub)
│   └── SLACK (haiku)           — Progress notifications
└── AI Provider Agents
    ├── CHATGPT (haiku)         — OpenAI GPT-4o, o1, o3-mini via bridge
    ├── GEMINI (haiku)          — Google Gemini 2.5 Flash/Pro via bridge
    ├── GROQ (haiku)            — Llama, Mixtral via Groq LPU bridge
    ├── KIMI (haiku)            — Moonshot AI ultra-long context via bridge
    └── WINDSURF (haiku)        — Codeium IDE headless/Docker via bridge
```

Key architectural decisions:
- **Each session creates a fresh SDK client** to prevent context window exhaustion in long-running loops
- **Agents don't share memory** — the orchestrator explicitly passes context between them
- **State is persisted via `.linear_project.json`** in the project directory
- **Session types:** "initializer" (first run, creates Linear issues) vs "continuation" (subsequent work)
- **Completion signal:** orchestrator outputs `PROJECT_COMPLETE:` when all features are done

## Running the Project

### Prerequisites
- Python 3.10+
- `uv` (recommended) or `pip` for package management
- Claude CLI authentication (`claude login`)
- Arcade API key and gateway (see `.env.example`)
- Node.js/npm (for Playwright MCP and generated projects)

### Quick Start

```bash
# Install dependencies
uv pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your ARCADE_API_KEY and ARCADE_GATEWAY_SLUG

# Authorize Arcade OAuth (one-time)
uv run python scripts/authorize_arcade.py

# Run the autonomous agent
uv run python scripts/autonomous_agent_demo.py --project-dir my-app

# With options
uv run python scripts/autonomous_agent_demo.py --project-dir my-app --model opus --max-iterations 5
```

### Running Tests

```bash
uv run python scripts/test_security.py
```

Tests are in `scripts/test_security.py` and cover:
- Command extraction logic (`extract_commands`)
- chmod validation (only `+x` variants allowed)
- init.sh validation (only `./init.sh` allowed)
- Dangerous command blocking (system directories, disallowed commands)
- Safe command allowlisting

There is no test framework — tests use a custom `test_hook()` harness that runs assertions and prints PASS/FAIL.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ARCADE_API_KEY` | Yes | Arcade API key (starts with `arc_`) |
| `ARCADE_GATEWAY_SLUG` | Yes | Custom MCP gateway slug |
| `ARCADE_USER_ID` | No | Email for Arcade tracking (default: `agent@local`) |
| `GENERATIONS_BASE_PATH` | No | Where to create projects (default: `./generations`) |
| `GITHUB_REPO` | No | `owner/repo` for GitHub integration |
| `SLACK_CHANNEL` | No | Slack channel for notifications |
| `ORCHESTRATOR_MODEL` | No | haiku/sonnet/opus (default: haiku) |
| `LINEAR_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `CODING_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `GITHUB_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `SLACK_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `PR_REVIEWER_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `OPS_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `CHATGPT_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `GEMINI_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `GROQ_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `KIMI_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `WINDSURF_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |

## Security Model

The system uses defense-in-depth with three layers:

1. **Sandbox** — OS-level bash isolation via `bwrap`/container (configured in `.claude_settings.json`)
2. **Permissions** — File operations restricted to the project directory only
3. **Security hooks** — Pre-execution bash command validation via allowlist in `security.py`

### Bash Command Allowlist

Only commands in `ALLOWED_COMMANDS` (in `security.py:29-73`) are permitted. Key restrictions:
- **`pkill`** — Only dev processes: `node`, `npm`, `npx`, `vite`, `next`
- **`chmod`** — Only `+x` mode (making files executable)
- **`rm`** — Blocks system directories (`/`, `/etc`, `/usr`, `/home`, etc.)
- **`init.sh`** — Only `./init.sh` execution allowed
- Commands not in the allowlist are blocked entirely (fail-safe)

## Code Conventions

- **Type hints throughout** — all functions use Python type annotations including `NamedTuple`, `TypedDict`, `Literal`, `TypeGuard`
- **Async/await** — core agent logic is fully async using `asyncio`
- **Docstrings** — all public functions have docstrings with Args/Returns/Raises sections
- **Constants** — module-level typed constants with `Final` where appropriate
- **Error handling** — specific exception types caught with actionable error messages
- **Ruff** — linter and formatter configured via `pyproject.toml` (line-length=100, target py311)
- **No CI/CD** — no `.github/workflows` directory

## Key Patterns

### Session Loop (agent.py)
```python
# Each iteration creates a fresh client to avoid context exhaustion
while True:
    client = create_client(project_dir, model)
    async with client:
        result = await run_agent_session(client, prompt, project_dir)
    # Handle result.status: "continue" | "error" | "complete"
```

### Agent Definitions (agents/definitions.py)
Agent models are configurable via `{AGENT_NAME}_AGENT_MODEL` env vars. Definitions are created at import time. Each agent gets a subset of tools matching its domain.

### MCP Integration (client.py, arcade_config.py)
Two MCP servers are configured:
- **Playwright** (`@playwright/mcp@latest`) — browser automation for UI testing
- **Arcade** (HTTP gateway) — unified auth for Linear (39 tools), GitHub (46 tools), Slack (8 tools)

### Bridge Modules (bridges/)
External AI providers are integrated via bridge modules in `bridges/`. Each bridge wraps a provider's API (using their SDK or OpenAI-compatible endpoints) and is invoked by the corresponding agent via Bash. CLIs are in `scripts/*_cli.py`.

### Generated Project Structure
Each run creates an isolated project in `generations/<project-name>/` with:
- Its own `.git` repository
- `.linear_project.json` state marker
- `.claude_settings.json` security settings
- `app_spec.txt` application specification
- `init.sh` dev server startup script

## Common Tasks for Contributors

### Adding a new allowed bash command
Add to `ALLOWED_COMMANDS` in `security.py`. If the command needs extra validation, add it to `COMMANDS_NEEDING_EXTRA_VALIDATION` and implement a `validate_<cmd>_command()` function following the existing pattern. Add test cases to `scripts/test_security.py`.

### Adding a new specialized agent
1. Create a prompt file in `prompts/<name>_agent_prompt.md`
2. Add an `AgentDefinition` in `agents/definitions.py`
3. Define the tool subset for the agent in `scripts/arcade_config.py` (if using Arcade tools)
4. Add a `{NAME}_AGENT_MODEL` env var in the `_get_model()` function

### Modifying the app specification
Edit `specs/app_spec.txt` or create a new spec in `specs/`. The default spec is copied into the project directory on first run.

## Agent Status Dashboard

The Agent Status Dashboard is a comprehensive metrics instrumentation system that tracks agent sessions, delegations, token usage, costs, and performance characteristics. It provides visibility into agent behavior across autonomous engineering tasks.

### Overview

The dashboard tracks:
- **Session metrics**: Each autonomous engineering session (initializer or continuation) with start/end times, agents involved, and tickets addressed
- **Agent delegations**: Individual invocations to agents (coding, github, linear, slack, etc.) with token counts and costs
- **Token usage**: Per-event and per-agent aggregates, supporting cost tracking at current Claude pricing
- **Artifacts**: What each agent produced (commits, PRs, files, issues, etc.)
- **Gamification**: XP, levels, achievement badges, and success streaks for agents
- **Performance analysis**: Strengths/weaknesses detection and rolling window statistics

### Data Model

The dashboard uses TypedDict types defined in `metrics.py`:

**AgentEvent** - Single agent invocation record:
```python
{
    "event_id": str,                      # UUID for this event
    "agent_name": str,                    # "coding", "github", "linear", "slack", etc.
    "session_id": str,                    # Parent session ID
    "ticket_key": str,                    # Linear ticket key (e.g., "AI-50")
    "started_at": str,                    # ISO 8601 timestamp
    "ended_at": str,                      # ISO 8601 timestamp
    "duration_seconds": float,            # Execution time
    "status": str,                        # "success", "error", "timeout", "blocked"
    "input_tokens": int,                  # Tokens in prompt
    "output_tokens": int,                 # Tokens generated
    "total_tokens": int,                  # Sum of input + output
    "estimated_cost_usd": float,          # Cost based on model pricing
    "artifacts": list[str],               # ["commit:abc123", "pr:#42", "file:src/foo.py", "issue:AI-12"]
    "error_message": str,                 # Details if status is "error"
    "model_used": str,                    # "claude-haiku-4-5", "claude-sonnet-4-5", etc.
}
```

**AgentProfile** - Cumulative statistics for one agent:
```python
{
    "agent_name": str,
    # Counters
    "total_invocations": int,
    "successful_invocations": int,
    "failed_invocations": int,
    "total_tokens": int,
    "total_cost_usd": float,
    "total_duration_seconds": float,
    # Artifacts
    "commits_made": int,
    "prs_created": int,
    "prs_merged": int,
    "files_created": int,
    "files_modified": int,
    "lines_added": int,
    "lines_removed": int,
    "tests_written": int,
    "issues_created": int,
    "issues_completed": int,
    "messages_sent": int,
    "reviews_completed": int,
    # Derived metrics
    "success_rate": float,                # 0.0 to 1.0
    "avg_duration_seconds": float,
    "avg_tokens_per_call": float,
    "cost_per_success_usd": float,
    # Gamification
    "xp": int,                            # Experience points
    "level": int,                         # Current level
    "current_streak": int,                # Consecutive successes
    "best_streak": int,                   # Peak streak
    "achievements": list[str],            # ["first_blood", "century_club", ...]
    # Analysis
    "strengths": list[str],               # ["fast_execution", "high_success_rate", "low_cost"]
    "weaknesses": list[str],              # ["high_error_rate", "slow", "expensive"]
    "recent_events": list[str],           # Last 20 event IDs
    "last_error": str,
    "last_active": str,                   # ISO 8601 timestamp
}
```

**SessionSummary** - Rollup metrics for entire session:
```python
{
    "session_id": str,
    "session_number": int,                # Sequential number within project
    "session_type": str,                  # "initializer" or "continuation"
    "started_at": str,
    "ended_at": str,
    "status": str,                        # "continue", "error", "complete"
    "agents_invoked": list[str],          # Agents used in session
    "total_tokens": int,
    "total_cost_usd": float,
    "tickets_worked": list[str],          # Tickets addressed
}
```

**DashboardState** - Root structure in `.agent_metrics.json`:
```python
{
    "version": int,                       # Schema version (currently 1)
    "project_name": str,
    "created_at": str,
    "updated_at": str,
    "total_sessions": int,
    "total_tokens": int,
    "total_cost_usd": float,
    "total_duration_seconds": float,
    "agents": dict[str, AgentProfile],   # Per-agent profiles
    "events": list[AgentEvent],          # Capped at 500 (FIFO eviction)
    "sessions": list[SessionSummary],    # Capped at 50 (FIFO eviction)
}
```

### Core Components

**AgentMetricsCollector** (`agent_metrics_collector.py`):
Main class for tracking agent delegations. Manages session lifecycle and provides the `track_agent()` context manager.

**MetricsStore** (`metrics_store.py`):
JSON persistence layer for `.agent_metrics.json`. Handles atomic writes, corruption recovery, cross-process locking, and FIFO eviction.

**strengths_weaknesses.py**:
Auto-detection of agent performance characteristics using rolling window statistics. Identifies patterns like "fast_execution", "high_success_rate", "expensive", etc.

**achievements.py**:
Gamification system with 12 achievement types (first_blood, century_club, perfect_day, speed_demon, comeback_kid, big_spender, penny_pincher, marathon, polyglot, night_owl, streak_10, streak_25).

### Usage Examples

**Basic Session Tracking**:
```python
from agent_metrics_collector import AgentMetricsCollector

# Initialize collector
collector = AgentMetricsCollector(project_name="my-project")

# Start a session
session_id = collector.start_session(session_type="initializer")

# Track an agent delegation
with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
    # Do work...
    tracker.add_tokens(input_tokens=2000, output_tokens=3000)
    tracker.add_artifact("file:created:src/agent.py")
    tracker.add_artifact("file:created:test_agent.py")

# Track another agent in the same session
with collector.track_agent("github", "AI-50", "claude-haiku-4-5", session_id) as tracker:
    tracker.add_tokens(input_tokens=500, output_tokens=1200)
    tracker.add_artifact("pr:created:#42")

# End the session
collector.end_session(session_id, status="complete")
```

**Accessing Metrics**:
```python
# Get current dashboard state
state = collector.get_state()

# Check global metrics
print(f"Total tokens: {state['total_tokens']}")
print(f"Total cost: ${state['total_cost_usd']:.2f}")
print(f"Sessions: {state['total_sessions']}")

# Check specific agent profile
coding_profile = state["agents"]["coding"]
print(f"Coding agent success rate: {coding_profile['success_rate']*100:.1f}%")
print(f"Coding agent XP: {coding_profile['xp']}")
print(f"Achievements: {', '.join(coding_profile['achievements'])}")
print(f"Strengths: {', '.join(coding_profile['strengths'])}")

# Browse recent events
for event in state["events"][-10:]:  # Last 10 events
    print(f"{event['agent_name']}: {event['status']} ({event['total_tokens']} tokens, ${event['estimated_cost_usd']:.4f})")

# Check session history
for session in state["sessions"]:
    print(f"Session {session['session_number']}: {session['status']} - {', '.join(session['agents_invoked'])}")
```

**Error Handling**:
```python
with collector.track_agent("coding", "AI-51", "claude-sonnet-4-5", session_id) as tracker:
    tracker.add_tokens(input_tokens=1000, output_tokens=500)
    # If an exception occurs, tracker will:
    # 1. Record the event with status="error"
    # 2. Preserve the error message
    # 3. Reset the agent's success streak
    # The exception still propagates to the caller
    try:
        dangerous_operation()
    except Exception as e:
        tracker.set_error(str(e))
        # Event will be recorded with this error message
        raise
```

### Integration with agent.py

The session loop in `agent.py` has been instrumented with metrics collection. When `run_agent_session()` is called:

1. A collector is initialized for the project
2. Session lifecycle is tracked (start -> agent invocations -> end)
3. Agent delegations to sub-agents are captured
4. Token counts from SDK response metadata are recorded
5. Orchestrator state is persisted to `.agent_metrics.json`

The metrics file is created automatically in the project directory on first session and updated after each event.

### Accessing the Metrics File

The `.agent_metrics.json` file is stored in the project directory and contains the complete dashboard state:

```bash
# View metrics summary
python -c "
from metrics_store import MetricsStore
from pathlib import Path

store = MetricsStore('my-project', metrics_dir=Path('my-project'))
state = store.load()

print(f'Project: {state[\"project_name\"]}')
print(f'Total sessions: {state[\"total_sessions\"]}')
print(f'Total cost: ${state[\"total_cost_usd\"]:.2f}')
print(f'Agents tracked: {list(state[\"agents\"].keys())}')
"

# Get storage stats
python -c "
from metrics_store import MetricsStore
from pathlib import Path

store = MetricsStore('my-project', metrics_dir=Path('my-project'))
stats = store.get_stats()
print(f'Metrics file size: {stats[\"metrics_file_size_bytes\"]} bytes')
print(f'Events logged: {stats[\"event_count\"]}')
print(f'Sessions: {stats[\"session_count\"]}')
print(f'Agents: {stats[\"agent_count\"]}')
"
```

### Cost Tracking

Token counts are converted to costs using the following pricing (per 1000 tokens):

- **claude-opus-4-6**: input=$0.015, output=$0.075
- **claude-sonnet-4-5**: input=$0.003, output=$0.015
- **claude-haiku-4-5**: input=$0.0008, output=$0.004
- Other models default to Sonnet pricing

Cost is calculated per-event and aggregated at the agent and session level:

```python
# Calculate cost for an event
from agent_metrics_collector import _calculate_cost

cost = _calculate_cost("claude-sonnet-4-5", input_tokens=1000, output_tokens=2000)
# cost = (1000/1000)*0.003 + (2000/1000)*0.015 = 0.033 USD
```

### Gamification System

Agents earn XP and achievements:

- **XP**: Awarded per successful invocation (scaled by cost and tokens)
- **Levels**: Derived from XP thresholds (level 1 at 0 XP, increases every 1000 XP)
- **Achievements**: 12 types including:
  - first_blood: First successful invocation
  - century_club: 100 successful invocations
  - perfect_day: 10+ invocations in one session with no errors
  - speed_demon: 5 consecutive completions under 30 seconds
  - comeback_kid: Success after 3+ consecutive errors
  - big_spender: Single invocation over $1.00
  - penny_pincher: 50+ successes at < $0.01 each
  - marathon: 100+ invocations in single project
  - polyglot: Used across 5+ different ticket types
  - night_owl: Invocation between 00:00-05:00 local time
  - streak_10: 10 consecutive successes
  - streak_25: 25 consecutive successes

### Testing

Test files are provided:
- `test_agent_session_metrics.py`: Unit tests for metrics collection, cost calculation, profile updates
- `test_integration_agent_session.py`: Integration tests showing full session flow
- `example_agent_session_metrics.py`: Runnable examples demonstrating all features

Run tests:
```bash
python -m pytest test_agent_session_metrics.py -v
python -m pytest test_integration_agent_session.py -v
python example_agent_session_metrics.py
```
