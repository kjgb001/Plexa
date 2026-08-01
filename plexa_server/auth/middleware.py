from __future__ import annotations

import asyncio
import logging
from fastapi import Request
from fastapi.responses import JSONResponse

from plexa_server.auth.base import AuthConfigurationError, RequestAuthenticator
from plexa_server.auth.factory import get_request_authenticator
from plexa_server.auth.identity import UserIdentity


logger = logging.getLogger(__name__)


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
        try:
            request.state.identity = await asyncio.to_thread(
                authenticator.authenticate_request,
                request,
            )
        except AuthConfigurationError:
            logger.exception("authentication_provider_unavailable")
            return JSONResponse(
                status_code=503,
                content={"detail": "Authentication provider unavailable"},
            )
        return await call_next(request)

    return _middleware
