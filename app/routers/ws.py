import asyncio
import json
import logging

import redis.asyncio as aioredis
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.auth import TokenPayload, decode_token
from app.core.constants import (
  CONVERSATIONS_COLLECTION,
  REDIS_CHAT_CHANNEL_PREFIX,
  WS_CLOSE_UNAUTHORIZED,
)
from app.db.mongodb import get_db
from app.db.redis import get_redis
from app.models.message import WsEvent, WsEventType
from app.services.message_service import MessageService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


async def _subscribe_and_forward(
  websocket: WebSocket,
  user_id: str,
  redis: aioredis.Redis,
) -> None:
  """Pull events from the user's Redis Pub/Sub channel and forward to the socket."""
  channel = f"{REDIS_CHAT_CHANNEL_PREFIX}{user_id}"
  pubsub = redis.pubsub()
  await pubsub.subscribe(channel)
  try:
    async for raw in pubsub.listen():
      if raw["type"] != "message":
        continue
      await websocket.send_text(raw["data"])
  finally:
    await pubsub.unsubscribe(channel)
    await pubsub.aclose()


@router.websocket("/ws")
async def websocket_endpoint(
  websocket: WebSocket,
  token: str,
  db: AsyncIOMotorDatabase = Depends(get_db),
  redis: aioredis.Redis = Depends(get_redis),
) -> None:
  """
  Connect with ?token=<access_token>.

  Incoming client frame format:
    {"type": "user_typing",   "payload": {"conversation_id": "<id>"}}
    {"type": "messages_read", "payload": {"conversation_id": "<id>"}}

  Outgoing server event format: WsEvent JSON
  """
  try:
    user: TokenPayload = decode_token(token)
  except HTTPException:
    await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Unauthorized")
    return

  await websocket.accept()
  logger.info("WS connected: user=%s", user.Id)

  service = MessageService(db, redis)
  redis_task = asyncio.create_task(_subscribe_and_forward(websocket, user.Id, redis))

  try:
    while True:
      raw = await websocket.receive_text()
      try:
        event = WsEvent.model_validate_json(raw)
      except Exception:
        await websocket.send_text(json.dumps({"error": "Invalid event format"}))
        continue

      if event.type == WsEventType.user_typing:
        conversation_id = event.payload.get("conversation_id")
        if conversation_id:
          await _handle_typing(db, redis, conversation_id, user.Id)

      elif event.type == WsEventType.messages_read:
        conversation_id = event.payload.get("conversation_id")
        if conversation_id:
          try:
            await service.mark_read(conversation_id, user.Id)
          except Exception as e:
            logger.warning("mark_read failed for user=%s conv=%s: %s", user.Id, conversation_id, e)

  except WebSocketDisconnect:
    logger.info("WS disconnected: user=%s", user.Id)
  finally:
    redis_task.cancel()


async def _handle_typing(
  db: AsyncIOMotorDatabase,
  redis: aioredis.Redis,
  conversation_id: str,
  user_id: str,
) -> None:
  """Fan out a typing indicator to the other participants in the conversation."""
  try:
    conv = await db[CONVERSATIONS_COLLECTION].find_one(
      {"_id": ObjectId(conversation_id), "participants": user_id}
    )
  except Exception:
    return
  if not conv:
    return

  typing_event = WsEvent(
    type=WsEventType.user_typing,
    payload={"conversation_id": conversation_id, "user_id": user_id},
  )
  data = typing_event.model_dump_json()
  for uid in conv["participants"]:
    if uid != user_id:
      await redis.publish(f"{REDIS_CHAT_CHANNEL_PREFIX}{uid}", data)
