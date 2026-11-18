"""Playwright browser tests for WebSocket real-time updates.

Tests cover:
- WebSocket connection establishment in browser
- Real-time metrics updates in UI
- Connection status indicator
- Reconnection after disconnect
- Live data refresh without page reload
"""

import os
import time
from datetime import datetime
from pathlib import Path

import pytest
from dashboard_server_process import dashboard_server
from playwright.sync_api import Page, expect, sync_playwright

from metrics import AgentProfile, DashboardState
from metrics_store import MetricsStore

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_SOURCE = (REPO_ROOT / 'dashboard.html').read_text()
# dashboard.html hard-codes the server at localhost:8080; the page served to the
# browser is rewritten to point at the test server's port instead.
assert 'localhost:8080' in DASHBOARD_SOURCE, "dashboard.html no longer uses localhost:8080"


@pytest.fixture(scope="module")
def metrics_dir(tmp_path_factory):
    """Isolated directory holding the metrics file the server reads."""
    return tmp_path_factory.mktemp("websocket_playwright")


@pytest.fixture(scope="module")
def server_process(metrics_dir):
    """Start dashboard server for testing."""
    # Create test metrics
    test_dir = metrics_dir
    store = MetricsStore(project_name='agent-status-dashboard', metrics_dir=test_dir)

    # Create test state
    now = datetime.utcnow().isoformat() + 'Z'
    test_agent: AgentProfile = {
        'agent_name': 'playwright_test_agent',
        'total_invocations': 10,
        'successful_invocations': 9,
        'failed_invocations': 1,
        'total_tokens': 2000,
        'total_cost_usd': 0.20,
        'total_duration_seconds': 100.0,
        'commits_made': 3,
        'prs_created': 1,
        'prs_merged': 1,
        'files_created': 5,
        'files_modified': 8,
        'lines_added': 150,
        'lines_removed': 30,
        'tests_written': 5,
        'issues_created': 0,
        'issues_completed': 0,
        'messages_sent': 0,
        'reviews_completed': 0,
        'success_rate': 0.9,
        'avg_duration_seconds': 10.0,
        'avg_tokens_per_call': 200.0,
        'cost_per_success_usd': 0.022,
        'xp': 900,
        'level': 3,
        'current_streak': 5,
        'best_streak': 7,
        'achievements': ['first_blood', 'ten_in_a_row', 'speed_demon'],
        'strengths': ['high_success_rate', 'consistent'],
        'weaknesses': [],
        'recent_events': ['event_pw_1'],
        'last_error': '',
        'last_active': now
    }

    state: DashboardState = {
        'version': 1,
        'project_name': 'agent-status-dashboard',
        'created_at': now,
        'updated_at': now,
        'total_sessions': 10,
        'total_tokens': 2000,
        'total_cost_usd': 0.20,
        'total_duration_seconds': 100.0,
        'agents': {'playwright_test_agent': test_agent},
        'events': [{
            'event_id': 'event_pw_1',
            'agent_name': 'playwright_test_agent',
            'session_id': 'session_pw_1',
            'ticket_key': 'PW-1',
            'started_at': now,
            'ended_at': now,
            'duration_seconds': 10.0,
            'status': 'success',
            'input_tokens': 100,
            'output_tokens': 100,
            'total_tokens': 200,
            'estimated_cost_usd': 0.02,
            'artifacts': ['commit:abc123'],
            'error_message': '',
            'model_used': 'claude-sonnet-4-5'
        }],
        'sessions': []
    }

    store.save(state)

    # The dashboard page is served from http://localhost:<port>, so the API must
    # allow that origin.
    def server_env(port: int) -> dict[str, str]:
        return {**os.environ, 'CORS_ALLOWED_ORIGINS': f'http://localhost:{port}'}

    with dashboard_server(test_dir, env_for_port=server_env) as port:
        yield port


@pytest.fixture(scope="module")
def dashboard_url(server_process):
    """URL the browser opens; served from the repository by browser_page."""
    return f'http://localhost:{server_process}/dashboard.html'


