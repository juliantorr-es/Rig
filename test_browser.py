import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Add an error listener to capture console errors
        page.on("console", lambda msg: print(f"Browser Console {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Browser Error: {err}"))
        
        # Navigate to the UI
        print("Navigating to http://localhost:65372...")
        try:
            await page.goto("http://localhost:65372", wait_until="networkidle")
        except Exception as e:
            print(f"Failed to navigate: {e}")
            
        print("Waiting for boot fallback to disappear...")
        try:
            # We want to see if the fallback goes away or stays
            await page.wait_for_timeout(3000)
            app_hidden = await page.evaluate("document.getElementById('app').hidden")
            print(f"App is hidden: {app_hidden}")
            fallback_hidden = await page.evaluate("document.getElementById('boot-fallback').hidden")
            print(f"Fallback is hidden: {fallback_hidden}")
        except Exception as e:
            print(f"Error checking state: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
