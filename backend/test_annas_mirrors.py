import asyncio
from playwright.async_api import async_playwright

domains = [
    "https://annas-archive.org",
    "https://annas-archive.se",
    "https://annas-archive.li",
    "https://annas-archive.gl"
]

async def test_domain(url: str):
    print(f"\nTesting: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        )
        page = await context.new_page()
        try:
            response = await page.goto(f"{url}/search?q=The+Alchemist", wait_until="domcontentloaded", timeout=15000)
            status = response.status if response else "No response"
            title = await page.title()
            content = await page.content()
            print(f"Status: {status}, Title: '{title}', Content Length: {len(content)}")
            if "ddos-guard" in title.lower() or "ddos-guard" in content.lower():
                print("Result: BLOCKED by DDoS-Guard")
            elif "cloudflare" in title.lower() or "cloudflare" in content.lower():
                print("Result: BLOCKED by Cloudflare")
            else:
                print("Result: SUCCESS (No blocks detected)")
        except Exception as e:
            print(f"Failed with exception: {e}")
        finally:
            await browser.close()

async def main():
    for domain in domains:
        await test_domain(domain)

if __name__ == "__main__":
    asyncio.run(main())