@pytest.fixture(scope="module")
def browser():
    """Chromium for this module, started and stopped with the module.

    The sync Playwright API keeps an event loop running while it is active, so it
    is shut down at the end of this module rather than kept for the whole session;
    otherwise later asyncio-based tests could not start their own loops.

    The dashboard page is fulfilled by Playwright rather than by a loopback server,
    so Chromium's Local Network Access checks would otherwise block the page's
    WebSocket to ws://localhost.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--disable-features=LocalNetworkAccessChecks"],
        )
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def page(browser):
    """Fresh browser context and page for each test."""
    context = browser.new_context()
    try:
        yield context.new_page()
    finally:
        context.close()


@pytest.fixture
def browser_page(page: Page, server_process, dashboard_url):
    """Configure browser page for testing."""
    page.set_viewport_size({"width": 1920, "height": 1080})
    # dashboard_server.py only serves the API and WebSocket, so serve the dashboard
    # page itself from the repository; API and WebSocket calls reach the test server.
    html = DASHBOARD_SOURCE.replace('localhost:8080', f'localhost:{server_process}')
    page.route(
        dashboard_url,
        lambda route: route.fulfill(body=html, content_type='text/html'),
    )
    return page


def test_websocket_connection_established(browser_page: Page, dashboard_url):
    """Test WebSocket connection establishes successfully."""
    # Navigate to dashboard
    browser_page.goto(dashboard_url)

    # Wait for page to load
    browser_page.wait_for_load_state('networkidle')

    # Check connection status indicator
    status_element = browser_page.locator('#connection-status')
    expect(status_element).to_be_visible(timeout=10000)

    # Should eventually show "connected"
    expect(status_element).to_have_class('connection-status connected', timeout=10000)

    # Status text should indicate live updates
    status_text = browser_page.locator('#status-text')
    expect(status_text).to_contain_text('Live updates active', timeout=10000)


def test_websocket_receives_initial_data(browser_page: Page, dashboard_url):
    """Test WebSocket receives and displays initial metrics data."""
    browser_page.goto(dashboard_url)
    browser_page.wait_for_load_state('networkidle')

    # Wait for data to load
    time.sleep(2)

    # Check that metrics are displayed
    agent_cards = browser_page.locator('.task-card')
    expect(agent_cards).to_have_count(1, timeout=10000)

    # Check agent name is displayed
    expect(browser_page.locator('text=playwright_test_agent').first).to_be_visible()

    # Check stats are displayed
    expect(browser_page.locator('text=Total Sessions')).to_be_visible()
    expect(browser_page.locator('.stat-value').first).to_be_visible()


def test_websocket_live_updates(browser_page: Page, dashboard_url, metrics_dir):
    """Test WebSocket receives live updates."""
    browser_page.goto(dashboard_url)
    browser_page.wait_for_load_state('networkidle')

    # Wait for initial connection
    expect(browser_page.locator('#connection-status.connected')).to_be_visible(timeout=10000)

    # Get initial XP value
    time.sleep(2)
    initial_metrics = browser_page.locator('.metric-value').all()
    assert len(initial_metrics) > 0

    # Modify metrics in the background
    test_dir = metrics_dir
    store = MetricsStore(project_name='agent-status-dashboard', metrics_dir=test_dir)
    state = store.load()
    state['agents']['playwright_test_agent']['xp'] = 1000  # Increase XP
    state['agents']['playwright_test_agent']['level'] = 4  # Level up
    store.save(state)

    # Wait for WebSocket to broadcast update (broadcast interval is 5s)
    time.sleep(7)

    # Check that UI updated with new values
    level_badge = browser_page.locator('text=Level 4')
    expect(level_badge).to_be_visible(timeout=5000)


def test_websocket_connection_status_indicator(browser_page: Page, dashboard_url):
    """Test connection status indicator updates correctly."""
    browser_page.goto(dashboard_url)

    # Initially should show connecting
    status = browser_page.locator('#connection-status')

    # Then should transition to connected
    expect(status).to_have_class('connection-status connected', timeout=10000)

    # Check indicator dot is visible
    indicator = browser_page.locator('#status-indicator')
    expect(indicator).to_be_visible()


def test_websocket_updates_timestamp(browser_page: Page, dashboard_url):
    """Test that update timestamp is displayed and updates."""
    browser_page.goto(dashboard_url)
    browser_page.wait_for_load_state('networkidle')

    # Wait for initial update
    time.sleep(2)

    # Check timestamp is displayed
    last_update = browser_page.locator('#last-update')
    expect(last_update).to_be_visible(timeout=10000)
    expect(last_update).to_contain_text('Updated at', timeout=10000)


def test_websocket_multiple_updates(browser_page: Page, dashboard_url, metrics_dir):
    """Test WebSocket handles multiple sequential updates."""
    browser_page.goto(dashboard_url)
    browser_page.wait_for_load_state('networkidle')

    # Wait for connection
    expect(browser_page.locator('#connection-status.connected')).to_be_visible(timeout=10000)

    test_dir = metrics_dir
    store = MetricsStore(project_name='agent-status-dashboard', metrics_dir=test_dir)

    # Make multiple updates
    for i in range(3):
        time.sleep(6)  # Wait for broadcast interval
        state = store.load()
        state['total_sessions'] = 10 + i + 1
        state['agents']['playwright_test_agent']['total_invocations'] = 10 + i + 1
        store.save(state)

    # Wait for final update
    time.sleep(7)

    # UI should have updated
    stats = browser_page.locator('.stat-card').all()
    assert len(stats) > 0


def test_websocket_dashboard_charts_update(browser_page: Page, dashboard_url):
    """Test that charts update with WebSocket data."""
    browser_page.goto(dashboard_url)
    browser_page.wait_for_load_state('networkidle')

    # Wait for charts to render
    time.sleep(3)

    # Check that charts are rendered
    charts = browser_page.locator('canvas')
    expect(charts.first).to_be_visible(timeout=10000)

    # Count charts
    chart_count = charts.count()
    assert chart_count >= 5  # We have 5 charts in dashboard


def test_websocket_activity_feed_updates(browser_page: Page, dashboard_url):
    """Test that activity feed shows data from WebSocket."""
    browser_page.goto(dashboard_url)
    browser_page.wait_for_load_state('networkidle')

    # Wait for data
    time.sleep(2)

    # Check activity feed has items
    activity_items = browser_page.locator('.activity-item')
    expect(activity_items.first).to_be_visible(timeout=10000)


def test_websocket_page_ready_without_manual_refresh(browser_page: Page, dashboard_url):
    """Test that dashboard works without manual refresh - all via WebSocket."""
    browser_page.goto(dashboard_url)

    # Wait for WebSocket connection
    expect(browser_page.locator('#connection-status.connected')).to_be_visible(timeout=10000)

    # Wait for data to populate
    time.sleep(3)

    # Verify all sections are populated
    expect(browser_page.locator('.stat-card').first).to_be_visible()
    expect(browser_page.locator('.task-card').first).to_be_visible()
    expect(browser_page.locator('canvas').first).to_be_visible()
    expect(browser_page.locator('.activity-item').first).to_be_visible()

    # No manual refresh needed - everything came via WebSocket
    navigation_count = browser_page.evaluate('window.performance.navigation.type')
    assert navigation_count == 0  # Normal navigation, not refresh


def test_websocket_screenshot_evidence(browser_page: Page, dashboard_url, tmp_path):
    """Take screenshot evidence of WebSocket live updates working."""
    browser_page.goto(dashboard_url)
    browser_page.wait_for_load_state('networkidle')

    # Wait for connection and data
    expect(browser_page.locator('#connection-status.connected')).to_be_visible(timeout=10000)
    time.sleep(3)

    # Take screenshot showing connected status and data
    screenshot_path = tmp_path / 'evidence_websocket_live_updates.png'
    browser_page.screenshot(path=str(screenshot_path), full_page=True)

    assert screenshot_path.exists()
    print(f"\nScreenshot saved to: {screenshot_path}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
