from __future__ import annotations

import os
import json

from plexa_server.db.config import get_database_config, load_server_env_file


class RuntimeConfigurationError(RuntimeError):
    """Raised when application runtime configuration is invalid."""


def get_app_environment() -> str:
    """Return the normalized Plexa application environment."""
    load_server_env_file()
    value = os.getenv("PLEXA_ENV", "development").strip().lower()
    if value in {"prod", "production"}:
        return "production"
    if value in {"test", "testing"}:
        return "test"
    return "development"


def is_production_environment() -> bool:
    """Return whether Plexa is running in production mode."""
    return get_app_environment() == "production"


def validate_production_runtime_configuration() -> None:
    """Fail fast when production-critical runtime configuration is missing."""
    if not is_production_environment():
        return

    database_config = get_database_config()
    if not database_config.is_configured:
        raise RuntimeConfigurationError(
            "Production runtime requires PLEXA_DATABASE_URL or PLEXA_DATABASE_SYNC_URL."
        )

    auth_mode = (os.getenv("PLEXA_AUTH_MODE") or "").strip().lower()
    if not auth_mode:
        raise RuntimeConfigurationError("Production runtime requires PLEXA_AUTH_MODE.")
    if auth_mode == "dev-header":
        raise RuntimeConfigurationError("Production runtime cannot use PLEXA_AUTH_MODE=dev-header.")

    cors_origins = os.getenv("PLEXA_CORS_ALLOWED_ORIGINS")
    if cors_origins is None or not cors_origins.strip():
        raise RuntimeConfigurationError("Production runtime requires explicit PLEXA_CORS_ALLOWED_ORIGINS.")

    log_key = os.getenv("PLEXA_LOG_ENCRYPTION_KEY")
    if log_key is None or not log_key.strip():
        raise RuntimeConfigurationError("Production runtime requires PLEXA_LOG_ENCRYPTION_KEY.")


def validate_production_inference_configuration() -> None:
    """Fail fast when production inference config would resolve to dev-only behavior."""
    if not is_production_environment():
        return

    raw_backend_specs = os.getenv("PLEXA_INFERENCE_BACKENDS")
    if raw_backend_specs and raw_backend_specs.strip():
        try:
            backend_specs = json.loads(raw_backend_specs)
        except json.JSONDecodeError as exc:
            raise RuntimeConfigurationError("PLEXA_INFERENCE_BACKENDS must be valid JSON.") from exc
        if not isinstance(backend_specs, dict):
            raise RuntimeConfigurationError("PLEXA_INFERENCE_BACKENDS must be a JSON object.")
        for backend_id, spec in backend_specs.items():
            if not isinstance(spec, dict):
                raise RuntimeConfigurationError(
                    f"PLEXA_INFERENCE_BACKENDS entry '{backend_id}' must be an object."
                )
            if spec.get("type") == "stub":
                raise RuntimeConfigurationError(
                    "Production runtime cannot use stub inference backends."
                )
        return

    backend_name = (os.getenv("PLEXA_INFERENCE_BACKEND") or "").strip().lower()
    if not backend_name or backend_name == "stub":
        raise RuntimeConfigurationError(
            "Production runtime requires explicit real inference configuration and cannot fall back to stub."
        )
