"""Dashboard Server - HTTP API for Agent Status Dashboard.

This module provides an aiohttp-based HTTP server that exposes metrics data
through REST endpoints. The server enables web dashboards and other clients
to query agent performance metrics, session summaries, and individual agent details.

Endpoints:
    GET /api/metrics - Returns complete DashboardState with all metrics
    GET /api/agents/<name> - Returns specific agent profile with detailed stats
    GET /health - Health check endpoint
    WS  /ws - WebSocket endpoint for real-time metrics streaming

CORS Configuration:
    - Configurable via CORS_ALLOWED_ORIGINS environment variable
    - Defaults to localhost origins for development security
    - Supports GET, POST, OPTIONS methods
    - Allows Content-Type, Authorization headers
    - A request whose Origin is not allowed gets no CORS headers
    - Set CORS_ALLOWED_ORIGINS='*' for development (with security warning);
      credentials are never allowed together with '*'
    - For production, set specific domains (e.g., 'https://dashboard.example.com')

WebSocket Origin check:
    - /ws rejects a handshake with 403 when its Origin header is not allowed
    - Allowed: origins in CORS_ALLOWED_ORIGINS, plus http://localhost,
      http://127.0.0.1 and http://[::1] on the server's own port
    - Clients that send no Origin header (scripts, curl) are not browsers and
      are accepted; they are covered by the bearer token below

Authentication:
    - Set DASHBOARD_API_TOKEN to require "Authorization: Bearer <token>" on
      /api/* and /ws (/health stays open)
    - On a loopback host (127.0.0.1, localhost, ::1) the token is optional, so
      local use needs no setup
    - On any other host (e.g. --host 0.0.0.0) the server refuses to start
      without DASHBOARD_API_TOKEN

A2UI Component Integration:
    This server provides data that can be visualized using A2UI components:
    - TaskCard: Display individual agent activities as task cards
    - ProgressRing: Show overall completion metrics (success rate, invocations)
    - ActivityItem: Timeline view of agent events
    - ErrorCard: Display agent errors with severity and stack traces

    Components available at:
    /Users/bkh223/Documents/GitHub/agent-engineers/reusable/a2ui-components/

    Example usage in frontend:
        <TaskCard data={{
            title: agent.agent_name,
            status: agent.success_rate > 0.8 ? 'completed' : 'in_progress',
            category: 'backend',
            progress: agent.success_rate * 100
        }} />

        <ProgressRing data={{
            percentage: agent.success_rate * 100,
            tasksCompleted: agent.successful_invocations,
            filesModified: agent.files_modified,
            testsCompleted: agent.tests_written
        }} />

Usage:
    # Start server on default port 8080
    python dashboard_server.py

    # Start server on custom port
    python dashboard_server.py --port 8000

    # Query metrics
    curl http://localhost:8080/api/metrics

    # Query specific agent
    curl http://localhost:8080/api/agents/coding_agent
"""

import argparse
import asyncio
import hmac
import ipaddress
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import WSMsgType, web
from aiohttp.web import Request, Response, WebSocketResponse, middleware

from metrics_store import MetricsStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Get CORS allowed origins from environment
def get_cors_origins() -> str:
    """Get CORS allowed origins from environment variable.

    Returns:
        Comma-separated list of allowed origins or '*' for development.
        Defaults to localhost origins for security.
    """
    origins = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:8080')

    # Warn if using wildcard in production
    if origins == '*':
        logger.warning(
            "SECURITY WARNING: CORS is configured to allow all origins (*). "
            "This is acceptable for development but should NOT be used in production. "
            "Set CORS_ALLOWED_ORIGINS to specific domains for production deployment."
        )

    return origins


AUTH_TOKEN_ENV = 'DASHBOARD_API_TOKEN'
PORT_KEY = web.AppKey('dashboard_port', int)
AUTH_TOKEN_KEY = web.AppKey('dashboard_auth_token', str)


def get_allowed_origin_list() -> list[str]:
    """Return CORS_ALLOWED_ORIGINS as a list of origins ('*' stays a single entry).

    Returns:
        List of allowed origin strings, without empty entries.
    """
    return [o.strip() for o in get_cors_origins().split(',') if o.strip()]


