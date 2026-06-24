from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.auth import decode_token

_PUBLIC_PATHS: frozenset[str] = frozenset({"/health", "/redoc", "/openapi.json"})


class AuthMiddleware(BaseHTTPMiddleware):
  def __init__(self, app: ASGIApp) -> None:
    super().__init__(app)

  async def dispatch(self, request: Request, call_next) -> Response:
    path = request.url.path

    if path in _PUBLIC_PATHS or path.startswith("/docs"):
      return await call_next(request)

    authorization: str = request.headers.get("Authorization", "")
    scheme, _, credentials = authorization.partition(" ")

    if scheme.lower() != "bearer" or not credentials:
      return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    try:
      request.state.user = decode_token(credentials)
    except HTTPException as exc:
      return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return await call_next(request)
