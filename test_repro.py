import asyncio
import subprocess
import time
import os
import signal
from playwright.async_api import async_playwright

async def run_test():
    # Start the rig ui server
    # We use a fixed port and browser mode to avoid pywebview popup
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    
    print("Starting Rig UI server...")
    proc = subprocess.Popen(
        ["python3", "-m", "rig", "ui", "--port", "65372", "--browser"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=os.setsid
    )
    
    # Wait for server to start and get the URL
    url = ""
    for _ in range(30):
        line = proc.stdout.readline()
        if line:
            print(f"Server: {line.strip()}")
            if "http://" in line:
                # Extract URL - expected format: UI Server started at http://127.0.0.1:65372/?rig_session=...
                # or similar
                parts = line.split("at ")
                if len(parts) > 1:
                    url = parts[1].strip()
                    break
        await asyncio.sleep(0.5)
        
    if not url:
        print("Failed to find server URL")
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        return

    print(f"Target URL: {url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Capture all logs
        page.on("console", lambda msg: print(f"BROWSER CONSOLE {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"BROWSER ERROR: {err}"))
        
        print("Navigating...")
        await page.goto(url, wait_until="networkidle")
        
        print("Waiting 10 seconds for UI to boot and logs to appear...")
        await asyncio.sleep(10)
        
        # Take a screenshot to verify what's on screen
        await page.screenshot(path="debug_ui.png")
        print("Screenshot saved to debug_ui.png")
        
        await browser.close()

    print("Cleaning up...")
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)

if __name__ == "__main__":
    asyncio.run(run_test())
