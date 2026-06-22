import asyncio
from playwright.async_api import async_playwright

async def main():
    mirror_url = "https://annas-archive.gl/slow_download/10ef67e100dd6296114668db5b7b6b61/0/2"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        )
        page = await context.new_page()
        try:
            print(f"Navigating to: {mirror_url}")
            await page.goto(mirror_url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait 5 seconds to let any redirect or lazy loading happen
            await asyncio.sleep(5)

            title = await page.title()
            print(f"Page title: {title}")

            content = await page.content()
            print(f"Content length: {len(content)}")
            
            # Let's search for "slow_download" or standard download keywords in the HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")
            print("All link tags in the page:")
            for a in soup.find_all("a", href=True):
                print(f"Href: {a['href']}, Text: {a.get_text(strip=True)}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