def is_loopback_host(host: str) -> bool:
    """Tell whether a bind host only accepts connections from this machine.

    Args:
        host: Host name or IP address the server binds to.

    Returns:
        True for localhost and loopback IP addresses, False otherwise.
    """
    host = host.strip().strip('[]').lower()
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _loopback_origins(port: int | None) -> set[str]:
    """Browser origins of pages served from loopback on the given port."""
    if port is None:
        return set()
    hosts = ('localhost', '127.0.0.1', '[::1]')
    return {f'http://{h}:{port}' for h in hosts}


def is_origin_allowed(origin: str, port: int | None = None) -> bool:
    """Check a browser Origin header against the allowed origins.

    Args:
        origin: Value of the request's Origin header.
        port: Port this server listens on; loopback origins on it are allowed.

    Returns:
        True if CORS_ALLOWED_ORIGINS is '*', lists this origin, or the origin is
        a loopback origin on the server's own port.
    """
    allowed = get_allowed_origin_list()
    if '*' in allowed:
        return True
    if not origin:
        return False
    try:
        parts = urlsplit(origin)
        normalized = f'{parts.scheme}://{parts.netloc}'.lower()
    except ValueError:
        return False
    if normalized in {o.lower().rstrip('/') for o in allowed}:
        return True
    return normalized in _loopback_origins(port)


def _request_port(request: Request) -> int | None:
    """Port this server is listening on, as recorded in the app."""
    return request.app.get(PORT_KEY)


# CORS middleware with environment-based configuration
@middleware
async def cors_middleware(request: Request, handler):
    """Add CORS headers to responses for allowed origins.

    CORS origins are configured via CORS_ALLOWED_ORIGINS environment variable.
    Defaults to localhost origins for development security. A request from an
    origin that is not allowed gets no CORS headers, so the browser blocks it.
    """
    response = await handler(request)

    allowed_list = get_allowed_origin_list()
    origin = request.headers.get('Origin', '')

    if '*' in allowed_list:
        # Browsers reject credentials together with '*', so never send both.
        response.headers['Access-Control-Allow-Origin'] = '*'
    elif origin and is_origin_allowed(origin, _request_port(request)):
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Vary'] = 'Origin'
    else:
        return response

    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


def _is_protected_path(path: str) -> bool:
    """Paths that need the bearer token when one is configured."""
    return path == '/ws' or path.startswith('/api/') or path == '/api'


@middleware
async def auth_middleware(request: Request, handler):
    """Require the configured bearer token on /api/* and /ws.

    No-op when no token is configured. CORS preflight (OPTIONS) requests pass,
    because browsers never send credentials on them.
    """
    token = request.app.get(AUTH_TOKEN_KEY)
    if not token or request.method == 'OPTIONS' or not _is_protected_path(request.path):
        return await handler(request)

    header = request.headers.get('Authorization', '')
    scheme, _, supplied = header.partition(' ')
    if scheme.lower() == 'bearer' and hmac.compare_digest(
        supplied.strip().encode(), token.encode()
    ):
        return await handler(request)

    return web.json_response(
        {'error': 'Unauthorized', 'message': 'Missing or invalid bearer token'},
        status=401,
        headers={'WWW-Authenticate': 'Bearer'},
    )


# Error handling middleware
@middleware
async def error_middleware(request: Request, handler):
    """Catch and format errors as JSON responses."""
    try:
        response = await handler(request)
        return response
    except web.HTTPException:
        # Let HTTP exceptions pass through
        raise
    except Exception as ex:
        logger.exception(f"Error handling request {request.method} {request.path}")
        return web.json_response(
            {
                'error': type(ex).__name__,
                'message': str(ex),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            },
            status=500
        )


