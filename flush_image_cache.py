"""Delete all cached album art from Redis."""

import asyncio
import os

import redis.asyncio as aioredis
from dotenv import load_dotenv

load_dotenv()


async def main():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    r = aioredis.from_url(redis_url)
    deleted = (
        await r.delete(*await r.keys("img:v1:*")) if await r.keys("img:v1:*") else 0
    )
    print(f"Deleted {deleted} cached image(s)")
    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
