from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.constants import CONVERSATIONS_COLLECTION, UNREAD_MESSAGES_COLLECTION
from app.core.exceptions import bad_request, forbidden, not_found
from app.models.conversation import (
  ConversationCreate,
  ConversationListResponse,
  ConversationResponse,
  ConversationType,
  LastMessagePreview,
)


def _doc_to_response(doc: dict) -> ConversationResponse:
  lmp = doc.get("last_message_preview")
  return ConversationResponse(
    id=str(doc["_id"]),
    type=doc["type"],
    participants=doc["participants"],
    name=doc.get("name"),
    avatar_url=doc.get("avatar_url"),
    created_by=doc["created_by"],
    created_at=doc["created_at"],
    updated_at=doc["updated_at"],
    last_message_preview=LastMessagePreview(**lmp) if lmp else None,
    unread_count=doc.get("unread_count", 0),
  )


class ConversationService:
  def __init__(self, db: AsyncIOMotorDatabase) -> None:
    self.db = db
    self.collection = db[CONVERSATIONS_COLLECTION]
    self.unread = db[UNREAD_MESSAGES_COLLECTION]

  async def list_conversations(
    self, user_id: str, cursor: str | None, limit: int
  ) -> ConversationListResponse:
    query: dict = {"participants": user_id}

    if cursor:
      try:
        raw_dt, raw_id = cursor.split("|", 1)
        cursor_dt = datetime.fromisoformat(raw_dt)
        cursor_oid = ObjectId(raw_id)
        query["$or"] = [
          {"updated_at": {"$lt": cursor_dt}},
          {"updated_at": cursor_dt, "_id": {"$lt": cursor_oid}},
        ]
      except Exception:
        raise bad_request("Invalid cursor")

    docs = (
      await self.collection.find(query)
      .sort([("updated_at", -1), ("_id", -1)])
      .limit(limit + 1)
      .to_list(limit + 1)
    )

    has_more = len(docs) > limit
    items = docs[:limit]
    next_cursor = (
      f"{items[-1]['updated_at'].isoformat()}|{items[-1]['_id']}"
      if has_more and items
      else None
    )

    if items:
      conversation_ids = [str(d["_id"]) for d in items]
      pipeline = [
        {"$match": {"user_id": user_id, "conversation_id": {"$in": conversation_ids}}},
        {"$group": {"_id": "$conversation_id", "count": {"$sum": 1}}},
      ]
      unread_map: dict[str, int] = {}
      async for bucket in self.unread.aggregate(pipeline):
        unread_map[bucket["_id"]] = bucket["count"]
      for d in items:
        d["unread_count"] = unread_map.get(str(d["_id"]), 0)

    return ConversationListResponse(
      items=[_doc_to_response(d) for d in items],
      next_cursor=next_cursor,
    )

  async def create_conversation(
    self, payload: ConversationCreate, created_by: str
  ) -> ConversationResponse:
    participants = list(payload.participants)
    if created_by not in participants:
      participants.append(created_by)

    if payload.type == ConversationType.direct:
      if len(participants) != 2:
        raise bad_request("Direct conversations must have exactly 2 participants")

      participants_key = "|".join(sorted(participants))
      existing = await self.collection.find_one({"participants_key": participants_key})
      if existing:
        return _doc_to_response(existing)

    elif payload.type == ConversationType.group:
      if not payload.name:
        raise bad_request("Group conversations require a name")
      if len(participants) < 2:
        raise bad_request("Group conversations require at least 2 participants")

    now = datetime.now(timezone.utc)
    is_direct = payload.type == ConversationType.direct
    doc: dict = {
      "type": payload.type,
      "participants": sorted(participants) if is_direct else participants,
      "participants_key": "|".join(sorted(participants)) if is_direct else None,
      "name": payload.name,
      "avatar_url": payload.avatar_url,
      "created_by": created_by,
      "created_at": now,
      "updated_at": now,
      "last_message_preview": None,
    }
    result = await self.collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_response(doc)

  async def get_conversation(
    self, conversation_id: str, user_id: str
  ) -> ConversationResponse:
    try:
      oid = ObjectId(conversation_id)
    except Exception:
      raise not_found("Conversation")

    doc = await self.collection.find_one({"_id": oid})
    if not doc:
      raise not_found("Conversation")
    if user_id not in doc["participants"]:
      raise forbidden()

    return _doc_to_response(doc)
