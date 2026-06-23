import pymongo
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.constants import CONVERSATIONS_COLLECTION, MESSAGES_COLLECTION


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
  conversations = db[CONVERSATIONS_COLLECTION]
  await conversations.create_index([("participants", pymongo.ASCENDING)])
  await conversations.create_index(
    [("updated_at", pymongo.DESCENDING), ("_id", pymongo.DESCENDING)]
  )
  # Enforces uniqueness for direct conversations at the DB level (prevents TOCTOU duplicates)
  await conversations.create_index(
    [("participants_key", pymongo.ASCENDING)],
    unique=True,
    sparse=True,
  )

  messages = db[MESSAGES_COLLECTION]
  await messages.create_index(
    [("conversation_id", pymongo.ASCENDING), ("sent_at", pymongo.DESCENDING)]
  )
  await messages.create_index([("sender_id", pymongo.ASCENDING)])
  await messages.create_index(
    [("reply_to.message_id", pymongo.ASCENDING)], sparse=True
  )
