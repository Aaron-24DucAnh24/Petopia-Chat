from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings

_redis: aioredis.Redis | None = None


async def connect() -> None:
  global _redis
  _redis = aioredis.from_url(settings.redis_url, decode_responses=True)


async def disconnect() -> None:
  if _redis:
    await _redis.aclose()


def get_redis() -> aioredis.Redis:
  if _redis is None:
    raise RuntimeError("Redis client not initialized")
  return _redis
