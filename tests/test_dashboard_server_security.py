"""Security tests for dashboard_server.py: WebSocket Origin check, CORS and bearer auth."""

import aiohttp
import pytest
from aiohttp.test_utils import TestClient, TestServer

import dashboard_server
from dashboard_server import DashboardServer, is_loopback_host, is_origin_allowed

PORT = 8890
TOKEN = 'test-token-not-a-secret'


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv('CORS_ALLOWED_ORIGINS', raising=False)
    monkeypatch.delenv(dashboard_server.AUTH_TOKEN_ENV, raising=False)


async def _client(tmp_path, **kwargs) -> TestClient:
    server = DashboardServer(
        project_name='sec-test', metrics_dir=tmp_path, port=PORT, **kwargs
    )
    client = TestClient(TestServer(server.app))
    await client.start_server()
    return client


async def _ws_status(client: TestClient, headers: dict[str, str]) -> int:
    try:
        ws = await client.ws_connect('/ws', headers=headers)
    except aiohttp.WSServerHandshakeError as e:
        return e.status
    await ws.close()
    return 101


# --- WebSocket Origin check -------------------------------------------------

async def test_ws_rejects_foreign_origin(tmp_path):
    client = await _client(tmp_path)
    try:
        assert await _ws_status(client, {'Origin': 'https://evil.example'}) == 403
        assert await _ws_status(client, {'Origin': 'null'}) == 403
        # Loopback, but a different port than the server: not allowed by default.
        assert await _ws_status(client, {'Origin': 'http://localhost:9999'}) == 403
    finally:
        await client.close()


async def test_ws_accepts_allowed_and_loopback_origins(tmp_path):
    client = await _client(tmp_path)
    try:
        assert await _ws_status(client, {'Origin': 'http://localhost:3000'}) == 101
        assert await _ws_status(client, {'Origin': f'http://127.0.0.1:{PORT}'}) == 101
        assert await _ws_status(client, {'Origin': f'http://[::1]:{PORT}'}) == 101
        # Non-browser clients send no Origin.
        assert await _ws_status(client, {}) == 101
    finally:
        await client.close()


async def test_ws_origin_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', 'https://dash.example.com')
    client = await _client(tmp_path)
    try:
        assert await _ws_status(client, {'Origin': 'https://dash.example.com'}) == 101
        assert await _ws_status(client, {'Origin': 'http://localhost:3000'}) == 403
    finally:
        await client.close()


# --- CORS --------------------------------------------------------------------

async def test_cors_wildcard_never_sends_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', '*')
    client = await _client(tmp_path)
    try:
        resp = await client.get('/api/metrics', headers={'Origin': 'https://a.example'})
        assert resp.headers['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Credentials' not in resp.headers
    finally:
        await client.close()


async def test_cors_mismatch_omits_headers(tmp_path):
    client = await _client(tmp_path)
    try:
        resp = await client.get('/api/metrics', headers={'Origin': 'https://evil.example'})
        assert 'Access-Control-Allow-Origin' not in resp.headers
        assert 'Access-Control-Allow-Credentials' not in resp.headers
    finally:
        await client.close()


# --- Bearer token ------------------------------------------------------------

async def test_no_token_on_loopback_needs_no_auth(tmp_path):
    client = await _client(tmp_path, host='127.0.0.1')
    try:
        assert (await client.get('/api/metrics')).status == 200
        assert await _ws_status(client, {}) == 101
    finally:
        await client.close()


async def test_token_required_on_api_and_ws(tmp_path):
    client = await _client(tmp_path, auth_token=TOKEN)
    try:
        assert (await client.get('/api/metrics')).status == 401
        assert (await client.get('/api/agents/x')).status == 401
        resp = await client.get('/api/metrics', headers={'Authorization': 'Bearer wrong'})
        assert resp.status == 401
        assert resp.headers['WWW-Authenticate'] == 'Bearer'
        assert await _ws_status(client, {}) == 401

        good = {'Authorization': f'Bearer {TOKEN}'}
        assert (await client.get('/api/metrics', headers=good)).status == 200
        assert await _ws_status(client, good) == 101
        # Health stays open; preflight carries no credentials.
        assert (await client.get('/health')).status == 200
        assert (await client.options('/api/metrics')).status == 204
    finally:
        await client.close()


async def test_token_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv(dashboard_server.AUTH_TOKEN_ENV, TOKEN)
    client = await _client(tmp_path)
    try:
        assert (await client.get('/api/metrics')).status == 401
        good = {'Authorization': f'Bearer {TOKEN}'}
        assert (await client.get('/api/metrics', headers=good)).status == 200
    finally:
        await client.close()


def test_non_loopback_host_requires_token(tmp_path):
    with pytest.raises(ValueError, match='DASHBOARD_API_TOKEN'):
        DashboardServer(metrics_dir=tmp_path, host='0.0.0.0')
    DashboardServer(metrics_dir=tmp_path, host='0.0.0.0', auth_token=TOKEN)


@pytest.mark.parametrize('host', ['127.0.0.1', 'localhost', '::1', '[::1]', '127.0.0.2'])
def test_loopback_hosts(host):
    assert is_loopback_host(host)


@pytest.mark.parametrize('host', ['0.0.0.0', '::', '192.168.1.5', 'example.com', ''])
def test_non_loopback_hosts(host):
    assert not is_loopback_host(host)


def test_origin_allowed_is_case_and_slash_insensitive():
    assert is_origin_allowed('HTTP://LOCALHOST:3000')
    assert not is_origin_allowed('')
    assert not is_origin_allowed('http://localhost:3000.evil.example')
