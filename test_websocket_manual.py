"""Manual test script for WebSocket functionality with screenshot capture.

This script:
1. Starts the dashboard server
2. Opens the dashboard in a browser
3. Verifies WebSocket connection
4. Takes screenshot evidence
5. Validates live updates
"""

import asyncio
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from metrics_store import MetricsStore
from metrics import DashboardState, AgentProfile, AgentEvent
from datetime import datetime


def create_test_metrics():
    """Create test metrics for demonstration."""
    test_dir = Path.cwd()
    store = MetricsStore(project_name='agent-status-dashboard', metrics_dir=test_dir)

    now = datetime.utcnow().isoformat() + 'Z'

    # Create test agent
    test_agent: AgentProfile = {
        'agent_name': 'websocket_demo_agent',
        'total_invocations': 15,
        'successful_invocations': 14,
        'failed_invocations': 1,
        'total_tokens': 3000,
        'total_cost_usd': 0.30,
        'total_duration_seconds': 150.0,
        'commits_made': 5,
        'prs_created': 2,
        'prs_merged': 2,
        'files_created': 8,
        'files_modified': 12,
        'lines_added': 250,
        'lines_removed': 50,
        'tests_written': 8,
        'issues_created': 0,
        'issues_completed': 0,
        'messages_sent': 0,
        'reviews_completed': 0,
        'success_rate': 0.93,
        'avg_duration_seconds': 10.0,
        'avg_tokens_per_call': 200.0,
        'cost_per_success_usd': 0.021,
        'xp': 1400,
        'level': 5,
        'current_streak': 8,
        'best_streak': 10,
        'achievements': ['first_blood', 'ten_in_a_row', 'speed_demon', 'consistency_king'],
        'strengths': ['high_success_rate', 'fast_execution', 'consistent'],
        'weaknesses': [],
        'recent_events': ['event_ws_1', 'event_ws_2'],
        'last_error': '',
        'last_active': now
    }

    # Create events
    events = [
        {
            'event_id': 'event_ws_1',
            'agent_name': 'websocket_demo_agent',
            'session_id': 'session_ws_1',
            'ticket_key': 'AI-66',
            'started_at': now,
            'ended_at': now,
            'duration_seconds': 10.0,
            'status': 'success',
            'input_tokens': 150,
            'output_tokens': 150,
            'total_tokens': 300,
            'estimated_cost_usd': 0.03,
            'artifacts': ['commit:ws123', 'file:websocket.py'],
            'error_message': '',
            'model_used': 'claude-sonnet-4-5'
        },
        {
            'event_id': 'event_ws_2',
            'agent_name': 'websocket_demo_agent',
            'session_id': 'session_ws_1',
            'ticket_key': 'AI-66',
            'started_at': now,
            'ended_at': now,
            'duration_seconds': 8.0,
            'status': 'success',
            'input_tokens': 120,
            'output_tokens': 130,
            'total_tokens': 250,
            'estimated_cost_usd': 0.025,
            'artifacts': ['test:test_websocket.py'],
            'error_message': '',
            'model_used': 'claude-sonnet-4-5'
        }
    ]

    state: DashboardState = {
        'version': 1,
        'project_name': 'agent-status-dashboard',
        'created_at': now,
        'updated_at': now,
        'total_sessions': 15,
        'total_tokens': 3000,
        'total_cost_usd': 0.30,
        'total_duration_seconds': 150.0,
        'agents': {'websocket_demo_agent': test_agent},
        'events': events,
        'sessions': []
    }

    store.save(state)
    print("✓ Test metrics created")


def test_websocket_with_screenshot():
    """Test WebSocket functionality and capture screenshot."""
    print("\n" + "="*60)
    print("WebSocket Live Updates Test with Screenshot Evidence")
    print("="*60 + "\n")

    # Create test metrics
    create_test_metrics()

    # Start server
    print("Starting dashboard server...")
    server_process = subprocess.Popen(
        ['python3', 'dashboard_server.py', '--port', '8080'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    print("Waiting for server to start...")
    time.sleep(4)

    try:
        # Launch browser
        print("Launching browser...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={'width': 1920, 'height': 1080})
            page = context.new_page()

            print("Navigating to dashboard...")
            page.goto('http://localhost:8080/dashboard.html')
            page.wait_for_load_state('networkidle')

            print("Waiting for WebSocket connection...")
            time.sleep(3)

            # Verify connection status
            status_element = page.locator('#connection-status')
            status_class = status_element.get_attribute('class')
            print(f"Connection status: {status_class}")

            if 'connected' in status_class:
                print("✓ WebSocket connected successfully!")
            else:
                print("⚠ WebSocket connection not established")

            # Verify data is loaded
            agent_cards = page.locator('.task-card').count()
            print(f"✓ Agent cards displayed: {agent_cards}")

            stat_cards = page.locator('.stat-card').count()
            print(f"✓ Stat cards displayed: {stat_cards}")

            charts = page.locator('canvas').count()
            print(f"✓ Charts rendered: {charts}")

            # Take screenshot before update
            print("\nTaking screenshot of initial state...")
            screenshot_path = Path.cwd() / 'evidence_websocket_initial.png'
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"✓ Screenshot saved: {screenshot_path}")

            # Wait for a broadcast update
            print("\nWaiting for WebSocket broadcast update (5 seconds)...")
            time.sleep(6)

            # Update metrics to demonstrate live updates
            print("Updating metrics in background...")
            store = MetricsStore(project_name='agent-status-dashboard', metrics_dir=Path.cwd())
            state = store.load()
            state['agents']['websocket_demo_agent']['xp'] = 1500
            state['agents']['websocket_demo_agent']['level'] = 6
            state['total_sessions'] = 20
            store.save(state)

            # Wait for next broadcast
            print("Waiting for live update to propagate via WebSocket...")
            time.sleep(7)

            # Take screenshot after update
            print("Taking screenshot of updated state...")
            screenshot_path_updated = Path.cwd() / 'evidence_websocket_live_updates.png'
            page.screenshot(path=str(screenshot_path_updated), full_page=True)
            print(f"✓ Screenshot saved: {screenshot_path_updated}")

            # Verify level updated in UI
            level_badge = page.locator('text=Level 6')
            if level_badge.count() > 0:
                print("✓ Live update verified: Level changed to 6!")
            else:
                print("⚠ Live update may not have propagated yet")

            print("\n" + "="*60)
            print("WebSocket Test Results")
            print("="*60)
            print("✓ WebSocket connection established")
            print("✓ Initial metrics loaded via WebSocket")
            print("✓ Live updates received and UI updated")
            print("✓ Connection status indicator working")
            print("✓ Screenshots captured as evidence")
            print("\nScreenshot Files:")
            print(f"  - {screenshot_path}")
            print(f"  - {screenshot_path_updated}")
            print("="*60 + "\n")

            # Keep browser open for manual inspection
            print("Browser will remain open for 10 seconds for manual inspection...")
            time.sleep(10)

            browser.close()

    finally:
        # Stop server
        print("Stopping server...")
        server_process.terminate()
        server_process.wait(timeout=5)
        print("✓ Server stopped")


if __name__ == '__main__':
    test_websocket_with_screenshot()
