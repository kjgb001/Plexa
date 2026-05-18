from __future__ import annotations

from functools import lru_cache

from plexa_server.auth.base import AuthConfigurationError, RequestAuthenticator
from plexa_server.auth.bearer_jwt import BearerJwtAuthenticator
from plexa_server.auth.config import load_auth_config
from plexa_server.auth.dev_header import DevHeaderAuthenticator


def create_request_authenticator() -> RequestAuthenticator:
    """Create the configured request authenticator."""
    config = load_auth_config()
    if config.mode == "dev-header":
        return DevHeaderAuthenticator(config)
    if config.mode == "bearer-jwt":
        return BearerJwtAuthenticator(config)
    raise AuthConfigurationError(f"Unsupported PLEXA_AUTH_MODE: {config.mode}")


@lru_cache(maxsize=1)
def get_request_authenticator() -> RequestAuthenticator:
    """Return the cached configured request authenticator."""
    return create_request_authenticator()


def clear_request_authenticator_cache() -> None:
    """Clear cached authenticator state, primarily for tests."""
    get_request_authenticator.cache_clear()
