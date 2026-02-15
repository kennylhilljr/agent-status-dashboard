"""Comprehensive tests for dashboard_server.py.

Tests cover:
- Server initialization and configuration
- Health check endpoint
- GET /api/metrics endpoint
- GET /api/agents/<name> endpoint
- CORS configuration
- Error handling (404, 500)
- Query parameters (pretty, include_events)
- Edge cases (empty metrics, non-existent agents)
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from dashboard_server import DashboardServer
from metrics_store import MetricsStore
from metrics import DashboardState, AgentProfile, AgentEvent


class TestDashboardServer(AioHTTPTestCase):
    """Integration tests for DashboardServer using aiohttp test client."""

    async def get_application(self):
        """Create test application instance."""
        # Create test server with temporary directory
        self.test_dir = Path('/tmp/test_dashboard_server')
        self.test_dir.mkdir(exist_ok=True)

        # Initialize server
        self.server = DashboardServer(
            project_name='test-project',
            metrics_dir=self.test_dir,
            port=8888,
            host='127.0.0.1'
        )

        # Create test metrics data
        self._create_test_metrics()

        return self.server.app

    def _create_test_metrics(self):
        """Create test metrics data for testing."""
        now = datetime.utcnow().isoformat() + 'Z'

        # Create test agent profile
        test_agent: AgentProfile = {
            'agent_name': 'test_agent',
            'total_invocations': 10,
            'successful_invocations': 8,
            'failed_invocations': 2,
            'total_tokens': 5000,
            'total_cost_usd': 0.50,
            'total_duration_seconds': 120.0,
            'commits_made': 3,
            'prs_created': 1,
            'prs_merged': 1,
            'files_created': 5,
            'files_modified': 10,
            'lines_added': 200,
            'lines_removed': 50,
            'tests_written': 8,
            'issues_created': 0,
            'issues_completed': 0,
            'messages_sent': 0,
            'reviews_completed': 0,
            'success_rate': 0.8,
            'avg_duration_seconds': 12.0,
            'avg_tokens_per_call': 500.0,
            'cost_per_success_usd': 0.0625,
            'xp': 800,
            'level': 2,
            'current_streak': 3,
            'best_streak': 5,
            'achievements': ['first_blood', 'ten_in_a_row'],
            'strengths': ['high_success_rate', 'fast_execution'],
            'weaknesses': ['needs_more_tests'],
            'recent_events': ['event_1', 'event_2'],
            'last_error': 'Test error message',
            'last_active': now
        }

        # Create test event
        test_event: AgentEvent = {
            'event_id': 'event_1',
            'agent_name': 'test_agent',
            'session_id': 'session_1',
            'ticket_key': 'TEST-1',
            'started_at': now,
            'ended_at': now,
            'duration_seconds': 10.0,
            'status': 'success',
            'input_tokens': 100,
            'output_tokens': 200,
            'total_tokens': 300,
            'estimated_cost_usd': 0.03,
            'artifacts': ['commit:abc123', 'file:test.py'],
            'error_message': '',
            'model_used': 'claude-sonnet-4-5'
        }

        # Create test state
        state: DashboardState = {
            'version': 1,
            'project_name': 'test-project',
            'created_at': now,
            'updated_at': now,
            'total_sessions': 5,
            'total_tokens': 5000,
            'total_cost_usd': 0.50,
            'total_duration_seconds': 120.0,
            'agents': {
                'test_agent': test_agent,
            },
            'events': [test_event],
            'sessions': []
        }

        # Save test state
        self.server.store.save(state)

    @unittest_run_loop
    async def test_health_check(self):
        """Test health check endpoint returns correct status."""
        resp = await self.client.request('GET', '/health')
        assert resp.status == 200

        data = await resp.json()
        assert data['status'] == 'ok'
        assert data['project'] == 'test-project'
        assert 'timestamp' in data
        assert 'metrics_file_exists' in data
        assert data['agent_count'] == 1
        assert data['event_count'] == 1

    @unittest_run_loop
    async def test_get_metrics_success(self):
        """Test GET /api/metrics returns complete metrics data."""
        resp = await self.client.request('GET', '/api/metrics')
        assert resp.status == 200

        data = await resp.json()
        assert data['project_name'] == 'test-project'
        assert data['version'] == 1
        assert data['total_sessions'] == 5
        assert data['total_tokens'] == 5000
        assert 'agents' in data
        assert 'test_agent' in data['agents']
        assert len(data['events']) == 1
        assert data['agents']['test_agent']['total_invocations'] == 10

    @unittest_run_loop
    async def test_get_metrics_pretty(self):
        """Test GET /api/metrics with pretty query parameter."""
        resp = await self.client.request('GET', '/api/metrics?pretty')
        assert resp.status == 200

        text = await resp.text()
        # Check that JSON is indented (pretty-printed)
        assert '\n' in text
        assert '  "version"' in text or '  ' in text

        # Verify it's valid JSON
        data = json.loads(text)
        assert data['project_name'] == 'test-project'

    @unittest_run_loop
    async def test_get_agent_success(self):
        """Test GET /api/agents/<name> returns agent profile."""
        resp = await self.client.request('GET', '/api/agents/test_agent')
        assert resp.status == 200

        data = await resp.json()
        assert 'agent' in data
        assert data['agent']['agent_name'] == 'test_agent'
        assert data['agent']['total_invocations'] == 10
        assert data['agent']['success_rate'] == 0.8
        assert data['project_name'] == 'test-project'
        assert 'updated_at' in data

    @unittest_run_loop
    async def test_get_agent_not_found(self):
        """Test GET /api/agents/<name> returns 404 for non-existent agent."""
        resp = await self.client.request('GET', '/api/agents/nonexistent_agent')
        assert resp.status == 404

        data = await resp.json()
        assert 'error' in data
        assert data['error'] == 'Agent not found'
        assert data['agent_name'] == 'nonexistent_agent'
        assert 'available_agents' in data
        assert 'test_agent' in data['available_agents']

    @unittest_run_loop
    async def test_get_agent_with_events(self):
        """Test GET /api/agents/<name> with include_events parameter."""
        resp = await self.client.request('GET', '/api/agents/test_agent?include_events')
        assert resp.status == 200

        data = await resp.json()
        assert 'agent' in data
        assert 'recent_events' in data
        assert len(data['recent_events']) == 1
        assert data['recent_events'][0]['event_id'] == 'event_1'
        assert data['recent_events'][0]['agent_name'] == 'test_agent'

    @unittest_run_loop
    async def test_get_agent_pretty(self):
        """Test GET /api/agents/<name> with pretty parameter."""
        resp = await self.client.request('GET', '/api/agents/test_agent?pretty')
        assert resp.status == 200

        text = await resp.text()
        # Check that JSON is indented
        assert '\n' in text

        # Verify it's valid JSON
        data = json.loads(text)
        assert data['agent']['agent_name'] == 'test_agent'

    @unittest_run_loop
    async def test_cors_headers(self):
        """Test CORS headers are present in responses."""
        resp = await self.client.request('GET', '/api/metrics')
        assert resp.status == 200

        # Check CORS headers - should be localhost by default (security-first)
        assert 'Access-Control-Allow-Origin' in resp.headers
        # Default allows localhost origins
        assert resp.headers['Access-Control-Allow-Origin'] in [
            'http://localhost:3000',
            'http://localhost:8080',
            'http://127.0.0.1:3000',
            'http://127.0.0.1:8080'
        ]
        assert 'Access-Control-Allow-Methods' in resp.headers
        assert 'Access-Control-Allow-Headers' in resp.headers

    @unittest_run_loop
    async def test_cors_preflight_options(self):
        """Test CORS preflight OPTIONS requests are handled."""
        resp = await self.client.request('OPTIONS', '/api/metrics')
        assert resp.status == 204

        # OPTIONS should have CORS headers - should be localhost by default (security-first)
        assert 'Access-Control-Allow-Origin' in resp.headers
        assert resp.headers['Access-Control-Allow-Origin'] in [
            'http://localhost:3000',
            'http://localhost:8080',
            'http://127.0.0.1:3000',
            'http://127.0.0.1:8080'
        ]

    @unittest_run_loop
    async def test_empty_metrics(self):
        """Test server handles empty metrics gracefully."""
        # Create empty state using the store from the app
        empty_state: DashboardState = {
            'version': 1,
            'project_name': 'test-project',
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'updated_at': datetime.utcnow().isoformat() + 'Z',
            'total_sessions': 0,
            'total_tokens': 0,
            'total_cost_usd': 0.0,
            'total_duration_seconds': 0.0,
            'agents': {},
            'events': [],
            'sessions': []
        }
        # Access store from the test directory
        store = MetricsStore(project_name='test-project', metrics_dir=self.test_dir)
        store.save(empty_state)

        resp = await self.client.request('GET', '/api/metrics')
        assert resp.status == 200

        data = await resp.json()
        assert data['total_sessions'] == 0
        assert len(data['agents']) == 0
        assert len(data['events']) == 0

    @unittest_run_loop
    async def test_health_check_cors(self):
        """Test health check endpoint has CORS headers."""
        resp = await self.client.request('GET', '/health')
        assert resp.status == 200
        # Should be localhost by default (security-first)
        assert 'Access-Control-Allow-Origin' in resp.headers
        assert resp.headers['Access-Control-Allow-Origin'] in [
            'http://localhost:3000',
            'http://localhost:8080',
            'http://127.0.0.1:3000',
            'http://127.0.0.1:8080'
        ]

    def tearDown(self):
        """Clean up test files."""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)


class TestDashboardServerUnit:
    """Unit tests for DashboardServer without HTTP client."""

    def test_server_initialization(self):
        """Test server initializes with correct configuration."""
        server = DashboardServer(
            project_name='test-project',
            metrics_dir=Path('/tmp/test'),
            port=9999,
            host='127.0.0.1'
        )

        assert server.project_name == 'test-project'
        assert server.port == 9999
        assert server.host == '127.0.0.1'
        assert server.store is not None
        assert server.app is not None

    def test_server_default_values(self):
        """Test server uses correct default values."""
        server = DashboardServer()

        assert server.project_name == 'agent-status-dashboard'
        assert server.port == 8080
        assert server.host == '127.0.0.1'  # Default is localhost-only for security
        assert server.metrics_dir == Path.cwd()

    def test_routes_registered(self):
        """Test all routes are registered correctly."""
        server = DashboardServer()

        # Get all registered routes
        routes = [str(route.resource) for route in server.app.router.routes()]

        # Check required routes exist
        route_paths = [r.split("'")[1] if "'" in r else r for r in routes]

        assert any('/health' in path for path in route_paths)
        assert any('/api/metrics' in path for path in route_paths)
        assert any('/api/agents/{agent_name}' in path for path in route_paths)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
