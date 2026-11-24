"""Regression tests: dashboard.html must not execute markup from API or WebSocket data.

Agent names and event fields come from .agent_metrics.json via /api/metrics and the
/ws metrics_update message. The page renders them with innerHTML templates, so any
value that is not escaped runs as HTML in the dashboard origin.
"""

import json
from pathlib import Path
from urllib.parse import unquote

import pytest
from playwright.async_api import async_playwright

DASHBOARD_URL = f"file://{(Path(__file__).parent.parent / 'dashboard.html').absolute()}"

# Each payload sets window.__xss when it executes. The quote-breaking one targets the
# old inline onclick="viewAgentDetails('${name}')" handler.
IMG_PAYLOAD = '<img src=x onerror="window.__xss=(window.__xss||0)+1">'
QUOTE_PAYLOAD = "x');window.__xss=(window.__xss||0)+1;('"
EVENT_TYPE_PAYLOAD = '<svg onload="window.__xss=(window.__xss||0)+1">'


def _agent(name: str) -> dict:
    return {
        "agent_name": name,
        "total_invocations": 3,
        "successful_invocations": 2,
        "failed_invocations": 1,
        "total_cost_usd": 0.5,
        "success_rate": 0.66,
        "avg_duration_seconds": 4.0,
        "xp": IMG_PAYLOAD,
        "level": IMG_PAYLOAD,
        "current_streak": 1,
        "files_modified": 0,
        "tests_written": 0,
    }


def _metrics() -> dict:
    return {
        "total_sessions": IMG_PAYLOAD,
        "total_tokens": 10,
        "total_cost_usd": 0.5,
        "agents": {IMG_PAYLOAD: _agent(IMG_PAYLOAD), QUOTE_PAYLOAD: _agent(QUOTE_PAYLOAD)},
        "events": [
            {
                "agent_name": IMG_PAYLOAD,
                "event_type": EVENT_TYPE_PAYLOAD,
                "description": IMG_PAYLOAD,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
    }


async def _open(p, *, via_websocket: bool):
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    detail_urls: list[str] = []
    body = json.dumps(_metrics())

    async def handle_api(route):
        url = route.request.url
        if "/api/metrics" in url and not via_websocket:
            await route.fulfill(status=200, content_type="application/json", body=body)
        elif "/api/agents/" in url:
            detail_urls.append(url)
            await route.fulfill(status=200, content_type="application/json", body="{}")
        else:
            await route.abort()

    def handle_ws(ws):
        if via_websocket:
            ws.send(json.dumps({"type": "metrics_update", "data": _metrics()}))

    await page.route("http://localhost:8080/**", handle_api)
    await page.route_web_socket("ws://localhost:8080/**", handle_ws)
    # Chart.js comes from a CDN; tests must not depend on the network.
    await page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    page.on("dialog", lambda dialog: dialog.accept())
    await page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
    await page.wait_for_selector(".task-card[data-agent]", timeout=10000)
    await page.wait_for_timeout(300)  # let any injected onerror/onload fire
    return browser, page, detail_urls


@pytest.mark.asyncio
@pytest.mark.parametrize("via_websocket", [False, True], ids=["rest", "websocket"])
async def test_hostile_agent_and_event_data_is_rendered_as_text(via_websocket):
    async with async_playwright() as p:
        browser, page, _ = await _open(p, via_websocket=via_websocket)
        try:
            assert await page.evaluate("window.__xss") is None
            # No element was created from the payloads.
            assert await page.locator("#agent-cards img, #activity-feed img").count() == 0
            assert await page.locator("#activity-feed svg[onload]").count() == 0
            assert await page.locator("#stats-grid img").count() == 0
            assert await page.locator("[onclick]").count() == 0
            # The names show up literally instead.
            titles = await page.locator("#agent-cards .card-title").all_text_contents()
            assert any(IMG_PAYLOAD in t for t in titles)
            assert any(QUOTE_PAYLOAD in t for t in titles)
            feed = await page.locator("#activity-feed").text_content()
            assert IMG_PAYLOAD in feed and EVENT_TYPE_PAYLOAD in feed
        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_clicking_hostile_agent_card_runs_no_script_and_encodes_url():
    async with async_playwright() as p:
        browser, page, detail_urls = await _open(p, via_websocket=False)
        try:
            for name in (QUOTE_PAYLOAD, IMG_PAYLOAD):
                card = page.locator(".task-card").filter(
                    has=page.locator(".card-title", has_text=name)
                )
                assert await card.get_attribute("data-agent") == name
                await card.click()
            await page.wait_for_timeout(300)
            assert await page.evaluate("window.__xss") is None
            # Each name is one encoded path segment that decodes back to the name.
            requested = []
            for url in detail_urls:
                segment, query = url.split("/api/agents/", 1)[1].split("?", 1)
                assert "/" not in segment and "<" not in segment and query == "include_events"
                requested.append(unquote(segment))
            assert requested == [QUOTE_PAYLOAD, IMG_PAYLOAD]
        finally:
            await browser.close()
