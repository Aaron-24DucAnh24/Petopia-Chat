from __future__ import annotations

from pydantic import BaseModel


class UnreadMessage(BaseModel):
  user_id: str
  conversation_id: str
