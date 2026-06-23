from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

_client: AsyncIOMotorClient | None = None


async def connect() -> None:
  global _client
  _client = AsyncIOMotorClient(settings.mongodb_url)


async def disconnect() -> None:
  if _client:
    _client.close()


def get_db() -> AsyncIOMotorDatabase:
  if _client is None:
    raise RuntimeError("MongoDB client not initialized")
  return _client[settings.mongodb_db_name]
