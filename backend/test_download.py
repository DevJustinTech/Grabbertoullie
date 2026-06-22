import asyncio
import httpx

async def main():
    url = "https://z-lib.sk/dl/gmey9YZ7pm"
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            print(f"Sending GET to {url}...")
            resp = await client.get(url, headers=headers, timeout=15.0)
            print(f"Status Code: {resp.status_code}")
            print(f"Headers: {dict(resp.headers)}")
            print(f"Content Length: {len(resp.content)}")
            # Show first 100 bytes
            print(f"Content Preview: {resp.content[:100]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
