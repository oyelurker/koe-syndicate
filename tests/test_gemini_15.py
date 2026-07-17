import asyncio
import os
import sys
from google import genai

async def test():
    client = genai.Client()
    try:
        response = await client.aio.models.generate_content(
            model='gemini-1.5-flash',
            contents='Hello'
        )
        print("Success:", response.text)
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
