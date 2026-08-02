"""OpenAPI metadata shared by the runtime and static documentation build."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from plexa_server.auth.config import AuthConfig


API_DESCRIPTION = """
Plexa serves the student and instructor portals through a versioned HTTP API.

Most endpoints require the identity mechanism configured by the institution.
The liveness, readiness, and non-production inference diagnostic endpoints are
intentionally public so deployment infrastructure can probe the service.
""".strip()

OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Resolve the server-authoritative identity and portal permissions.",
    },
    {
        "name": "courses",
        "description": "Browse courses and manage enrollment, lessons, timelines, and logs.",
    },
    {
        "name": "sessions",
        "description": "Run lesson conversations, reflections, completion, and turn-in.",
    },
    {
        "name": "admin",
        "description": "Administrative course and lesson operations.",
    },
    {
        "name": "health",
        "description": "Public process and dependency health checks.",
    },
]

PUBLIC_OPERATION_PATHS = frozenset(
    {
        "/api/health",
        "/api/ready",
        "/api/debug/inference",
    }
)


def _security_scheme(config: AuthConfig) -> tuple[str, dict[str, Any]]:
    """Return the OpenAPI scheme matching the active request authenticator."""
    if config.mode == "dev-header":
        return (
            "DevHeaderAuth",
            {
                "type": "apiKey",
                "in": "header",
                "name": config.user_header_name,
                "description": "Development-only identity header. Do not enable in production.",
            },
        )

    if config.mode == "bearer-jwt":
        if config.authorization_header_name.lower() == "authorization":
            return (
                "BearerAuth",
                {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Institution-issued bearer JWT.",
                },
            )
        return (
            "BearerAuth",
            {
                "type": "apiKey",
                "in": "header",
                "name": config.authorization_header_name,
                "description": "Institution-issued JWT formatted as `Bearer <token>`.",
            },
        )

    raise ValueError(f"Unsupported OpenAPI authentication mode: {config.mode}")


def configure_openapi_security(app: FastAPI, config: AuthConfig) -> None:
    """Annotate the generated schema with the configured authentication mode."""
    scheme_name, scheme = _security_scheme(config)
    original_openapi: Callable[[], dict[str, Any]] = app.openapi

    def custom_openapi() -> dict[str, Any]:
        schema = original_openapi()
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes[scheme_name] = scheme
        schema["security"] = [{scheme_name: []}]

        for path in PUBLIC_OPERATION_PATHS:
            for operation in schema.get("paths", {}).get(path, {}).values():
                if isinstance(operation, dict):
                    operation["security"] = []
        return schema

    app.openapi = custom_openapi
