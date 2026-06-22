import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("debug_validation")

async def _validate_zlib_url(url: str) -> bool:
    try:
        async with async_playwright() as p:
            print("Launching browser...")
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            try:
                print(f"Expecting download for URL: {url}")
                async with page.expect_download(timeout=15000) as download_info:
                    try:
                        print("Navigating...")
                        response = await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                        print(f"Navigation status: {response.status if response else 'No Response'}")
                    except Exception as e:
                        print(f"Goto exception (expected if download starts immediately): {e}")
                print("Waiting for download value...")
                download = await download_info.value
                print(f"Download started: {download.url}")
                await download.cancel()
                return True
            except Exception as e:
                print(f"Playwright validation failed: {e}")
                return False
            finally:
                await browser.close()
    except Exception as e:
        print(f"Playwright setup failed: {e}")
        return False

async def main():
    url = "https://z-lib.sk/dl/gmey9YZ7pm"
    res = await _validate_zlib_url(url)
    print(f"Validation result: {res}")

if __name__ == "__main__":
    asyncio.run(main())
