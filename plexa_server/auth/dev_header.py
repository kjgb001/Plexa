from __future__ import annotations

from fastapi import Request

from plexa_server.auth.base import RequestAuthenticator
from plexa_server.auth.config import AuthConfig
from plexa_server.auth.identity import UserIdentity


class DevHeaderAuthenticator(RequestAuthenticator):
    """Development-only authenticator that trusts a configured user header."""

    def __init__(self, config: AuthConfig):
        self._config = config

    def authenticate_request(self, request: Request) -> UserIdentity:
        """Return a normalized identity from the dev user header."""
        user_id = request.headers.get(self._config.user_header_name)
        if user_id is None or not user_id.strip():
            return UserIdentity()
        normalized_user_id = user_id.strip()
        if len(normalized_user_id) > 255 or any(
            ord(character) < 32 or ord(character) == 127
            for character in normalized_user_id
        ):
            return UserIdentity()

        identity = UserIdentity(
            user_id=normalized_user_id,
            roles={"user"},
            auth_type="dev_header",
        )
        if identity.user_id in self._config.admin_user_ids:
            identity.roles.add("admin")
        return identity
