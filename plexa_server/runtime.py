from __future__ import annotations

import os
import json
import logging
from urllib.parse import urlsplit

from plexa_server.auth.config import load_auth_config
from plexa_server.db.config import get_database_config, load_server_env_file


logger = logging.getLogger(__name__)


class RuntimeConfigurationError(RuntimeError):
    """Raised when application runtime configuration is invalid."""


def _is_obviously_dev_database_url(url: str) -> bool:
    """Return whether a production database URL still contains dev-only markers."""
    if "plexa_dev_password" in url:
        return True

    database_name = urlsplit(url).path.lstrip("/").lower()
    if database_name == "plexa_test":
        return True

    return False


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


def is_env_flag_enabled(name: str) -> bool:
    """Return whether a boolean environment flag is explicitly enabled."""
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _validate_https_url(name: str, value: str) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise RuntimeConfigurationError(
            f"Production {name} must be an absolute HTTPS URL without credentials or a fragment."
        )


def validate_production_runtime_configuration() -> None:
    """Fail fast when production-critical runtime configuration is missing."""
    if not is_production_environment():
        return

    database_config = get_database_config()
    if not database_config.is_configured:
        raise RuntimeConfigurationError(
            "Production runtime requires PLEXA_DATABASE_URL or PLEXA_DATABASE_SYNC_URL."
        )
    for key, value in (
        ("PLEXA_DATABASE_URL", database_config.async_url),
        ("PLEXA_DATABASE_SYNC_URL", database_config.sync_url),
    ):
        if value and _is_obviously_dev_database_url(value):
            raise RuntimeConfigurationError(
                f"Production runtime rejects obviously development-only database value in {key}."
            )

    auth_mode = (os.getenv("PLEXA_AUTH_MODE") or "").strip().lower()
    if not auth_mode:
        raise RuntimeConfigurationError("Production runtime requires PLEXA_AUTH_MODE.")
    if auth_mode == "dev-header":
        if not is_env_flag_enabled("PLEXA_ENABLE_DEV_LOGIN"):
            raise RuntimeConfigurationError(
                "Production runtime cannot use PLEXA_AUTH_MODE=dev-header unless "
                "PLEXA_ENABLE_DEV_LOGIN=true is set for temporary smoke testing."
            )
        logger.warning(
            "PLEXA_AUTH_MODE=dev-header is enabled in production because "
            "PLEXA_ENABLE_DEV_LOGIN=true. Replace this with institutional auth "
            "before serving real students."
        )
    elif auth_mode == "bearer-jwt":
        required = {
            "PLEXA_AUTH_ISSUER": os.getenv("PLEXA_AUTH_ISSUER"),
            "PLEXA_AUTH_AUDIENCE": os.getenv("PLEXA_AUTH_AUDIENCE"),
            "PLEXA_AUTH_JWKS_URL": os.getenv("PLEXA_AUTH_JWKS_URL"),
        }
        missing = [name for name, value in required.items() if not value or not value.strip()]
        if missing:
            raise RuntimeConfigurationError(
                "Production bearer JWT auth requires: " + ", ".join(missing)
            )
        algorithms = (os.getenv("PLEXA_AUTH_ALLOWED_ALGORITHMS") or "RS256").strip()
        if algorithms not in {"RS256", '["RS256"]'}:
            raise RuntimeConfigurationError("Production auth only permits RS256.")
        if not is_env_flag_enabled("PLEXA_AUTH_REQUIRE_EXP"):
            raise RuntimeConfigurationError("Production auth requires PLEXA_AUTH_REQUIRE_EXP=true.")
        _validate_https_url("PLEXA_AUTH_ISSUER", required["PLEXA_AUTH_ISSUER"].strip())
        _validate_https_url("PLEXA_AUTH_JWKS_URL", required["PLEXA_AUTH_JWKS_URL"].strip())
        auth_config = load_auth_config()
        if not auth_config.admin_user_ids and not (
            auth_config.roles_claim and auth_config.admin_role_name
        ):
            raise RuntimeConfigurationError(
                "Production auth requires an initial admin user id or both a roles claim "
                "and admin role mapping."
            )
        if auth_config.jwks_refresh_s <= 0:
            raise RuntimeConfigurationError("PLEXA_AUTH_JWKS_REFRESH_S must be positive.")
        if auth_config.clock_skew_s < 0:
            raise RuntimeConfigurationError("PLEXA_AUTH_CLOCK_SKEW_S cannot be negative.")
    else:
        raise RuntimeConfigurationError(f"Unsupported production auth mode: {auth_mode}")

    cors_origins = os.getenv("PLEXA_CORS_ALLOWED_ORIGINS")
    if cors_origins is None or not cors_origins.strip():
        raise RuntimeConfigurationError("Production runtime requires explicit PLEXA_CORS_ALLOWED_ORIGINS.")
    try:
        parsed_origins = json.loads(cors_origins) if cors_origins.lstrip().startswith("[") else [
            item.strip() for item in cors_origins.split(",") if item.strip()
        ]
    except json.JSONDecodeError as exc:
        raise RuntimeConfigurationError(
            "PLEXA_CORS_ALLOWED_ORIGINS must be valid JSON or CSV."
        ) from exc
    if not isinstance(parsed_origins, list) or not parsed_origins or not all(
        isinstance(item, str) and item for item in parsed_origins
    ):
        raise RuntimeConfigurationError(
            "PLEXA_CORS_ALLOWED_ORIGINS must contain one or more string origins."
        )
    for origin in parsed_origins:
        parsed = urlsplit(origin)
        is_local_smoke_origin = (
            auth_mode == "dev-header"
            and parsed.scheme == "http"
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        )
        if (
            origin == "*"
            or not parsed.hostname
            or (parsed.scheme != "https" and not is_local_smoke_origin)
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeConfigurationError(
                "Production CORS entries must be HTTPS origins; local smoke mode may use loopback HTTP."
            )

    log_key = os.getenv("PLEXA_LOG_ENCRYPTION_KEY")
    log_key_file = os.getenv("PLEXA_LOG_ENCRYPTION_KEY_FILE")
    log_keyring_file = os.getenv("PLEXA_LOG_ENCRYPTION_KEYS_FILE")
    if (log_key is None or not log_key.strip()) and not log_key_file and not log_keyring_file:
        raise RuntimeConfigurationError(
            "Production runtime requires PLEXA_LOG_ENCRYPTION_KEY, "
            "PLEXA_LOG_ENCRYPTION_KEY_FILE, or PLEXA_LOG_ENCRYPTION_KEYS_FILE."
        )

    retention_days = os.getenv("PLEXA_CONTENT_RETENTION_DAYS")
    if retention_days is None or not retention_days.isdigit() or int(retention_days) <= 0:
        raise RuntimeConfigurationError(
            "Production runtime requires a positive PLEXA_CONTENT_RETENTION_DAYS value."
        )

    if os.getenv("PLEXA_WEB_CONCURRENCY", "1").strip() != "1":
        raise RuntimeConfigurationError("Plexa currently supports exactly one application worker.")


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
            base_url = spec.get("base_url")
            if not isinstance(base_url, str):
                raise RuntimeConfigurationError(
                    f"Production inference backend '{backend_id}' requires a base_url."
                )
            parsed_url = urlsplit(base_url)
            if (
                parsed_url.scheme not in {"http", "https"}
                or not parsed_url.hostname
                or parsed_url.username
                or parsed_url.password
                or parsed_url.query
                or parsed_url.fragment
            ):
                raise RuntimeConfigurationError(
                    f"Production inference backend '{backend_id}' has an invalid base_url."
                )
            if not parsed_url.path.rstrip("/").endswith("/v1"):
                raise RuntimeConfigurationError(
                    f"Production inference backend '{backend_id}' base_url must end in /v1."
                )
            if (
                parsed_url.scheme != "https"
                and not is_env_flag_enabled("PLEXA_ALLOW_INSECURE_INFERENCE")
            ):
                raise RuntimeConfigurationError(
                    f"Production inference backend '{backend_id}' must use HTTPS. "
                    "Set PLEXA_ALLOW_INSECURE_INFERENCE=true only for a trusted private network."
                )
            timeout_s = spec.get("timeout_s", 30)
            if (
                not isinstance(timeout_s, (int, float))
                or isinstance(timeout_s, bool)
                or timeout_s <= 0
            ):
                raise RuntimeConfigurationError(
                    f"Production inference backend '{backend_id}' timeout_s must be greater than zero."
                )
        return

    backend_name = (os.getenv("PLEXA_INFERENCE_BACKEND") or "").strip().lower()
    if not backend_name or backend_name == "stub":
        raise RuntimeConfigurationError(
            "Production runtime requires explicit real inference configuration and cannot fall back to stub."
        )
