from __future__ import annotations

from datetime import datetime, timezone

import redis.asyncio as aioredis
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.constants import (
  CONVERSATIONS_COLLECTION,
  MESSAGES_COLLECTION,
  REDIS_CHAT_CHANNEL_PREFIX,
  REPLY_PREVIEW_MAX_LENGTH,
  UNREAD_MESSAGES_COLLECTION,
)
from app.core.exceptions import bad_request, forbidden, not_found
from app.models.message import (
  MessageCreate,
  MessageListResponse,
  MessageResponse,
  MessageType,
  ReplyPreview,
  WsEvent,
  WsEventType,
)


def _doc_to_response(doc: dict) -> MessageResponse:
  rt = doc.get("reply_to")
  reply_to = (
    ReplyPreview(
      message_id=rt["message_id"],
      sender_id=rt["sender_id"],
      content_preview=rt["content_preview"],
    )
    if rt
    else None
  )
  return MessageResponse(
    id=str(doc["_id"]),
    conversation_id=str(doc["conversation_id"]),
    sender_id=doc["sender_id"],
    content=doc.get("content"),
    message_type=doc["message_type"],
    media_url=doc.get("media_url"),
    sent_at=doc["sent_at"],
    read_by=doc.get("read_by", []),
    reply_to=reply_to,
    reactions=doc.get("reactions", {}),
    is_deleted=doc.get("is_deleted", False),
  )


