from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class MessageType(str, Enum):
  text = "text"
  image = "image"
  file = "file"


class ReplyPreview(BaseModel):
  message_id: str
  sender_id: str
  content_preview: str


class MessageCreate(BaseModel):
  content: str | None = None
  message_type: MessageType = MessageType.text
  media_url: str | None = None
  reply_to_id: str | None = None


class MessageResponse(BaseModel):
  id: str
  conversation_id: str
  sender_id: str
  content: str | None
  message_type: MessageType
  media_url: str | None
  sent_at: datetime
  read_by: list[str]
  reply_to: ReplyPreview | None
  is_forwarded: bool
  forwarded_from_message_id: str | None
  reactions: dict[str, list[str]]
  is_deleted: bool


class ReactionRequest(BaseModel):
  emoji: str


class ForwardRequest(BaseModel):
  target_conversation_id: str


class MessageListResponse(BaseModel):
  items: list[MessageResponse]
  next_cursor: str | None


class WsEventType(str, Enum):
  new_message = "new_message"
  message_deleted = "message_deleted"
  reaction_updated = "reaction_updated"
  user_typing = "user_typing"
  messages_read = "messages_read"


class WsEvent(BaseModel):
  type: WsEventType
  payload: dict
