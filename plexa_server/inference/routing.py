from __future__ import annotations

from typing import AsyncIterator, Iterable

from plexa_server.inference.base import (
    InferenceBackend,
    InferenceConfig,
    InferenceConfigurationError,
    InferenceChunk,
    InferenceProfile,
    InferenceRejected,
    InferenceResult,
    ResolvedInferenceConfig,
)


class InferenceRegistry:
    """Registry of configured inference backends and server-side profiles."""

    def __init__(self) -> None:
        self._backends: dict[str, InferenceBackend] = {}
        self._profiles: dict[str, InferenceProfile] = {}

    def register_backend(self, backend_id: str, backend: InferenceBackend) -> None:
        """Register a backend instance under a stable identifier."""
        if backend_id in self._backends:
            raise InferenceConfigurationError(f"Duplicate inference backend id: {backend_id}")
        self._backends[backend_id] = backend

    def register_profile(self, profile: InferenceProfile) -> None:
        """Register an inference profile."""
        if profile.name in self._profiles:
            raise InferenceConfigurationError(f"Duplicate inference profile name: {profile.name}")
        self._profiles[profile.name] = profile

    def get_backend(self, backend_id: str) -> InferenceBackend:
        """Return a registered backend by id."""
        try:
            return self._backends[backend_id]
        except KeyError as exc:
            raise InferenceConfigurationError(f"Unknown inference backend id: {backend_id}") from exc

    def get_profile(self, profile_name: str) -> InferenceProfile:
        """Return a registered profile by name."""
        try:
            return self._profiles[profile_name]
        except KeyError as exc:
            raise InferenceConfigurationError(f"Unknown inference profile: {profile_name}") from exc

    def list_backends(self) -> dict[str, InferenceBackend]:
        """Return a copy of the registered backend mapping."""
        return dict(self._backends)

    def list_profiles(self) -> dict[str, InferenceProfile]:
        """Return a copy of the registered profile mapping."""
        return dict(self._profiles)


class InferenceRouter:
    """Resolve inference profiles and dispatch generation to the right backend."""

    def __init__(
        self,
        registry: InferenceRegistry,
        default_backend_id: str | None = None,
    ) -> None:
        self._registry = registry
        self._default_backend_id = default_backend_id

    @property
    def registry(self) -> InferenceRegistry:
        """Expose the underlying registry for read-only consumers."""
        return self._registry

    @property
    def default_backend_id(self) -> str | None:
        """Return the fallback backend id used for unresolved profiles."""
        return self._default_backend_id

    def resolve(self, config: InferenceConfig) -> ResolvedInferenceConfig:
        """Resolve a frozen lesson/session config into concrete backend settings."""
        profile_name = config.profile.strip()
        if not profile_name:
            raise InferenceRejected("Inference profile cannot be empty.")

        if profile_name in self._registry.list_profiles():
            profile = self._registry.get_profile(profile_name)
            backend = self._registry.get_backend(profile.backend_id)
            merged_extra = {**profile.extra, **config.extra}
            return ResolvedInferenceConfig(
                profile=profile.name,
                backend_id=profile.backend_id,
                backend_name=backend.name,
                model=profile.model,
                temperature=config.temperature if config.temperature is not None else profile.temperature,
                top_p=config.top_p if config.top_p is not None else profile.top_p,
                max_tokens=config.max_tokens if config.max_tokens is not None else profile.max_tokens,
                stop=config.stop if config.stop is not None else profile.stop,
                timeout_s=config.timeout_s if config.timeout_s is not None else profile.timeout_s,
                seed=config.seed if config.seed is not None else profile.seed,
                extra=merged_extra,
            )

        if self._default_backend_id is not None:
            backend = self._registry.get_backend(self._default_backend_id)
            return ResolvedInferenceConfig(
                profile=profile_name,
                backend_id=self._default_backend_id,
                backend_name=backend.name,
                model=profile_name,
                temperature=config.temperature,
                top_p=config.top_p,
                max_tokens=config.max_tokens,
                stop=config.stop,
                timeout_s=config.timeout_s,
                seed=config.seed,
                extra=dict(config.extra),
            )

        raise InferenceRejected(f"Unknown inference profile: {profile_name}")

    async def generate(self, messages: list["Message"], config: InferenceConfig) -> InferenceResult:
        """Resolve and execute an inference request."""
        resolved = self.resolve(config)
        backend = self._registry.get_backend(resolved.backend_id)
        return await backend.generate(messages, resolved)

    async def stream(
        self,
        messages: list["Message"],
        config: InferenceConfig,
    ) -> AsyncIterator[InferenceChunk]:
        """Resolve and stream an inference request."""
        resolved = self.resolve(config)
        backend = self._registry.get_backend(resolved.backend_id)
        async for chunk in backend.stream(messages, resolved):
            yield chunk

    async def health_check(self, required_backend_ids: set[str] | None = None) -> dict[str, bool]:
        """Return backend health by id for the requested backend set."""
        if required_backend_ids is None:
            backend_ids: Iterable[str] = self._registry.list_backends().keys()
        else:
            backend_ids = required_backend_ids

        statuses: dict[str, bool] = {}
        for backend_id in backend_ids:
            try:
                backend = self._registry.get_backend(backend_id)
                statuses[backend_id] = await backend.health_check()
            except Exception:
                statuses[backend_id] = False
        return statuses


def create_single_backend_router(
    backend: InferenceBackend,
    backend_id: str | None = None,
) -> InferenceRouter:
    """Create a compatibility router around a single backend instance."""
    backend_identifier = backend_id or backend.name
    registry = InferenceRegistry()
    registry.register_backend(backend_identifier, backend)
    return InferenceRouter(registry=registry, default_backend_id=backend_identifier)


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plexa_server.models.message import Message
