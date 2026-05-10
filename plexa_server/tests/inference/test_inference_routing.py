import asyncio

import pytest

from plexa_server.inference.base import (
    InferenceConfig,
    InferenceProfile,
    InferenceRejected,
    InferenceResult,
    ResolvedInferenceConfig,
)
from plexa_server.inference.routing import (
    InferenceRegistry,
    InferenceRouter,
    create_single_backend_router,
)
from plexa_server.inference.stub import StubInference
from plexa_server.models.message import Message


def make_message(role: str, content: str) -> Message:
    return Message(
        message_id="m1",
        session_id="s1",
        role=role,
        content=content,
    )


class _RecordingBackend(StubInference):
    def __init__(self):
        self.seen_config = None

    async def generate(self, messages, config: ResolvedInferenceConfig) -> InferenceResult:
        self.seen_config = config
        return await super().generate(messages, config)


def test_registry_registers_backends_and_profiles():
    registry = InferenceRegistry()
    registry.register_backend("stub-a", StubInference())
    registry.register_profile(InferenceProfile(name="default", backend_id="stub-a", model="stub-model"))

    assert "stub-a" in registry.list_backends()
    assert registry.get_profile("default").model == "stub-model"


def test_router_resolves_profile_defaults_and_overrides():
    registry = InferenceRegistry()
    backend = _RecordingBackend()
    registry.register_backend("stub-a", backend)
    registry.register_profile(
        InferenceProfile(
            name="fast",
            backend_id="stub-a",
            model="stub-model",
            temperature=0.2,
            extra={"stream": False, "profile_hint": "fast"},
        )
    )
    router = InferenceRouter(registry)

    resolved = router.resolve(
        InferenceConfig(
            profile="fast",
            temperature=0.5,
            extra={"profile_hint": "lesson", "lesson_only": True},
        )
    )

    assert resolved.backend_id == "stub-a"
    assert resolved.model == "stub-model"
    assert resolved.temperature == 0.5
    assert resolved.extra["profile_hint"] == "lesson"
    assert resolved.extra["lesson_only"] is True
    assert resolved.extra["stream"] is False


def test_router_rejects_unknown_profile_without_default_backend():
    registry = InferenceRegistry()
    registry.register_backend("stub-a", StubInference())
    router = InferenceRouter(registry)

    with pytest.raises(InferenceRejected):
        router.resolve(InferenceConfig(profile="missing"))


def test_single_backend_router_allows_direct_profile_passthrough():
    router = create_single_backend_router(StubInference())

    resolved = router.resolve(InferenceConfig(profile="reasoning", temperature=0.4))

    assert resolved.backend_id == "stub"
    assert resolved.model == "reasoning"
    assert resolved.temperature == 0.4


def test_router_dispatches_to_selected_backend():
    registry = InferenceRegistry()
    backend = _RecordingBackend()
    registry.register_backend("stub-a", backend)
    registry.register_profile(InferenceProfile(name="default", backend_id="stub-a", model="stub-model"))
    router = InferenceRouter(registry)

    result = asyncio.run(
        router.generate(
            [make_message("user", "hello")],
            InferenceConfig(profile="default"),
        )
    )

    assert backend.seen_config is not None
    assert backend.seen_config.model == "stub-model"
    assert result.backend == "stub"


def test_router_health_check_reports_status_by_backend_id():
    registry = InferenceRegistry()
    registry.register_backend("stub-a", StubInference())
    router = InferenceRouter(registry)

    statuses = asyncio.run(router.health_check())

    assert statuses == {"stub-a": True}
