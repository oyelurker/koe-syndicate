import httpx
import asyncio

async def main():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post('http://127.0.0.1:8081/a2a', json={"data": "test"})
            print(resp.status_code, resp.text)
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
