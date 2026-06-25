from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.message import MessageType


class ConversationType(str, Enum):
  direct = "direct"
  group = "group"


class LastMessagePreview(BaseModel):
  content: str | None = None
  sender_id: str
  sent_at: datetime
  message_type: MessageType = MessageType.text


class ConversationCreate(BaseModel):
  type: ConversationType
  participants: Annotated[list[str], Field(min_length=2)]
  name: str | None = None
  avatar_url: str | None = None


class ConversationResponse(BaseModel):
  id: str
  type: ConversationType
  participants: list[str]
  name: str | None
  avatar_url: str | None
  created_by: str
  created_at: datetime
  updated_at: datetime
  last_message_preview: LastMessagePreview | None
  unread_count: int = 0


class ConversationListResponse(BaseModel):
  items: list[ConversationResponse]
  next_cursor: str | None
