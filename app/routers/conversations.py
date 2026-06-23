from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.auth import TokenPayload, get_current_user
from app.core.constants import DEFAULT_CONVERSATION_LIMIT, MAX_PAGE_LIMIT
from app.db.mongodb import get_db
from app.models.conversation import (
  ConversationCreate,
  ConversationListResponse,
  ConversationResponse,
)
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def get_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> ConversationService:
  return ConversationService(db)


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
  cursor: Optional[str] = Query(None, description="Pagination cursor (updated_at ISO timestamp)"),
  limit: int = Query(DEFAULT_CONVERSATION_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
  current_user: TokenPayload = Depends(get_current_user),
  service: ConversationService = Depends(get_service),
) -> ConversationListResponse:
  return await service.list_conversations(current_user.Id, cursor, limit)


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
  payload: ConversationCreate,
  current_user: TokenPayload = Depends(get_current_user),
  service: ConversationService = Depends(get_service),
) -> ConversationResponse:
  return await service.create_conversation(payload, current_user.Id)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
  conversation_id: str,
  current_user: TokenPayload = Depends(get_current_user),
  service: ConversationService = Depends(get_service),
) -> ConversationResponse:
  return await service.get_conversation(conversation_id, current_user.Id)
