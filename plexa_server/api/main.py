import json
import os

import uvicorn

from plexa_server.api.app import build_app
from plexa_server.db.config import load_server_env_file
from plexa_server.inference.base import InferenceProfile
from plexa_server.inference.openai_compatible import OpenAICompatibleInference
from plexa_server.inference.routing import InferenceRegistry, InferenceRouter
from plexa_server.inference.stub import StubInference
from plexa_server.runtime import (
    validate_production_inference_configuration,
    validate_production_runtime_configuration,
)


def _load_json_env(name: str):
    """Return parsed JSON from an environment variable when present."""
    import os

    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be valid JSON.") from exc


def _build_backend_from_spec(spec: dict) -> object:
    """Build an inference backend instance from a backend spec."""
    backend_type = spec.get("type")
    if backend_type == "stub":
        return StubInference()
    if backend_type == "openai-compatible":
        base_url = spec.get("base_url")
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("OpenAI-compatible backend spec requires a non-empty base_url.")
        timeout_s = float(spec.get("timeout_s", 30.0))
        api_key = spec.get("api_key")
        if api_key is not None and not isinstance(api_key, str):
            raise ValueError("OpenAI-compatible backend api_key must be a string when provided.")
        return OpenAICompatibleInference(
            base_url=base_url,
            api_key=api_key,
            timeout_s=timeout_s,
        )
    raise ValueError(f"Unsupported inference backend type: {backend_type}")


def create_inference_registry() -> InferenceRegistry:
    """Create the configured inference backend/profile registry from environment settings."""
    import os

    load_server_env_file()
    registry = InferenceRegistry()

    backend_specs = _load_json_env("PLEXA_INFERENCE_BACKENDS")
    profile_specs = _load_json_env("PLEXA_INFERENCE_PROFILES")
    backend_name = os.getenv("PLEXA_INFERENCE_BACKEND", "").strip().lower()
    app_env = os.getenv("PLEXA_ENV", "development").strip().lower()

    if backend_name == "stub" and app_env not in {"prod", "production"}:
        registry.register_backend("stub", StubInference())
        return registry

    if backend_specs is not None:
        if not isinstance(backend_specs, dict):
            raise ValueError("PLEXA_INFERENCE_BACKENDS must be a JSON object.")
        for backend_id, spec in backend_specs.items():
            if not isinstance(backend_id, str) or not isinstance(spec, dict):
                raise ValueError("PLEXA_INFERENCE_BACKENDS must map string ids to backend objects.")
            registry.register_backend(backend_id, _build_backend_from_spec(spec))

        if profile_specs is None or not isinstance(profile_specs, dict):
            raise ValueError("PLEXA_INFERENCE_PROFILES must be a JSON object when using multiple backends.")
        for profile_name, spec in profile_specs.items():
            if not isinstance(profile_name, str) or not isinstance(spec, dict):
                raise ValueError("PLEXA_INFERENCE_PROFILES must map string names to profile objects.")
            backend_id = spec["backend_id"]
            if backend_id not in registry.list_backends():
                raise ValueError(
                    f"Profile '{profile_name}' references unknown backend id '{backend_id}'."
                )
            registry.register_profile(
                InferenceProfile(
                    name=profile_name,
                    backend_id=backend_id,
                    model=spec["model"],
                    temperature=spec.get("temperature"),
                    top_p=spec.get("top_p"),
                    max_tokens=spec.get("max_tokens"),
                    stop=spec.get("stop"),
                    timeout_s=spec.get("timeout_s"),
                    seed=spec.get("seed"),
                    extra=spec.get("extra", {}),
                )
        )
        return registry

    backend_name = backend_name or "stub"
    if backend_name == "stub":
        registry.register_backend("stub", StubInference())
        return registry

    if backend_name == "openai-compatible":
        registry.register_backend("openai-compatible", OpenAICompatibleInference.from_env())

        model_map = _load_json_env("PLEXA_OPENAI_MODEL_MAP")
        default_model = os.getenv("PLEXA_OPENAI_DEFAULT_MODEL")
        if model_map is not None:
            if not isinstance(model_map, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in model_map.items()
            ):
                raise ValueError("PLEXA_OPENAI_MODEL_MAP must be a JSON object of string pairs.")
            for profile_name, model_name in model_map.items():
                registry.register_profile(
                    InferenceProfile(
                        name=profile_name,
                        backend_id="openai-compatible",
                        model=model_name,
                    )
                )
        if default_model and "default" not in registry.list_profiles():
            registry.register_profile(
                InferenceProfile(
                    name="default",
                    backend_id="openai-compatible",
                    model=default_model,
                )
            )
        if not registry.list_profiles():
            raise ValueError(
                "OpenAI-compatible inference requires at least one profile. "
                "Set PLEXA_OPENAI_DEFAULT_MODEL, PLEXA_OPENAI_MODEL_MAP, or "
                "use PLEXA_INFERENCE_PROFILES with PLEXA_INFERENCE_BACKENDS."
            )
        return registry

    raise ValueError(f"Unsupported inference backend: {backend_name}")


def create_inference_router() -> InferenceRouter:
    """Create the configured inference router."""
    import os

    registry = create_inference_registry()
    backend_specs = _load_json_env("PLEXA_INFERENCE_BACKENDS")
    backend_name = os.getenv("PLEXA_INFERENCE_BACKEND", "stub").strip().lower()
    app_env = os.getenv("PLEXA_ENV", "development").strip().lower()
    if (
        backend_name == "stub"
        and app_env not in {"prod", "production"}
        and "stub" in registry.list_backends()
    ):
        return InferenceRouter(registry=registry, default_backend_id="stub")
    if backend_specs is None and backend_name == "stub":
        return InferenceRouter(registry=registry, default_backend_id="stub")
    return InferenceRouter(registry=registry)


def create_required_backend_ids() -> set[str] | None:
    """Return backend ids that must be healthy for readiness checks."""
    import os

    required = _load_json_env("PLEXA_INFERENCE_REQUIRED_BACKENDS")
    if required is not None:
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise ValueError("PLEXA_INFERENCE_REQUIRED_BACKENDS must be a JSON array of strings.")
        return set(required)

    raw = os.getenv("PLEXA_INFERENCE_REQUIRED_BACKENDS_CSV")
    if raw:
        return {item.strip() for item in raw.split(",") if item.strip()}
    return None


def create_app():
    """Create the default application instance backed by the configured inference router."""
    load_server_env_file()
    validate_production_runtime_configuration()
    validate_production_inference_configuration()
    return build_app(
        inference_router=create_inference_router(),
        required_backend_ids=create_required_backend_ids(),
    )


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "plexa_server.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("PLEXA_UVICORN_RELOAD", "false").strip().lower() == "true",
        ws="none",
    )