class MessageService:
  def __init__(self, db: AsyncIOMotorDatabase, redis: aioredis.Redis) -> None:
    self.db = db
    self.redis = redis
    self.collection = db[MESSAGES_COLLECTION]
    self.conversations = db[CONVERSATIONS_COLLECTION]
    self.unread = db[UNREAD_MESSAGES_COLLECTION]

  # ------------------------------------------------------------------
  # Helpers
  # ------------------------------------------------------------------

  async def _require_participant(self, conversation_id: str, user_id: str) -> dict:
    try:
      oid = ObjectId(conversation_id)
    except Exception:
      raise not_found("Conversation")
    doc = await self.conversations.find_one({"_id": oid})
    if not doc:
      raise not_found("Conversation")
    if user_id not in doc["participants"]:
      raise forbidden()
    return doc

  async def _get_message(self, message_id: str) -> dict:
    try:
      oid = ObjectId(message_id)
    except Exception:
      raise not_found("Message")
    doc = await self.collection.find_one({"_id": oid})
    if not doc:
      raise not_found("Message")
    return doc

  async def _publish(self, user_ids: list[str], event: WsEvent) -> None:
    data = event.model_dump_json()
    for uid in user_ids:
      await self.redis.publish(f"{REDIS_CHAT_CHANNEL_PREFIX}{uid}", data)

  # ------------------------------------------------------------------
  # Public methods
  # ------------------------------------------------------------------

  async def list_messages(
    self, conversation_id: str, user_id: str, cursor: str | None, limit: int
  ) -> MessageListResponse:
    await self._require_participant(conversation_id, user_id)

    query: dict = {
      "conversation_id": ObjectId(conversation_id),
      "is_deleted": False,
    }
    if cursor:
      try:
        query["_id"] = {"$lt": ObjectId(cursor)}
      except Exception:
        raise bad_request("Invalid cursor")

    docs = (
      await self.collection.find(query)
      .sort("sent_at", -1)
      .limit(limit + 1)
      .to_list(limit + 1)
    )

    has_more = len(docs) > limit
    items = docs[:limit]
    next_cursor = str(items[-1]["_id"]) if has_more and items else None

    return MessageListResponse(
      items=[_doc_to_response(d) for d in items],
      next_cursor=next_cursor,
    )

  async def send_message(
    self, conversation_id: str, payload: MessageCreate, sender_id: str
  ) -> MessageResponse:
    conv = await self._require_participant(conversation_id, sender_id)

    if payload.message_type == MessageType.text and not payload.content:
      raise bad_request("Text messages must have content")

    reply_to_doc: dict | None = None
    if payload.reply_to_id:
      original = await self._get_message(payload.reply_to_id)
      if str(original["conversation_id"]) != conversation_id:
        raise bad_request("reply_to message belongs to a different conversation")
      reply_to_doc = {
        "message_id": payload.reply_to_id,
        "sender_id": original["sender_id"],
        "content_preview": (original.get("content") or "")[:REPLY_PREVIEW_MAX_LENGTH],
      }

    now = datetime.now(timezone.utc)
    doc: dict = {
      "conversation_id": ObjectId(conversation_id),
      "sender_id": sender_id,
      "content": payload.content,
      "message_type": payload.message_type,
      "media_url": payload.media_url,
      "sent_at": now,
      "read_by": [sender_id],
      "reply_to": reply_to_doc,
      "reactions": {},
      "is_deleted": False,
      "deleted_at": None,
    }
    result = await self.collection.insert_one(doc)
    doc["_id"] = result.inserted_id

    await self.conversations.update_one(
      {"_id": ObjectId(conversation_id)},
      {
        "$set": {
          "updated_at": now,
          "last_message_preview": {
            "content": payload.content,
            "sender_id": sender_id,
            "sent_at": now,
            "message_type": payload.message_type,
          },
        }
      },
    )

    response = _doc_to_response(doc)
    recipients = [uid for uid in conv["participants"] if uid != sender_id]

    # Upsert an unread marker for recipients who don't have this conversation open
    if recipients:
      active_users: set = await self.redis.smembers(f"active_conv:{conversation_id}")
      # smembers may return bytes; decode for comparison
      active_str = {u.decode() if isinstance(u, bytes) else u for u in active_users}
      for uid in recipients:
        if uid not in active_str:
          await self.unread.update_one(
            {"user_id": uid, "conversation_id": conversation_id},
            {"$setOnInsert": {"user_id": uid, "conversation_id": conversation_id}},
            upsert=True,
          )

    await self._publish(
      recipients,
      WsEvent(type=WsEventType.new_message, payload=response.model_dump(mode="json")),
    )
    return response

  async def delete_message(self, message_id: str, user_id: str) -> None:
    doc = await self._get_message(message_id)
    if doc["sender_id"] != user_id:
      raise forbidden("Only the sender can delete a message")
    if doc.get("is_deleted"):
      return  # idempotent

    now = datetime.now(timezone.utc)
    await self.collection.update_one(
      {"_id": ObjectId(message_id)},
      {"$set": {"is_deleted": True, "deleted_at": now}},
    )

    conv = await self.conversations.find_one({"_id": doc["conversation_id"]})
    if conv:
      await self._publish(
        conv["participants"],
        WsEvent(
          type=WsEventType.message_deleted,
          payload={
            "message_id": message_id,
            "conversation_id": str(doc["conversation_id"]),
          },
        ),
      )

  async def toggle_reaction(
    self, message_id: str, user_id: str, emoji: str
  ) -> MessageResponse:
    doc = await self._get_message(message_id)
    if doc.get("is_deleted"):
      raise bad_request("Cannot react to a deleted message")

    conv = await self.conversations.find_one({"_id": doc["conversation_id"]})
    if not conv or user_id not in conv["participants"]:
      raise forbidden()

    reactions: dict[str, list[str]] = doc.get("reactions", {})
    users = reactions.get(emoji, [])

    if user_id in users:
      users.remove(user_id)
    else:
      users.append(user_id)

    if users:
      reactions[emoji] = users
    else:
      reactions.pop(emoji, None)

    await self.collection.update_one(
      {"_id": ObjectId(message_id)}, {"$set": {"reactions": reactions}}
    )
    doc["reactions"] = reactions
    response = _doc_to_response(doc)

    await self._publish(
      conv["participants"],
      WsEvent(
        type=WsEventType.reaction_updated,
        payload=response.model_dump(mode="json"),
      ),
    )
    return response

  async def mark_read(self, conversation_id: str, user_id: str) -> None:
    await self._require_participant(conversation_id, user_id)

    await self.collection.update_many(
      {
        "conversation_id": ObjectId(conversation_id),
        "read_by": {"$ne": user_id},
        "is_deleted": False,
      },
      {"$addToSet": {"read_by": user_id}},
    )

    # Clear unread tracking for this user+conversation
    await self.unread.delete_many({"user_id": user_id, "conversation_id": conversation_id})

    # Notify distinct senders (other than the reader) about the read receipt
    senders: list[str] = await self.collection.distinct(
      "sender_id",
      {
        "conversation_id": ObjectId(conversation_id),
        "sender_id": {"$ne": user_id},
      },
    )
    if senders:
      await self._publish(
        senders,
        WsEvent(
          type=WsEventType.messages_read,
          payload={"conversation_id": conversation_id, "read_by": user_id},
        ),
      )
