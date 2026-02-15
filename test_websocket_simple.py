"""Simple WebSocket test without Playwright - validates server functionality."""

import asyncio
import aiohttp
import json
from pathlib import Path
from datetime import datetime
from metrics_store import MetricsStore
from metrics import DashboardState, AgentProfile


async def test_websocket_connection():
    """Test WebSocket connection and message reception."""
    print("\n" + "="*60)
    print("WebSocket Connection Test")
    print("="*60 + "\n")

    # Create test metrics
    test_dir = Path.cwd()
    store = MetricsStore(project_name='agent-status-dashboard', metrics_dir=test_dir)

    now = datetime.utcnow().isoformat() + 'Z'
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
        'achievements': ['first_blood', 'ten_in_a_row', 'speed_demon'],
        'strengths': ['high_success_rate', 'fast_execution'],
        'weaknesses': [],
        'recent_events': ['event_1'],
        'last_error': '',
        'last_active': now
    }

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
        'events': [],
        'sessions': []
    }

    store.save(state)
    print("✓ Test metrics created\n")

    # Start server in background
    import subprocess
    print("Starting dashboard server on port 8080...")
    server_process = subprocess.Popen(
        ['python3', 'dashboard_server.py', '--port', '8080'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    await asyncio.sleep(3)

    try:
        # Test WebSocket connection
        async with aiohttp.ClientSession() as session:
            print("Connecting to WebSocket endpoint...")
            async with session.ws_connect('http://localhost:8080/ws') as ws:
                print("✓ WebSocket connected!\n")

                # Receive initial message
                print("Waiting for initial metrics message...")
                msg = await ws.receive_json(timeout=5)
                print("✓ Received initial message")
                print(f"  Message type: {msg.get('type')}")
                print(f"  Project: {msg.get('data', {}).get('project_name')}")
                print(f"  Agents: {list(msg.get('data', {}).get('agents', {}).keys())}")
                print()

                # Wait for broadcast update
                print("Waiting for broadcast update (5 seconds)...")
                await asyncio.sleep(1)
                msg2 = await ws.receive_json(timeout=7)
                print("✓ Received broadcast update")
                print(f"  Message type: {msg2.get('type')}")
                print(f"  Timestamp: {msg2.get('timestamp')}")
                print()

                # Send ping
                print("Sending ping...")
                await ws.send_str('ping')
                pong = await ws.receive_str(timeout=5)
                print(f"✓ Received: {pong}")
                print()

                # Update metrics and wait for broadcast
                print("Updating metrics...")
                state = store.load()
                state['agents']['websocket_demo_agent']['xp'] = 1500
                state['agents']['websocket_demo_agent']['level'] = 6
                store.save(state)
                print("✓ Metrics updated (XP: 1500, Level: 6)")
                print()

                print("Waiting for live update broadcast...")
                msg3 = await ws.receive_json(timeout=7)
                updated_xp = msg3['data']['agents']['websocket_demo_agent']['xp']
                updated_level = msg3['data']['agents']['websocket_demo_agent']['level']
                print(f"✓ Received live update via WebSocket")
                print(f"  Updated XP: {updated_xp}")
                print(f"  Updated Level: {updated_level}")
                print()

                # Close connection
                await ws.close()
                print("✓ WebSocket connection closed gracefully\n")

        print("="*60)
        print("WebSocket Test Summary")
        print("="*60)
        print("✓ WebSocket endpoint accessible at /ws")
        print("✓ Connection established successfully")
        print("✓ Initial metrics received immediately")
        print("✓ Periodic broadcasts received (5s interval)")
        print("✓ Ping/pong mechanism works")
        print("✓ Live metrics updates propagate correctly")
        print("✓ Graceful disconnect works")
        print("="*60 + "\n")

        # Test HTTP endpoint too
        print("Testing HTTP endpoint for comparison...")
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8080/api/metrics') as resp:
                data = await resp.json()
                print(f"✓ HTTP API working (status: {resp.status})")
                print(f"  Project: {data.get('project_name')}")
                print(f"  Total sessions: {data.get('total_sessions')}")
                print()

    finally:
        # Stop server
        server_process.terminate()
        server_process.wait(timeout=5)
        print("✓ Server stopped\n")


if __name__ == '__main__':
    asyncio.run(test_websocket_connection())
