from fastapi import HTTPException, Request, status
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.constants import JWT_CLAIM_EMAIL, JWT_CLAIM_ID, JWT_CLAIM_ROLE


class UserContextModel(BaseModel):
  Id: str
  Email: str
  Role: str


def decode_token(token: str) -> UserContextModel:
  try:
    payload = jwt.decode(
      token,
      settings.jwt_secret,
      algorithms=[settings.jwt_algorithm],
      issuer=settings.jwt_issuer,
      audience=settings.jwt_issuer,
    )
    return UserContextModel(
      Id=payload[JWT_CLAIM_ID],
      Email=payload[JWT_CLAIM_EMAIL],
      Role=payload[JWT_CLAIM_ROLE],
    )
  except JWTError:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Invalid or expired token",
    )


def get_current_user(request: Request) -> UserContextModel:
  user = getattr(request.state, "user", None)
  if user is None:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Not authenticated",
    )
  return user
