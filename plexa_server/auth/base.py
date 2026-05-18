from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import Request

from plexa_server.auth.identity import UserIdentity


class AuthConfigurationError(RuntimeError):
    """Raised when auth configuration is invalid or incomplete."""


class AuthVerificationError(RuntimeError):
    """Raised when a presented credential cannot be validated."""


class RequestAuthenticator(Protocol):
    """Authenticate a FastAPI request into a normalized identity."""

    def authenticate_request(self, request: Request) -> UserIdentity:
        """Return the identity represented by the request."""


@dataclass(frozen=True)
class AuthResult:
    """Internal normalized auth result before middleware attachment."""

    identity: UserIdentity
