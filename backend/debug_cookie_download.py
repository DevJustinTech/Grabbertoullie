import asyncio
from playwright.async_api import async_playwright

async def main():
    detail_url = "https://z-lib.sk/book/YzLZwAPL5l/the-alchemist.html"
    download_url = "https://z-lib.sk/dl/gmey9YZ7pm"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        try:
            print(f"1. Navigating to detail page: {detail_url}")
            await page.goto(detail_url, wait_until="domcontentloaded", timeout=15000)
            
            # Print page title to check if we loaded it successfully
            title = await page.title()
            print(f"Detail page title: {title}")

            # Get cookies
            cookies = await context.cookies()
            print(f"Cookies after detail page: {len(cookies)}")

            print(f"2. Navigating to download URL: {download_url}")
            async with page.expect_download(timeout=15000) as download_info:
                try:
                    await page.goto(download_url, wait_until="domcontentloaded", timeout=10000)
                except Exception as e:
                    print(f"Goto exception (may be expected): {e}")
            
            download = await download_info.value
            print(f"Download triggered successfully! Filename: {download.suggested_filename}")
            await download.cancel()
            print("Validation result: True")
        except Exception as e:
            print(f"Error during validation: {e}")
            # Get HTML content of the page when it failed
            try:
                content = await page.content()
                print(f"Page content preview (first 500 chars):\n{content[:500]}")
            except Exception:
                pass
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
