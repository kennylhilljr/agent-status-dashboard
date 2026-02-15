"""Demo script for dashboard_server.py with Playwright browser testing.

This script:
1. Starts the dashboard server in background
2. Uses Playwright to test endpoints in a real browser
3. Takes screenshots of API responses
4. Generates evidence report
"""

import asyncio
import json
import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime

from metrics_store import MetricsStore
from metrics import DashboardState, AgentProfile, AgentEvent


# Server configuration
SERVER_PORT = 8765
SERVER_HOST = 'localhost'
BASE_URL = f'http://{SERVER_HOST}:{SERVER_PORT}'


def create_demo_metrics():
    """Create demo metrics data for testing."""
    now = datetime.utcnow().isoformat() + 'Z'

    # Create demo agent profiles
    coding_agent: AgentProfile = {
        'agent_name': 'coding_agent',
        'total_invocations': 50,
        'successful_invocations': 45,
        'failed_invocations': 5,
        'total_tokens': 25000,
        'total_cost_usd': 2.50,
        'total_duration_seconds': 600.0,
        'commits_made': 20,
        'prs_created': 8,
        'prs_merged': 6,
        'files_created': 30,
        'files_modified': 75,
        'lines_added': 1500,
        'lines_removed': 300,
        'tests_written': 40,
        'issues_created': 0,
        'issues_completed': 0,
        'messages_sent': 0,
        'reviews_completed': 0,
        'success_rate': 0.90,
        'avg_duration_seconds': 12.0,
        'avg_tokens_per_call': 500.0,
        'cost_per_success_usd': 0.056,
        'xp': 4500,
        'level': 4,
        'current_streak': 12,
        'best_streak': 18,
        'achievements': ['first_blood', 'ten_in_a_row', 'century_club', 'speed_demon'],
        'strengths': ['high_success_rate', 'fast_execution', 'thorough_testing'],
        'weaknesses': [],
        'recent_events': ['evt_1', 'evt_2', 'evt_3', 'evt_4', 'evt_5'],
        'last_error': '',
        'last_active': now
    }

    github_agent: AgentProfile = {
        'agent_name': 'github_agent',
        'total_invocations': 30,
        'successful_invocations': 28,
        'failed_invocations': 2,
        'total_tokens': 15000,
        'total_cost_usd': 1.50,
        'total_duration_seconds': 300.0,
        'commits_made': 10,
        'prs_created': 10,
        'prs_merged': 8,
        'files_created': 0,
        'files_modified': 0,
        'lines_added': 0,
        'lines_removed': 0,
        'tests_written': 0,
        'issues_created': 5,
        'issues_completed': 3,
        'messages_sent': 0,
        'reviews_completed': 7,
        'success_rate': 0.93,
        'avg_duration_seconds': 10.0,
        'avg_tokens_per_call': 500.0,
        'cost_per_success_usd': 0.054,
        'xp': 2800,
        'level': 3,
        'current_streak': 8,
        'best_streak': 12,
        'achievements': ['first_blood', 'pr_master', 'reviewer_extraordinaire'],
        'strengths': ['high_success_rate', 'efficient', 'collaborative'],
        'weaknesses': [],
        'recent_events': ['evt_6', 'evt_7', 'evt_8'],
        'last_error': '',
        'last_active': now
    }

    linear_agent: AgentProfile = {
        'agent_name': 'linear_agent',
        'total_invocations': 20,
        'successful_invocations': 19,
        'failed_invocations': 1,
        'total_tokens': 8000,
        'total_cost_usd': 0.80,
        'total_duration_seconds': 200.0,
        'commits_made': 0,
        'prs_created': 0,
        'prs_merged': 0,
        'files_created': 0,
        'files_modified': 0,
        'lines_added': 0,
        'lines_removed': 0,
        'tests_written': 0,
        'issues_created': 15,
        'issues_completed': 12,
        'messages_sent': 0,
        'reviews_completed': 0,
        'success_rate': 0.95,
        'avg_duration_seconds': 10.0,
        'avg_tokens_per_call': 400.0,
        'cost_per_success_usd': 0.042,
        'xp': 1900,
        'level': 2,
        'current_streak': 6,
        'best_streak': 10,
        'achievements': ['first_blood', 'issue_master'],
        'strengths': ['high_success_rate', 'efficient'],
        'weaknesses': [],
        'recent_events': ['evt_9', 'evt_10'],
        'last_error': 'Rate limit exceeded',
        'last_active': now
    }

    # Create demo events
    events = [
        {
            'event_id': f'evt_{i}',
            'agent_name': ['coding_agent', 'github_agent', 'linear_agent'][i % 3],
            'session_id': 'demo_session',
            'ticket_key': f'DEMO-{i}',
            'started_at': now,
            'ended_at': now,
            'duration_seconds': 10.0 + i,
            'status': 'success' if i % 8 != 7 else 'error',
            'input_tokens': 100 + i * 10,
            'output_tokens': 200 + i * 20,
            'total_tokens': 300 + i * 30,
            'estimated_cost_usd': 0.03 + i * 0.01,
            'artifacts': [f'commit:demo{i}', f'file:demo{i}.py'],
            'error_message': 'Demo error' if i % 8 == 7 else '',
            'model_used': 'claude-sonnet-4-5'
        }
        for i in range(1, 21)
    ]

    # Create demo state
    state: DashboardState = {
        'version': 1,
        'project_name': 'dashboard-server-demo',
        'created_at': now,
        'updated_at': now,
        'total_sessions': 15,
        'total_tokens': 48000,
        'total_cost_usd': 4.80,
        'total_duration_seconds': 1100.0,
        'agents': {
            'coding_agent': coding_agent,
            'github_agent': github_agent,
            'linear_agent': linear_agent,
        },
        'events': events,
        'sessions': []
    }

    # Save demo state
    store = MetricsStore(project_name='dashboard-server-demo', metrics_dir=Path.cwd())
    store.save(state)
    print(f"✓ Created demo metrics with {len(state['agents'])} agents and {len(events)} events")


