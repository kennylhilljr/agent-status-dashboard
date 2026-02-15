"""Playwright browser tests for dashboard_server.py.

Tests verify that endpoints are accessible via browser and return correct JSON.
Uses Playwright to simulate real browser requests and validate responses.
"""

import json
import pytest
import asyncio
import subprocess
import time
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page
from metrics_store import MetricsStore
from metrics import DashboardState, AgentProfile, AgentEvent


# Server configuration for tests
TEST_PORT = 8889
TEST_HOST = 'localhost'
BASE_URL = f'http://{TEST_HOST}:{TEST_PORT}'


@pytest.fixture(scope='module')
def test_metrics_dir():
    """Create temporary directory for test metrics."""
    test_dir = Path('/tmp/test_dashboard_playwright')
    test_dir.mkdir(exist_ok=True)

    # Create test metrics data
    _create_test_metrics(test_dir)

    yield test_dir

    # Cleanup
    import shutil
    if test_dir.exists():
        shutil.rmtree(test_dir)


def _create_test_metrics(test_dir: Path):
    """Create test metrics data."""
    now = datetime.utcnow().isoformat() + 'Z'

    # Create test agent profiles
    coding_agent: AgentProfile = {
        'agent_name': 'coding_agent',
        'total_invocations': 25,
        'successful_invocations': 22,
        'failed_invocations': 3,
        'total_tokens': 15000,
        'total_cost_usd': 1.50,
        'total_duration_seconds': 300.0,
        'commits_made': 10,
        'prs_created': 3,
        'prs_merged': 2,
        'files_created': 15,
        'files_modified': 30,
        'lines_added': 500,
        'lines_removed': 100,
        'tests_written': 20,
        'issues_created': 0,
        'issues_completed': 0,
        'messages_sent': 0,
        'reviews_completed': 0,
        'success_rate': 0.88,
        'avg_duration_seconds': 12.0,
        'avg_tokens_per_call': 600.0,
        'cost_per_success_usd': 0.068,
        'xp': 2200,
        'level': 3,
        'current_streak': 8,
        'best_streak': 12,
        'achievements': ['first_blood', 'ten_in_a_row', 'century_club'],
        'strengths': ['high_success_rate', 'fast_execution', 'thorough_testing'],
        'weaknesses': [],
        'recent_events': ['evt_1', 'evt_2', 'evt_3'],
        'last_error': '',
        'last_active': now
    }

    github_agent: AgentProfile = {
        'agent_name': 'github_agent',
        'total_invocations': 15,
        'successful_invocations': 14,
        'failed_invocations': 1,
        'total_tokens': 8000,
        'total_cost_usd': 0.80,
        'total_duration_seconds': 150.0,
        'commits_made': 5,
        'prs_created': 5,
        'prs_merged': 4,
        'files_created': 0,
        'files_modified': 0,
        'lines_added': 0,
        'lines_removed': 0,
        'tests_written': 0,
        'issues_created': 2,
        'issues_completed': 1,
        'messages_sent': 0,
        'reviews_completed': 3,
        'success_rate': 0.93,
        'avg_duration_seconds': 10.0,
        'avg_tokens_per_call': 533.0,
        'cost_per_success_usd': 0.057,
        'xp': 1400,
        'level': 2,
        'current_streak': 5,
        'best_streak': 8,
        'achievements': ['first_blood', 'pr_master'],
        'strengths': ['high_success_rate', 'efficient'],
        'weaknesses': [],
        'recent_events': ['evt_4', 'evt_5'],
        'last_error': 'API rate limit',
        'last_active': now
    }

    # Create test events
    events = [
        {
            'event_id': f'evt_{i}',
            'agent_name': 'coding_agent' if i % 2 == 0 else 'github_agent',
            'session_id': 'session_1',
            'ticket_key': f'TEST-{i}',
            'started_at': now,
            'ended_at': now,
            'duration_seconds': 10.0 + i,
            'status': 'success' if i % 5 != 4 else 'error',
            'input_tokens': 100 + i * 10,
            'output_tokens': 200 + i * 20,
            'total_tokens': 300 + i * 30,
            'estimated_cost_usd': 0.03 + i * 0.01,
            'artifacts': [f'commit:abc{i}', f'file:test{i}.py'],
            'error_message': 'Test error' if i % 5 == 4 else '',
            'model_used': 'claude-sonnet-4-5'
        }
        for i in range(1, 11)
    ]

    # Create test state
    state: DashboardState = {
        'version': 1,
        'project_name': 'test-playwright-project',
        'created_at': now,
        'updated_at': now,
        'total_sessions': 10,
        'total_tokens': 23000,
        'total_cost_usd': 2.30,
        'total_duration_seconds': 450.0,
        'agents': {
            'coding_agent': coding_agent,
            'github_agent': github_agent,
        },
        'events': events,
        'sessions': []
    }

    # Save test state
    store = MetricsStore(project_name='test-playwright-project', metrics_dir=test_dir)
    store.save(state)


