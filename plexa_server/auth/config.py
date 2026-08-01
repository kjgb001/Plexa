from __future__ import annotations

import json
import os
from dataclasses import dataclass

from plexa_server.db.config import load_server_env_file


@dataclass(frozen=True)
class AuthConfig:
    """Normalized server auth configuration."""

    mode: str
    user_id_claim: str = "sub"
    roles_claim: str | None = None
    admin_role_name: str | None = None
    admin_user_ids: frozenset[str] = frozenset()
    issuer: str | None = None
    audience: str | None = None
    allowed_algorithms: tuple[str, ...] = ("RS256",)
    shared_secret: str | None = None
    public_key_pem: str | None = None
    public_key_file: str | None = None
    jwks_json: str | None = None
    jwks_file: str | None = None
    jwks_url: str | None = None
    jwks_refresh_s: int = 300
    clock_skew_s: int = 30
    require_exp: bool = False
    user_header_name: str = "X-User-Id"
    authorization_header_name: str = "Authorization"


def _parse_admin_user_ids(raw: str | None) -> frozenset[str]:
    """Parse configured admin user ids from JSON or CSV."""
    if raw is None or not raw.strip():
        return frozenset()

    raw = raw.strip()
    if raw.startswith("["):
        data = json.loads(raw)
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ValueError("PLEXA_ADMIN_USER_IDS must be a JSON array of strings or a CSV string.")
        return frozenset(item.strip() for item in data if item.strip())

    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def _parse_allowed_algorithms(raw: str | None) -> tuple[str, ...]:
    """Parse allowed JWT algorithms from JSON or CSV."""
    if raw is None or not raw.strip():
        return ("RS256",)

    raw = raw.strip()
    if raw.startswith("["):
        data = json.loads(raw)
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ValueError(
                "PLEXA_AUTH_ALLOWED_ALGORITHMS must be a JSON array of strings or a CSV string."
            )
        values = tuple(item.strip() for item in data if item.strip())
        return values or ("RS256",)

    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values or ("RS256",)


def load_auth_config() -> AuthConfig:
    """Load server auth configuration from environment variables."""
    load_server_env_file()

    mode = os.getenv("PLEXA_AUTH_MODE", "dev-header").strip().lower()
    return AuthConfig(
        mode=mode,
        user_id_claim=os.getenv("PLEXA_AUTH_USER_ID_CLAIM", "sub").strip() or "sub",
        roles_claim=(os.getenv("PLEXA_AUTH_ROLES_CLAIM") or "").strip() or None,
        admin_role_name=(os.getenv("PLEXA_AUTH_ADMIN_ROLE_NAME") or "").strip() or None,
        admin_user_ids=_parse_admin_user_ids(os.getenv("PLEXA_ADMIN_USER_IDS")),
        issuer=(os.getenv("PLEXA_AUTH_ISSUER") or "").strip() or None,
        audience=(os.getenv("PLEXA_AUTH_AUDIENCE") or "").strip() or None,
        allowed_algorithms=_parse_allowed_algorithms(os.getenv("PLEXA_AUTH_ALLOWED_ALGORITHMS")),
        shared_secret=(os.getenv("PLEXA_AUTH_SHARED_SECRET") or "").strip() or None,
        public_key_pem=(os.getenv("PLEXA_AUTH_PUBLIC_KEY_PEM") or "").strip() or None,
        public_key_file=(os.getenv("PLEXA_AUTH_PUBLIC_KEY_FILE") or "").strip() or None,
        jwks_json=(os.getenv("PLEXA_AUTH_JWKS_JSON") or "").strip() or None,
        jwks_file=(os.getenv("PLEXA_AUTH_JWKS_FILE") or "").strip() or None,
        jwks_url=(os.getenv("PLEXA_AUTH_JWKS_URL") or "").strip() or None,
        jwks_refresh_s=int(os.getenv("PLEXA_AUTH_JWKS_REFRESH_S", "300")),
        clock_skew_s=int(os.getenv("PLEXA_AUTH_CLOCK_SKEW_S", "30")),
        require_exp=os.getenv("PLEXA_AUTH_REQUIRE_EXP", "false").strip().lower()
        in {"1", "true", "yes", "on"},
        user_header_name=os.getenv("PLEXA_AUTH_USER_HEADER_NAME", "X-User-Id").strip() or "X-User-Id",
        authorization_header_name=(
            os.getenv("PLEXA_AUTH_AUTHORIZATION_HEADER_NAME", "Authorization").strip()
            or "Authorization"
        ),
    )
