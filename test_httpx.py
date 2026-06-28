import asyncio
import httpx

async def main():
    client = httpx.AsyncClient()
    request = client.build_request("GET", "https://httpbin.org/get")
    response = await client.send(request, stream=True)
    print(response.status_code)
    async for chunk in response.aiter_bytes():
        print(len(chunk))
    await response.aclose()
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
