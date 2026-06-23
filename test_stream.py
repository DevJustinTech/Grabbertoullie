import asyncio
import httpx

async def main():
    client = httpx.AsyncClient(follow_redirects=True)
    req = client.build_request("GET", "https://httpbin.org/bytes/1024")
    response = await client.send(req, stream=True)

    async def stream_generator():
        try:
            async for chunk in response.aiter_bytes():
                print("Yielded chunk length:", len(chunk))
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()
            print("Cleaned up!")

    gen = stream_generator()
    async for c in gen:
        pass

asyncio.run(main())
