#!/usr/bin/env python3
"""Test metrics collection system."""
from metrics_store import MetricsStore

m = MetricsStore(project_name="test-project")
state = m.load()
agents = state.get("agents", {})
print(f"Metrics loaded: {len(agents)} agents")
print(f"MetricsStore operational - loaded {state.get('total_sessions', 0)} sessions")
print("SUCCESS")
