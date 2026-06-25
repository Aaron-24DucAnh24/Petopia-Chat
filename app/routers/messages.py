from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.auth import TokenPayload, get_current_user
from app.core.constants import DEFAULT_MESSAGE_LIMIT, MAX_PAGE_LIMIT
from app.db.mongodb import get_db
from app.db.redis import get_redis
from app.models.message import (
  MessageCreate,
  MessageListResponse,
  MessageResponse,
  ReactionRequest,
)
from app.services.message_service import MessageService

router = APIRouter(tags=["Messages"])


def get_service(
  db: AsyncIOMotorDatabase = Depends(get_db),
  redis: aioredis.Redis = Depends(get_redis),
) -> MessageService:
  return MessageService(db, redis)


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
  conversation_id: str,
  cursor: Optional[str] = Query(None, description="Pagination cursor (message ObjectId hex)"),
  limit: int = Query(DEFAULT_MESSAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
  current_user: TokenPayload = Depends(get_current_user),
  service: MessageService = Depends(get_service),
) -> MessageListResponse:
  return await service.list_messages(conversation_id, current_user.Id, cursor, limit)


@router.post(
  "/conversations/{conversation_id}/messages",
  response_model=MessageResponse,
  status_code=status.HTTP_201_CREATED,
)
async def send_message(
  conversation_id: str,
  payload: MessageCreate,
  current_user: TokenPayload = Depends(get_current_user),
  service: MessageService = Depends(get_service),
) -> MessageResponse:
  return await service.send_message(conversation_id, payload, current_user.Id)


@router.post("/conversations/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def mark_read(
  conversation_id: str,
  current_user: TokenPayload = Depends(get_current_user),
  service: MessageService = Depends(get_service),
):
  await service.mark_read(conversation_id, current_user.Id)


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_message(
  message_id: str,
  current_user: TokenPayload = Depends(get_current_user),
  service: MessageService = Depends(get_service),
):
  await service.delete_message(message_id, current_user.Id)


@router.post("/messages/{message_id}/reactions", response_model=MessageResponse)
async def toggle_reaction(
  message_id: str,
  payload: ReactionRequest,
  current_user: TokenPayload = Depends(get_current_user),
  service: MessageService = Depends(get_service),
) -> MessageResponse:
  return await service.toggle_reaction(message_id, current_user.Id, payload.emoji)


