import asyncio
import json
import logging

import redis.asyncio as aioredis
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.auth import UserContextModel, decode_token
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
    user: UserContextModel = decode_token(token)
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

      elif event.type == WsEventType.conversation_opened:
        conversation_id = event.payload.get("conversation_id")
        if conversation_id:
          await _set_active_conversation(redis, user.Id, conversation_id)

      elif event.type == WsEventType.conversation_closed:
        conversation_id = event.payload.get("conversation_id")
        if conversation_id:
          await _clear_active_conversation(redis, user.Id, conversation_id)

  except WebSocketDisconnect:
    logger.info("WS disconnected: user=%s", user.Id)
  finally:
    redis_task.cancel()
    await _cleanup_active_conversation(redis, user.Id)


_ACTIVE_CONV_TTL = 3600  # seconds — safety-net TTL in case disconnect cleanup is missed


async def _set_active_conversation(
  redis: aioredis.Redis,
  user_id: str,
  conversation_id: str,
) -> None:
  """Mark user as actively viewing a conversation (prevents unread inserts)."""
  await redis.set(f"user_active_conv:{user_id}", conversation_id, ex=_ACTIVE_CONV_TTL)
  await redis.sadd(f"active_conv:{conversation_id}", user_id)
  await redis.expire(f"active_conv:{conversation_id}", _ACTIVE_CONV_TTL)


async def _clear_active_conversation(
  redis: aioredis.Redis,
  user_id: str,
  conversation_id: str,
) -> None:
  """Remove user from an active conversation set."""
  await redis.delete(f"user_active_conv:{user_id}")
  await redis.srem(f"active_conv:{conversation_id}", user_id)


async def _cleanup_active_conversation(redis: aioredis.Redis, user_id: str) -> None:
  """On WS disconnect: remove the user from whichever conversation they had open."""
  try:
    conv_id = await redis.get(f"user_active_conv:{user_id}")
    if conv_id:
      if isinstance(conv_id, bytes):
        conv_id = conv_id.decode()
      await redis.srem(f"active_conv:{conv_id}", user_id)
      await redis.delete(f"user_active_conv:{user_id}")
  except Exception as e:
    logger.warning("cleanup_active_conversation failed for user=%s: %s", user_id, e)


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
