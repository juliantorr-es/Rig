import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright
import subprocess
import time

# Add src to path
sys.path.insert(0, str(Path("./src").resolve()))

from rig_tools.ui_server import RigUIServer

async def run_repro():
    repo_root = Path(".").resolve()
    token = "repro-token"
    server = RigUIServer(repo_root=repo_root, host="127.0.0.1", port=0, session_token=token)
    
    port = await server.start()
    url = f"http://127.0.0.1:{port}/?rig_session={token}"
    print(f"Server started at {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Capture console logs
        page.on("console", lambda msg: print(f"[BROWSER CONSOLE] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"[BROWSER ERROR] {err}"))
        page.on("requestfailed", lambda req: print(f"[BROWSER REQUEST FAILED] {req.url}: {req.failure.error_text}"))

        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="networkidle")
        
        print("Waiting 5 seconds for boot sequence...")
        await asyncio.sleep(5)
        
        # Check elements
        app_hidden = await page.evaluate("document.getElementById('app').hidden")
        fallback_hidden = await page.evaluate("document.getElementById('boot-fallback').hidden")
        print(f"App element hidden: {app_hidden}")
        print(f"Fallback element hidden: {fallback_hidden}")
        
        await browser.close()
    
    await server.stop()

if __name__ == "__main__":
    asyncio.run(run_repro())
