import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path('./src').resolve()))

from rig_tools.ui_server import UIServer
from aiohttp import web
from playwright.async_api import async_playwright

async def run_server():
    repo_root = Path('.').resolve()
    server = UIServer(repo_root=repo_root, session_token="debug_token")
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 65372)
    await site.start()
    return runner

async def main():
    print("Starting UI Server on http://127.0.0.1:65372...")
    runner = await run_server()
    
    print("Launching browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Capture all console messages
        page.on("console", lambda msg: print(f"BROWSER_LOG: {msg.text}"))
        page.on("pageerror", lambda err: print(f"BROWSER_ERROR: {err}"))
        
        url = "http://127.0.0.1:65372/?rig_session=debug_token"
        print(f"Navigating to {url}...")
        
        try:
            await page.goto(url, wait_until="networkidle")
            print("Page loaded (networkidle). Waiting for boot transition...")
            
            # Wait for up to 10 seconds for the transition to happen
            for _ in range(10):
                await asyncio.sleep(1)
                app_hidden = await page.evaluate("document.getElementById('app')?.hidden")
                fallback_hidden = await page.evaluate("document.getElementById('boot-fallback')?.hidden")
                print(f"State check: app.hidden={app_hidden}, fallback.hidden={fallback_hidden}")
                if app_hidden is False:
                    print("SUCCESS: UI transitioned!")
                    break
            else:
                print("FAILURE: UI stuck in boot state.")
                
        except Exception as e:
            print(f"Test failed: {e}")
        finally:
            await browser.close()
            await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
