from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.constants import JWT_CLAIM_EMAIL, JWT_CLAIM_ID, JWT_CLAIM_ROLE

bearer_scheme = HTTPBearer()


class TokenPayload(BaseModel):
  Id: str
  Email: str
  Role: str


def decode_token(token: str) -> TokenPayload:
  try:
    payload = jwt.decode(
      token,
      settings.jwt_secret,
      algorithms=[settings.jwt_algorithm],
      issuer=settings.jwt_issuer,
    )
    return TokenPayload(
      Id=payload[JWT_CLAIM_ID],
      Email=payload[JWT_CLAIM_EMAIL],
      Role=payload[JWT_CLAIM_ROLE],
    )
  except JWTError:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Invalid or expired token",
    )


def get_current_user(
  credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenPayload:
  return decode_token(credentials.credentials)
