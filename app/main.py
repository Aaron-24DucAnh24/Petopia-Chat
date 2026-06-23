from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import mongodb, redis
from app.db.indexes import create_indexes
from app.routers import conversations, messages, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
  await mongodb.connect()
  await redis.connect()
  await create_indexes(mongodb.get_db())
  yield
  await mongodb.disconnect()
  await redis.disconnect()


app = FastAPI(
  title="Petopia Chat Service",
  version="0.1.0",
  lifespan=lifespan,
)

app.include_router(conversations.router)
app.include_router(messages.router)
app.include_router(ws.router)


@app.get("/health", tags=["Health"])
async def health() -> dict:
  return {"status": "ok"}