@pytest.fixture(scope='module')
async def server_process(test_metrics_dir):
    """Start dashboard server as subprocess for testing."""
    # Start server process
    cmd = [
        'python',
        str(Path(__file__).parent.parent / 'dashboard_server.py'),
        '--port', str(TEST_PORT),
        '--host', TEST_HOST,
        '--metrics-dir', str(test_metrics_dir),
        '--project-name', 'test-playwright-project'
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    max_wait = 10
    for _ in range(max_wait):
        try:
            # Try to connect
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((TEST_HOST, TEST_PORT))
            sock.close()
            if result == 0:
                break
        except:
            pass
        time.sleep(1)
    else:
        process.kill()
        raise RuntimeError(f"Server failed to start within {max_wait} seconds")

    yield process

    # Cleanup
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture(scope='module')
async def browser():
    """Create Playwright browser instance."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest.fixture
async def page(browser: Browser):
    """Create new page for each test."""
    page = await browser.new_page()
    yield page
    await page.close()


@pytest.mark.asyncio
async def test_health_endpoint_browser(server_process, page: Page):
    """Test health check endpoint via browser."""
    # Navigate to health endpoint
    response = await page.goto(f'{BASE_URL}/health')

    # Check response status
    assert response.status == 200

    # Get JSON content
    content = await page.content()
    assert 'ok' in content

    # Parse JSON from page
    json_text = await page.evaluate('() => document.body.innerText')
    data = json.loads(json_text)

    assert data['status'] == 'ok'
    assert data['project'] == 'test-playwright-project'
    assert 'timestamp' in data
    assert data['agent_count'] == 2


@pytest.mark.asyncio
async def test_metrics_endpoint_browser(server_process, page: Page):
    """Test /api/metrics endpoint via browser."""
    # Navigate to metrics endpoint
    response = await page.goto(f'{BASE_URL}/api/metrics')

    # Check response status
    assert response.status == 200

    # Get JSON content
    json_text = await page.evaluate('() => document.body.innerText')
    data = json.loads(json_text)

    # Verify metrics structure
    assert data['project_name'] == 'test-playwright-project'
    assert data['version'] == 1
    assert data['total_sessions'] == 10
    assert data['total_tokens'] == 23000
    assert 'agents' in data
    assert 'coding_agent' in data['agents']
    assert 'github_agent' in data['agents']
    assert len(data['events']) == 10


@pytest.mark.asyncio
async def test_agent_endpoint_browser(server_process, page: Page):
    """Test /api/agents/<name> endpoint via browser."""
    # Navigate to agent endpoint
    response = await page.goto(f'{BASE_URL}/api/agents/coding_agent')

    # Check response status
    assert response.status == 200

    # Get JSON content
    json_text = await page.evaluate('() => document.body.innerText')
    data = json.loads(json_text)

    # Verify agent data
    assert 'agent' in data
    assert data['agent']['agent_name'] == 'coding_agent'
    assert data['agent']['total_invocations'] == 25
    assert data['agent']['success_rate'] == 0.88
    assert data['agent']['level'] == 3
    assert 'century_club' in data['agent']['achievements']


@pytest.mark.asyncio
async def test_agent_not_found_browser(server_process, page: Page):
    """Test /api/agents/<name> returns 404 for non-existent agent."""
    # Navigate to non-existent agent
    response = await page.goto(f'{BASE_URL}/api/agents/nonexistent_agent')

    # Check response status
    assert response.status == 404

    # Get JSON content
    json_text = await page.evaluate('() => document.body.innerText')
    data = json.loads(json_text)

    # Verify error response
    assert 'error' in data
    assert data['error'] == 'Agent not found'
    assert data['agent_name'] == 'nonexistent_agent'
    assert 'available_agents' in data
    assert 'coding_agent' in data['available_agents']
    assert 'github_agent' in data['available_agents']


@pytest.mark.asyncio
async def test_metrics_pretty_browser(server_process, page: Page):
    """Test /api/metrics with pretty parameter via browser."""
    # Navigate to metrics with pretty parameter
    response = await page.goto(f'{BASE_URL}/api/metrics?pretty')

    # Check response status
    assert response.status == 200

    # Get formatted JSON content
    json_text = await page.evaluate('() => document.body.innerText')

    # Verify it's pretty-printed (has newlines and indentation)
    assert '\n' in json_text
    data = json.loads(json_text)
    assert data['project_name'] == 'test-playwright-project'


@pytest.mark.asyncio
async def test_agent_with_events_browser(server_process, page: Page):
    """Test /api/agents/<name> with include_events parameter via browser."""
    # Navigate to agent with events
    response = await page.goto(f'{BASE_URL}/api/agents/coding_agent?include_events')

    # Check response status
    assert response.status == 200

    # Get JSON content
    json_text = await page.evaluate('() => document.body.innerText')
    data = json.loads(json_text)

    # Verify events are included
    assert 'agent' in data
    assert 'recent_events' in data
    assert len(data['recent_events']) > 0
    # Should have coding_agent events only
    for event in data['recent_events']:
        assert event['agent_name'] == 'coding_agent'


@pytest.mark.asyncio
async def test_cors_headers_browser(server_process, page: Page):
    """Test CORS headers are present in browser requests."""
    # Navigate to metrics endpoint
    response = await page.goto(f'{BASE_URL}/api/metrics')

    # Check CORS headers
    headers = response.headers
    assert 'access-control-allow-origin' in headers
    assert headers['access-control-allow-origin'] == '*'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s', '--tb=short'])
