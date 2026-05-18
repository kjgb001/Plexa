from __future__ import annotations

from fastapi import Request

from plexa_server.auth.base import RequestAuthenticator
from plexa_server.auth.factory import get_request_authenticator
from plexa_server.auth.identity import UserIdentity


def build_request_identity(request: Request) -> UserIdentity:
    """Resolve a request identity using the configured authenticator.

    Args:
        request: Incoming FastAPI request.

    Returns:
        UserIdentity: Identity derived from the request headers.
    """
    return get_request_authenticator().authenticate_request(request)


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


def create_auth_identity_middleware(authenticator: RequestAuthenticator):
    """Create middleware bound to a specific authenticator instance."""

    async def _middleware(request: Request, call_next):
        request.state.identity = authenticator.authenticate_request(request)
        return await call_next(request)

    return _middleware
