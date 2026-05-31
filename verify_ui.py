import time
from playwright.sync_api import sync_playwright

def verify():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(record_video_dir="/home/jules/verification/videos")
        page = context.new_page()

        print("Navigating to http://localhost:3001")
        # Give the dev server a moment to spin up
        time.sleep(3)
        page.goto("http://localhost:3001")

        # Wait for input
        page.wait_for_selector("input[type='text']")

        # Test input text
        page.fill("input[type='text']", "grab The Alchemist pdf")

        # Trigger send
        page.click("button[type='submit']")

        # Take a screenshot to show the UI
        print("Taking screenshot...")
        page.screenshot(path="/home/jules/verification/screenshots/screenshot.png")

        print("Done.")
        context.close()
        browser.close()

if __name__ == "__main__":
    verify()
