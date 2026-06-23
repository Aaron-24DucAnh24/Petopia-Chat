from fastapi import HTTPException, status


def not_found(resource: str = "Resource") -> HTTPException:
  return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} not found")


def forbidden(detail: str = "Access denied") -> HTTPException:
  return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def bad_request(detail: str) -> HTTPException:
  return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
