from fastapi import Header, HTTPException
import os


def require_admin_token(
    token: str | None = Header(default=None, alias="X-Admin-Token")
) -> str:
    expected = os.getenv("PLEXA_ADMIN_TOKEN")
    if expected is None:
        raise HTTPException(
            status_code=500,
            detail="Admin token not configured"
        )

    if token is None or token != expected:
        raise HTTPException(
            status_code=403,
            detail="Invalid admin token"
        )

    return token