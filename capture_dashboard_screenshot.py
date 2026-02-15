#!/usr/bin/env python3
"""Capture screenshot of dashboard with live data.

This script:
1. Starts the dashboard server
2. Opens the dashboard in a browser
3. Waits for data to load
4. Captures a screenshot
5. Stops the server
"""

import asyncio
import subprocess
import time
from pathlib import Path
from playwright.async_api import async_playwright


async def capture_screenshot():
    """Capture dashboard screenshot with live data."""
    # Start the dashboard server
    print("Starting dashboard server...")
    server_process = subprocess.Popen(
        ['python', 'dashboard_server.py', '--port', '8080'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    await asyncio.sleep(3)

    try:
        # Launch browser
        print("Launching browser...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            # Navigate to dashboard
            print("Loading dashboard...")
            dashboard_path = Path(__file__).parent / 'dashboard.html'
            dashboard_url = f'file://{dashboard_path.absolute()}'

            await page.goto(dashboard_url, wait_until='networkidle', timeout=10000)

            # Wait for data to load
            print("Waiting for data to load...")
            await asyncio.sleep(5)

            # Capture screenshot
            screenshot_path = Path(__file__).parent / 'evidence' / 'dashboard_with_data.png'
            screenshot_path.parent.mkdir(exist_ok=True)

            print(f"Capturing screenshot to {screenshot_path}...")
            await page.screenshot(path=str(screenshot_path), full_page=True)

            print(f"Screenshot saved: {screenshot_path}")
            print(f"Screenshot size: {screenshot_path.stat().st_size / 1024:.1f} KB")

            # Also capture viewport screenshot
            viewport_path = Path(__file__).parent / 'evidence' / 'dashboard_viewport.png'
            await page.screenshot(path=str(viewport_path), full_page=False)
            print(f"Viewport screenshot saved: {viewport_path}")

            await browser.close()

    finally:
        # Stop the server
        print("Stopping server...")
        server_process.terminate()
        server_process.wait(timeout=5)
        print("Done!")


if __name__ == '__main__':
    asyncio.run(capture_screenshot())
