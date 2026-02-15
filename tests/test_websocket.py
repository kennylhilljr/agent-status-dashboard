"""Comprehensive tests for WebSocket functionality in dashboard_server.py.

Tests cover:
- WebSocket connection and disconnection
- Real-time metrics broadcasting
- Multiple concurrent clients
- Reconnection handling
- Error handling and edge cases
- Graceful shutdown
"""

import asyncio
import json
import pytest
from pathlib import Path
from datetime import datetime
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from dashboard_server import DashboardServer
from metrics_store import MetricsStore
from metrics import DashboardState, AgentProfile, AgentEvent


class TestWebSocketServer(AioHTTPTestCase):
    """Integration tests for WebSocket functionality."""

    async def get_application(self):
        """Create test application instance."""
        # Create test server with temporary directory
        self.test_dir = Path('/tmp/test_websocket_server')
        self.test_dir.mkdir(exist_ok=True)

        # Initialize server with shorter broadcast interval for testing
        self.server = DashboardServer(
            project_name='test-ws-project',
            metrics_dir=self.test_dir,
            port=8889,
            host='127.0.0.1'
        )
        # Set broadcast interval to 1 second for faster testing
        self.server.broadcast_interval = 1

        # Create test metrics data
        self._create_test_metrics()

        # Store server reference in app for test access
        self.server.app['server'] = self.server

        return self.server.app

    def _create_test_metrics(self):
        """Create test metrics data for testing."""
        now = datetime.utcnow().isoformat() + 'Z'

        # Create test agent profile
        test_agent: AgentProfile = {
            'agent_name': 'ws_test_agent',
            'total_invocations': 5,
            'successful_invocations': 4,
            'failed_invocations': 1,
            'total_tokens': 1000,
            'total_cost_usd': 0.10,
            'total_duration_seconds': 50.0,
            'commits_made': 1,
            'prs_created': 0,
            'prs_merged': 0,
            'files_created': 2,
            'files_modified': 3,
            'lines_added': 50,
            'lines_removed': 10,
            'tests_written': 2,
            'issues_created': 0,
            'issues_completed': 0,
            'messages_sent': 0,
            'reviews_completed': 0,
            'success_rate': 0.8,
            'avg_duration_seconds': 10.0,
            'avg_tokens_per_call': 200.0,
            'cost_per_success_usd': 0.025,
            'xp': 400,
            'level': 1,
            'current_streak': 2,
            'best_streak': 3,
            'achievements': ['first_blood'],
            'strengths': ['fast_execution'],
            'weaknesses': [],
            'recent_events': ['event_1'],
            'last_error': '',
            'last_active': now
        }

        # Create test event
        test_event: AgentEvent = {
            'event_id': 'event_1',
            'agent_name': 'ws_test_agent',
            'session_id': 'session_1',
            'ticket_key': 'WS-1',
            'started_at': now,
            'ended_at': now,
            'duration_seconds': 10.0,
            'status': 'success',
            'input_tokens': 100,
            'output_tokens': 100,
            'total_tokens': 200,
            'estimated_cost_usd': 0.02,
            'artifacts': ['commit:xyz789'],
            'error_message': '',
            'model_used': 'claude-sonnet-4-5'
        }

        # Create test state
        state: DashboardState = {
            'version': 1,
            'project_name': 'test-ws-project',
            'created_at': now,
            'updated_at': now,
            'total_sessions': 1,
            'total_tokens': 1000,
            'total_cost_usd': 0.10,
            'total_duration_seconds': 50.0,
            'agents': {
                'ws_test_agent': test_agent,
            },
            'events': [test_event],
            'sessions': []
        }

        # Save test state
        self.server.store.save(state)

    @unittest_run_loop
    async def test_websocket_connection(self):
        """Test WebSocket connection establishes successfully."""
        async with self.client.ws_connect('/ws') as ws:
            # Should receive initial metrics immediately
            msg = await ws.receive_json(timeout=5)

            assert msg['type'] == 'metrics_update'
            assert 'timestamp' in msg
            assert 'data' in msg
            assert msg['data']['project_name'] == 'test-ws-project'
            assert 'ws_test_agent' in msg['data']['agents']

    @unittest_run_loop
    async def test_websocket_receives_updates(self):
        """Test WebSocket receives periodic updates."""
        async with self.client.ws_connect('/ws') as ws:
            # Receive initial message
            initial_msg = await ws.receive_json(timeout=5)
            assert initial_msg['type'] == 'metrics_update'

            # Wait for broadcast update (broadcast_interval = 1s)
            update_msg = await ws.receive_json(timeout=3)
            assert update_msg['type'] == 'metrics_update'
            assert 'timestamp' in update_msg
            assert update_msg['data']['project_name'] == 'test-ws-project'

    @unittest_run_loop
    async def test_websocket_multiple_clients(self):
        """Test multiple WebSocket clients can connect simultaneously."""
        # Connect multiple clients
        ws1 = await self.client.ws_connect('/ws')
        ws2 = await self.client.ws_connect('/ws')
        ws3 = await self.client.ws_connect('/ws')

        try:
            # All should receive initial messages
            msg1 = await ws1.receive_json(timeout=5)
            msg2 = await ws2.receive_json(timeout=5)
            msg3 = await ws3.receive_json(timeout=5)

            assert msg1['type'] == 'metrics_update'
            assert msg2['type'] == 'metrics_update'
            assert msg3['type'] == 'metrics_update'

            # All should receive broadcast updates
            update1 = await ws1.receive_json(timeout=3)
            update2 = await ws2.receive_json(timeout=3)
            update3 = await ws3.receive_json(timeout=3)

            assert update1['type'] == 'metrics_update'
            assert update2['type'] == 'metrics_update'
            assert update3['type'] == 'metrics_update'

            # Verify all have same data (from same broadcast)
            assert update1['data']['project_name'] == update2['data']['project_name']
            assert update2['data']['project_name'] == update3['data']['project_name']

        finally:
            await ws1.close()
            await ws2.close()
            await ws3.close()

    @unittest_run_loop
    async def test_websocket_ping_pong(self):
        """Test WebSocket ping/pong mechanism."""
        async with self.client.ws_connect('/ws') as ws:
            # Receive initial message
            await ws.receive_json(timeout=5)

            # Send ping
            await ws.send_str('ping')

            # Receive pong
            pong_msg = await ws.receive_str(timeout=5)
            assert pong_msg == 'pong'

    @unittest_run_loop
    async def test_websocket_graceful_close(self):
        """Test WebSocket graceful close from client side."""
        async with self.client.ws_connect('/ws') as ws:
            # Receive initial message
            await ws.receive_json(timeout=5)

            # Close connection gracefully
            await ws.close()

            # Verify closed
            assert ws.closed

    @unittest_run_loop
    async def test_websocket_client_disconnect_cleanup(self):
        """Test server cleans up disconnected clients."""
        # Get server instance from app
        server = self.app['server'] if 'server' in self.app else self.server

        # Connect and disconnect a client
        ws1 = await self.client.ws_connect('/ws')
        initial_count = len(server.websockets)
        assert initial_count >= 1

        await ws1.close()
        # Give server time to clean up
        await asyncio.sleep(0.5)

        # Connect new client and verify old one was cleaned up
        ws2 = await self.client.ws_connect('/ws')
        try:
            # Should have replaced the old connection
            current_count = len(server.websockets)
            assert current_count >= 1
        finally:
            await ws2.close()

    @unittest_run_loop
    async def test_websocket_metrics_data_validity(self):
        """Test WebSocket messages contain valid metrics data."""
        async with self.client.ws_connect('/ws') as ws:
            msg = await ws.receive_json(timeout=5)

            # Validate message structure
            assert 'type' in msg
            assert 'timestamp' in msg
            assert 'data' in msg

            # Validate metrics data structure
            data = msg['data']
            assert 'version' in data
            assert 'project_name' in data
            assert 'agents' in data
            assert 'events' in data
            assert 'total_sessions' in data
            assert 'total_tokens' in data

            # Validate agent data
            assert 'ws_test_agent' in data['agents']
            agent = data['agents']['ws_test_agent']
            assert agent['total_invocations'] == 5
            assert agent['success_rate'] == 0.8
            assert agent['xp'] == 400

    @unittest_run_loop
    async def test_websocket_broadcast_after_metrics_change(self):
        """Test WebSocket broadcasts updated metrics after changes."""
        # Get server instance from app
        server = self.app['server'] if 'server' in self.app else self.server

        async with self.client.ws_connect('/ws') as ws:
            # Receive initial message
            initial_msg = await ws.receive_json(timeout=5)
            initial_xp = initial_msg['data']['agents']['ws_test_agent']['xp']
            assert initial_xp == 400

            # Modify metrics
            state = server.store.load()
            state['agents']['ws_test_agent']['xp'] = 500
            server.store.save(state)

            # Wait for next broadcast
            update_msg = await ws.receive_json(timeout=3)
            updated_xp = update_msg['data']['agents']['ws_test_agent']['xp']
            assert updated_xp == 500

    @unittest_run_loop
    async def test_websocket_connection_tracking(self):
        """Test server tracks WebSocket connections correctly."""
        # Get server instance from app
        server = self.app['server'] if 'server' in self.app else self.server

        initial_count = len(server.websockets)

        # Connect first client
        ws1 = await self.client.ws_connect('/ws')
        await ws1.receive_json(timeout=5)
        count_after_first = len(server.websockets)
        assert count_after_first == initial_count + 1

        # Connect second client
        ws2 = await self.client.ws_connect('/ws')
        await ws2.receive_json(timeout=5)
        count_after_second = len(server.websockets)
        assert count_after_second == initial_count + 2

        # Close first client
        await ws1.close()
        await asyncio.sleep(0.5)  # Wait for cleanup
        count_after_close = len(server.websockets)
        assert count_after_close == initial_count + 1

        # Close second client
        await ws2.close()
        await asyncio.sleep(0.5)
        final_count = len(server.websockets)
        assert final_count == initial_count

    @unittest_run_loop
    async def test_websocket_receives_multiple_broadcasts(self):
        """Test WebSocket client receives multiple broadcast messages."""
        async with self.client.ws_connect('/ws') as ws:
            messages_received = []

            # Receive initial message
            msg = await ws.receive_json(timeout=5)
            messages_received.append(msg)

            # Receive 2 broadcast messages
            for i in range(2):
                msg = await ws.receive_json(timeout=3)
                messages_received.append(msg)

            assert len(messages_received) == 3
            for msg in messages_received:
                assert msg['type'] == 'metrics_update'
                assert 'timestamp' in msg
                assert 'data' in msg

    def tearDown(self):
        """Clean up test files."""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)


class TestWebSocketUnit:
    """Unit tests for WebSocket server components."""

    def test_websockets_set_initialization(self):
        """Test WebSocket connections set is initialized."""
        server = DashboardServer(
            project_name='test-ws-unit',
            port=9999
        )

        assert hasattr(server, 'websockets')
        assert isinstance(server.websockets, set)
        assert len(server.websockets) == 0

    def test_broadcast_interval_configuration(self):
        """Test broadcast interval can be configured."""
        server = DashboardServer(
            project_name='test-ws-unit',
            port=9999
        )

        assert hasattr(server, 'broadcast_interval')
        assert server.broadcast_interval == 5  # Default 5 seconds

        # Can be modified
        server.broadcast_interval = 10
        assert server.broadcast_interval == 10

    def test_websocket_route_registered(self):
        """Test WebSocket route is registered."""
        server = DashboardServer(
            project_name='test-ws-unit',
            port=9999
        )

        # Get all registered routes
        routes = [str(route.resource) for route in server.app.router.routes()]
        route_paths = [r.split("'")[1] if "'" in r else r for r in routes]

        assert any('/ws' in path for path in route_paths)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
