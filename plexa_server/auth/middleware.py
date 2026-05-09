from __future__ import annotations

import os

from fastapi import Request

from plexa_server.auth.identity import UserIdentity


def build_request_identity(request: Request) -> UserIdentity:
    """Resolve a request identity from the currently supported auth headers.

    Args:
        request: Incoming FastAPI request.

    Returns:
        UserIdentity: Identity derived from the request headers.
    """
    user_id = request.headers.get("X-User-Id")
    admin_token = request.headers.get("X-Admin-Token")
    expected_admin_token = os.getenv("PLEXA_ADMIN_TOKEN")

    if admin_token is not None and expected_admin_token is not None and admin_token == expected_admin_token:
        return UserIdentity(
            user_id=user_id,
            roles={"admin"} | ({"user"} if user_id is not None else set()),
            claims={"admin_token_present": True},
            auth_type="admin_token",
        )

    if user_id is not None:
        claims: dict[str, object] = {}
        if admin_token is not None:
            claims["admin_token_present"] = True
            claims["admin_token_valid"] = False
        return UserIdentity(
            user_id=user_id,
            roles={"user"},
            claims=claims,
            auth_type="dev_header",
        )

    claims = {}
    if admin_token is not None:
        claims["admin_token_present"] = True
        claims["admin_token_valid"] = False
    return UserIdentity(claims=claims)


async def auth_identity_middleware(request: Request, call_next):
    """Attach the resolved request identity to `request.state`.

    Args:
        request: Incoming FastAPI request.
        call_next: Downstream ASGI application callback.

    Returns:
        Response: Downstream response.
    """
    request.state.identity = build_request_identity(request)
    return await call_next(request)
