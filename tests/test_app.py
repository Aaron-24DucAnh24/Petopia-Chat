import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import mongodb, redis as redis_module
from app.main import app


@pytest_asyncio.fixture
async def db():
  await mongodb.connect()
  yield mongodb.get_db()
  await mongodb.disconnect()


@pytest_asyncio.fixture
async def redis():
  await redis_module.connect()
  yield redis_module.get_redis()
  await redis_module.disconnect()


async def test_health_endpoint():
  async with AsyncClient(
    transport=ASGITransport(app=app), base_url="http://test"
  ) as client:
    response = await client.get("/health")
  assert response.status_code == 200
  assert response.json() == {"status": "ok"}


async def test_redis_connected(redis):
  assert await redis.ping() is True


async def test_mongodb_connected(db):
  result = await db.command("ping")
  assert result.get("ok") == 1.0