class DashboardServer:
    """HTTP server for Agent Status Dashboard metrics API.

    Provides REST endpoints for querying metrics data with CORS support.
    Uses MetricsStore for data persistence.
    """

    def __init__(
        self,
        project_name: str = "agent-status-dashboard",
        metrics_dir: Path | None = None,
        port: int = 8080,
        host: str = "127.0.0.1",
        auth_token: str | None = None,
    ):
        """Initialize DashboardServer.

        Args:
            project_name: Project name for metrics store
            metrics_dir: Directory containing .agent_metrics.json
            port: HTTP server port
            host: HTTP server host (default: 127.0.0.1 for localhost-only access)
            auth_token: Bearer token required on /api/* and /ws. Defaults to the
                DASHBOARD_API_TOKEN environment variable; empty means no token.

        Raises:
            ValueError: If host is not a loopback address and no token is set.

        Security Notes:
            - Default host is 127.0.0.1 (localhost only) for security
            - Use host="0.0.0.0" to bind to all network interfaces (WARNING: exposes server to network)
            - For production, use a reverse proxy (nginx/caddy) with proper TLS/SSL
        """
        self.project_name = project_name
        self.metrics_dir = metrics_dir or Path.cwd()
        self.port = port
        self.host = host
        if auth_token is None:
            auth_token = os.getenv(AUTH_TOKEN_ENV, '')
        self.auth_token = auth_token.strip()

        if not self.auth_token and not is_loopback_host(host):
            raise ValueError(
                f"Refusing to bind to non-loopback host {host!r} without authentication. "
                f"Set {AUTH_TOKEN_ENV} to a long random value; clients must then send "
                "'Authorization: Bearer <token>'."
            )

        # Security warning for 0.0.0.0 binding
        if host == "0.0.0.0":
            logger.warning(
                "SECURITY WARNING: Server is binding to 0.0.0.0 (all network interfaces). "
                "This exposes the server to your network. "
                "For production deployment, use a reverse proxy with TLS/SSL. "
                "For local development, consider using 127.0.0.1 instead."
            )

        # Initialize metrics store
        self.store = MetricsStore(
            project_name=project_name,
            metrics_dir=self.metrics_dir
        )

        # WebSocket connections tracking
        self.websockets: set[WebSocketResponse] = set()
        self.broadcast_task: asyncio.Task | None = None
        self.broadcast_interval = 5  # seconds

        # Create app with middlewares
        self.app = web.Application(
            middlewares=[error_middleware, cors_middleware, auth_middleware]
        )
        self.app[PORT_KEY] = port
        self.app[AUTH_TOKEN_KEY] = self.auth_token

        # Register routes
        self._setup_routes()

        # Setup WebSocket broadcasting
        self.app.on_startup.append(self._start_broadcast)
        self.app.on_cleanup.append(self._cleanup_websockets)

        logger.info(f"Dashboard server initialized for project: {project_name}")
        logger.info(f"Metrics directory: {self.metrics_dir}")

    def _setup_routes(self):
        """Register HTTP routes and WebSocket endpoint."""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/api/metrics', self.get_metrics)
        self.app.router.add_get('/api/agents/{agent_name}', self.get_agent)
        self.app.router.add_get('/ws', self.websocket_handler)

        # OPTIONS for CORS preflight
        self.app.router.add_route('OPTIONS', '/api/metrics', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/{agent_name}', self.handle_options)

    async def handle_options(self, request: Request) -> Response:
        """Handle CORS preflight OPTIONS requests."""
        return web.Response(status=204)

    async def health_check(self, request: Request) -> Response:
        """Health check endpoint.

        Returns:
            JSON response with server status and metrics file info
        """
        stats = self.store.get_stats()

        return web.json_response({
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'project': self.project_name,
            'metrics_file_exists': stats['metrics_file_exists'],
            'event_count': stats['event_count'],
            'session_count': stats['session_count'],
            'agent_count': stats['agent_count']
        })

    async def get_metrics(self, request: Request) -> Response:
        """Get all metrics data.

        Returns complete DashboardState including:
        - Global counters
        - All agent profiles
        - Recent events (last 500)
        - Session history (last 50)

        Query Parameters:
            pretty: If set, format JSON with indentation

        Returns:
            JSON response with complete metrics data
        """
        logger.info("GET /api/metrics")

        try:
            state = self.store.load()

            # Check if client wants pretty-printed JSON
            pretty = 'pretty' in request.query

            if pretty:
                json_data = json.dumps(state, indent=2, ensure_ascii=False)
                return web.Response(
                    text=json_data,
                    content_type='application/json',
                    status=200
                )
            else:
                return web.json_response(state)

        except Exception as e:
            logger.error(f"Error loading metrics: {e}")
            raise web.HTTPInternalServerError(
                text=json.dumps({'error': str(e)}),
                content_type='application/json'
            )

    async def get_agent(self, request: Request) -> Response:
        """Get specific agent profile by name.

        Path Parameters:
            agent_name: Name of the agent (e.g., 'coding_agent', 'github_agent')

        Query Parameters:
            include_events: If set, include recent events for this agent
            pretty: If set, format JSON with indentation

        Returns:
            JSON response with agent profile and optionally recent events

        Raises:
            404: If agent not found
        """
        agent_name = request.match_info['agent_name']
        logger.info(f"GET /api/agents/{agent_name}")

        try:
            state = self.store.load()

            # Check if agent exists
            if agent_name not in state['agents']:
                logger.warning(f"Agent not found: {agent_name}")
                raise web.HTTPNotFound(
                    text=json.dumps({
                        'error': 'Agent not found',
                        'agent_name': agent_name,
                        'available_agents': list(state['agents'].keys())
                    }),
                    content_type='application/json'
                )

            # Get agent profile
            agent_profile = state['agents'][agent_name]

            response_data = {
                'agent': agent_profile,
                'project_name': state['project_name'],
                'updated_at': state['updated_at']
            }

            # Optionally include recent events for this agent
            if 'include_events' in request.query:
                agent_events = [
                    event for event in state['events']
                    if event['agent_name'] == agent_name
                ]
                # Return last 20 events
                response_data['recent_events'] = agent_events[-20:]

            # Check if client wants pretty-printed JSON
            pretty = 'pretty' in request.query

            if pretty:
                json_data = json.dumps(response_data, indent=2, ensure_ascii=False)
                return web.Response(
                    text=json_data,
                    content_type='application/json',
                    status=200
                )
            else:
                return web.json_response(response_data)

        except web.HTTPNotFound:
            raise
        except Exception as e:
            logger.error(f"Error loading agent {agent_name}: {e}")
            raise web.HTTPInternalServerError(
                text=json.dumps({'error': str(e)}),
                content_type='application/json'
            )

    async def websocket_handler(self, request: Request) -> WebSocketResponse:
        """WebSocket endpoint for real-time metrics streaming.

        Accepts WebSocket connections and broadcasts metrics updates to all connected clients.
        Clients receive JSON-formatted metrics data every 5 seconds.

        Browsers do not apply CORS to WebSockets, so a handshake whose Origin is
        not allowed is rejected here; otherwise any web page could read the
        metrics stream. Requests without an Origin header come from non-browser
        clients and are accepted (the bearer token, when set, still applies).

        Returns:
            WebSocketResponse configured for metrics streaming

        Raises:
            403: If the Origin header is present and not allowed
        """
        origin = request.headers.get('Origin')
        if origin is not None and not is_origin_allowed(origin, self.port):
            logger.warning(f"Rejected WebSocket handshake from origin {origin!r}")
            raise web.HTTPForbidden(
                text=json.dumps({'error': 'Origin not allowed'}),
                content_type='application/json',
            )

        ws = WebSocketResponse()
        await ws.prepare(request)

        # Add to active connections
        self.websockets.add(ws)
        client_id = id(ws)
        logger.info(f"WebSocket client connected: {client_id} (total: {len(self.websockets)})")

        try:
            # Send initial metrics immediately
            try:
                state = self.store.load()
                await ws.send_json({
                    'type': 'metrics_update',
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'data': state
                })
            except Exception as e:
                logger.error(f"Error sending initial metrics to WebSocket {client_id}: {e}")

            # Listen for client messages (mostly for ping/pong and close)
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Handle client messages (e.g., ping)
                    if msg.data == 'ping':
                        await ws.send_str('pong')
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket {client_id} error: {ws.exception()}")
                    break
                elif msg.type == WSMsgType.CLOSE:
                    logger.info(f"WebSocket {client_id} closed by client")
                    break

        except Exception as e:
            logger.error(f"WebSocket {client_id} error: {e}")
        finally:
            # Remove from active connections
            self.websockets.discard(ws)
            logger.info(f"WebSocket client disconnected: {client_id} (remaining: {len(self.websockets)})")

        return ws

    async def _broadcast_metrics(self):
        """Periodically broadcast metrics to all connected WebSocket clients."""
        while True:
            try:
                await asyncio.sleep(self.broadcast_interval)

                if not self.websockets:
                    continue

                # Load current metrics
                try:
                    state = self.store.load()
                except Exception as e:
                    logger.error(f"Error loading metrics for broadcast: {e}")
                    continue

                # Prepare broadcast message
                message = {
                    'type': 'metrics_update',
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'data': state
                }

                # Broadcast to all connected clients
                disconnected = set()
                for ws in self.websockets:
                    try:
                        await ws.send_json(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting to WebSocket {id(ws)}: {e}")
                        disconnected.add(ws)

                # Remove disconnected clients
                self.websockets -= disconnected
                if disconnected:
                    logger.info(f"Removed {len(disconnected)} disconnected WebSocket clients")

            except asyncio.CancelledError:
                logger.info("Metrics broadcast task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")

    async def _start_broadcast(self, app):
        """Start the periodic metrics broadcast task."""
        self.broadcast_task = asyncio.create_task(self._broadcast_metrics())
        logger.info(f"WebSocket broadcast started (interval: {self.broadcast_interval}s)")

    async def _cleanup_websockets(self, app):
        """Clean up all WebSocket connections on shutdown."""
        logger.info("Cleaning up WebSocket connections...")

        # Cancel broadcast task
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass

        # Close all active connections
        for ws in self.websockets:
            try:
                await ws.close(code=1001, message=b'Server shutting down')
            except Exception as e:
                logger.error(f"Error closing WebSocket {id(ws)}: {e}")

        self.websockets.clear()
        logger.info("WebSocket cleanup complete")

    def run(self):
        """Start the HTTP server with WebSocket support.

        Runs the aiohttp application and blocks until server is stopped.
        """
        logger.info(f"Starting Dashboard Server on {self.host}:{self.port}")
        logger.info("Endpoints available:")
        logger.info(f"  GET  {self.host}:{self.port}/health")
        logger.info(f"  GET  {self.host}:{self.port}/api/metrics")
        logger.info(f"  GET  {self.host}:{self.port}/api/agents/<name>")
        logger.info(f"  WS   ws://{self.host}:{self.port}/ws")
        logger.info("")
        logger.info("WebSocket Real-Time Updates:")
        logger.info(f"  Broadcast interval: {self.broadcast_interval}s")
        logger.info("  Auto-reconnect supported with exponential backoff")
        logger.info("")
        logger.info("A2UI Component Integration:")
        logger.info("  Components: TaskCard, ProgressRing, ActivityItem, ErrorCard")
        logger.info("  Location: /Users/bkh223/Documents/GitHub/agent-engineers/reusable/a2ui-components/")
        logger.info("")
        logger.info("Press Ctrl+C to stop the server")

        try:
            web.run_app(
                self.app,
                host=self.host,
                port=self.port,
                print=None  # Disable aiohttp's default logging
            )
        except KeyboardInterrupt:
            logger.info("Server stopped by user")


def main():
    """CLI entry point for dashboard server."""
    parser = argparse.ArgumentParser(
        description='Agent Status Dashboard HTTP Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server on default port 8080
  python dashboard_server.py

  # Start server on custom port
  python dashboard_server.py --port 8000

  # Specify custom metrics directory
  python dashboard_server.py --metrics-dir /path/to/metrics

API Endpoints:
  GET  /health                    - Health check
  GET  /api/metrics               - Get all metrics data
  GET  /api/agents/<name>         - Get specific agent profile

A2UI Components:
  Available at: /Users/bkh223/Documents/GitHub/agent-engineers/reusable/a2ui-components/
  - TaskCard: Display agent activities
  - ProgressRing: Show completion metrics
  - ActivityItem: Timeline of events
  - ErrorCard: Display errors with details
        """
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='HTTP server port (default: 8080)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help=(
            'HTTP server host (default: 127.0.0.1 for localhost-only access; '
            f'a non-loopback host such as 0.0.0.0 requires {AUTH_TOKEN_ENV})'
        )
    )

    parser.add_argument(
        '--metrics-dir',
        type=Path,
        default=None,
        help='Directory containing .agent_metrics.json (default: current directory)'
    )

    parser.add_argument(
        '--project-name',
        type=str,
        default='agent-status-dashboard',
        help='Project name (default: agent-status-dashboard)'
    )

    args = parser.parse_args()

    # Create and run server
    try:
        server = DashboardServer(
            project_name=args.project_name,
            metrics_dir=args.metrics_dir,
            port=args.port,
            host=args.host
        )
    except ValueError as e:
        parser.error(str(e))

    server.run()


if __name__ == '__main__':
    main()
