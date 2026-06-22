import asyncio
from playwright.async_api import async_playwright

async def main():
    detail_url = "https://annas-archive.org/md5/10ef67e100dd6296114668db5b7b6b61"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        )
        page = await context.new_page()
        try:
            print(f"Navigating to: {detail_url}")
            await page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait a few seconds
            await asyncio.sleep(3)

            title = await page.title()
            print(f"Page title: {title}")

            content = await page.content()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")
            
            # Print all links that contain download or mirror information
            print("\nFound links:")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if any(x in href.lower() or x in text.lower() for x in ["download", "mirror", "libgen", "ipfs", "slow", "fast"]):
                    print(f"Href: {href} | Text: {text}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