def start_server():
    """Start dashboard server in background."""
    print(f"\nStarting dashboard server on {BASE_URL}...")

    cmd = [
        sys.executable,
        'dashboard_server.py',
        '--port', str(SERVER_PORT),
        '--host', SERVER_HOST,
        '--project-name', 'dashboard-server-demo'
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    max_wait = 15
    for i in range(max_wait):
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((SERVER_HOST, SERVER_PORT))
            sock.close()
            if result == 0:
                print(f"✓ Server started successfully on {BASE_URL}")
                return process
        except:
            pass
        time.sleep(1)
        if i % 3 == 0:
            print(f"  Waiting for server... ({i}/{max_wait}s)")

    process.kill()
    raise RuntimeError(f"Server failed to start within {max_wait} seconds")


async def test_with_playwright(screenshot_dir: Path):
    """Test endpoints with Playwright and take screenshots."""
    print("\n" + "="*70)
    print("PLAYWRIGHT BROWSER TESTS")
    print("="*70)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: python -m playwright install")
        return False

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Test 1: Health check
        print("\n1. Testing /health endpoint...")
        try:
            response = await page.goto(f'{BASE_URL}/health', wait_until='networkidle')
            assert response.status == 200, f"Expected 200, got {response.status}"

            content = await page.evaluate('() => document.body.innerText')
            data = json.loads(content)

            print(f"   ✓ Health check passed")
            print(f"   - Status: {data['status']}")
            print(f"   - Project: {data['project']}")
            print(f"   - Agents: {data['agent_count']}")
            print(f"   - Events: {data['event_count']}")

            # Take screenshot
            await page.screenshot(path=str(screenshot_dir / 'health_endpoint.png'))
            print(f"   ✓ Screenshot saved: health_endpoint.png")

        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            return False

        # Test 2: Get all metrics
        print("\n2. Testing /api/metrics endpoint...")
        try:
            response = await page.goto(f'{BASE_URL}/api/metrics', wait_until='networkidle')
            assert response.status == 200

            content = await page.evaluate('() => document.body.innerText')
            data = json.loads(content)

            print(f"   ✓ Metrics endpoint passed")
            print(f"   - Total sessions: {data['total_sessions']}")
            print(f"   - Total tokens: {data['total_tokens']:,}")
            print(f"   - Total cost: ${data['total_cost_usd']:.2f}")
            print(f"   - Agents: {', '.join(data['agents'].keys())}")

            # Take screenshot
            await page.screenshot(path=str(screenshot_dir / 'metrics_endpoint.png'))
            print(f"   ✓ Screenshot saved: metrics_endpoint.png")

        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            return False

        # Test 3: Get specific agent
        print("\n3. Testing /api/agents/coding_agent endpoint...")
        try:
            response = await page.goto(f'{BASE_URL}/api/agents/coding_agent', wait_until='networkidle')
            assert response.status == 200

            content = await page.evaluate('() => document.body.innerText')
            data = json.loads(content)

            agent = data['agent']
            print(f"   ✓ Agent endpoint passed")
            print(f"   - Agent: {agent['agent_name']}")
            print(f"   - Invocations: {agent['total_invocations']}")
            print(f"   - Success rate: {agent['success_rate']*100:.1f}%")
            print(f"   - Level: {agent['level']}")
            print(f"   - XP: {agent['xp']}")
            print(f"   - Achievements: {', '.join(agent['achievements'])}")

            # Take screenshot
            await page.screenshot(path=str(screenshot_dir / 'agent_endpoint.png'))
            print(f"   ✓ Screenshot saved: agent_endpoint.png")

        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            return False

        # Test 4: Test 404 error
        print("\n4. Testing 404 error handling...")
        try:
            response = await page.goto(f'{BASE_URL}/api/agents/nonexistent', wait_until='networkidle')
            assert response.status == 404

            content = await page.evaluate('() => document.body.innerText')
            data = json.loads(content)

            print(f"   ✓ 404 error handling passed")
            print(f"   - Error: {data['error']}")
            print(f"   - Available agents: {', '.join(data['available_agents'])}")

            # Take screenshot
            await page.screenshot(path=str(screenshot_dir / '404_error.png'))
            print(f"   ✓ Screenshot saved: 404_error.png")

        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            return False

        await browser.close()

    print("\n" + "="*70)
    print("ALL PLAYWRIGHT TESTS PASSED ✓")
    print("="*70)
    return True


def main():
    """Run demo and tests."""
    print("="*70)
    print("DASHBOARD SERVER DEMO & PLAYWRIGHT TESTS")
    print("="*70)

    # Create screenshot directory
    screenshot_dir = Path('verification_evidence')
    screenshot_dir.mkdir(exist_ok=True)

    # Create demo metrics
    create_demo_metrics()

    # Start server
    server_process = None
    try:
        server_process = start_server()

        # Run Playwright tests
        success = asyncio.run(test_with_playwright(screenshot_dir))

        if success:
            print("\n" + "="*70)
            print("DEMO COMPLETED SUCCESSFULLY")
            print("="*70)
            print(f"\nScreenshots saved in: {screenshot_dir.absolute()}")
            print(f"Server URL: {BASE_URL}")
            print("\nEndpoints:")
            print(f"  - {BASE_URL}/health")
            print(f"  - {BASE_URL}/api/metrics")
            print(f"  - {BASE_URL}/api/agents/coding_agent")
            print(f"  - {BASE_URL}/api/agents/github_agent")
            print(f"  - {BASE_URL}/api/agents/linear_agent")
            return 0
        else:
            print("\nSome tests failed. See output above.")
            return 1

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Stop server
        if server_process:
            print("\nStopping server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
            print("✓ Server stopped")


if __name__ == '__main__':
    sys.exit(main())
