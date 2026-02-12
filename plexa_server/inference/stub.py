from __future__ import annotations

import time
from typing import List

from plexa_server.inference.base import (
    InferenceBackend,
    InferenceConfig,
    InferenceResult,
    Usage,
)


class StubInference(InferenceBackend):
    """Deterministic, in-process inference backend.

    This backend performs no network calls and requires no model.
    It is used to validate session lifecycle, policy enforcement,
    locking, and atomic state transitions.
    """

    @property
    def name(self) -> str:
        return "stub"

    def generate(self, messages: List["Message"], config: InferenceConfig) -> InferenceResult:
        start = time.perf_counter()

        # Extract the most recent user message (if any)
        last_user_content = None
        for message in reversed(messages):
            if message.role == "user":
                last_user_content = message.content
                break

        if last_user_content is None:
            last_user_content = "<no user message found>"

        # Deterministic response construction
        response_text = (
            "[STUB RESPONSE]\n"
            f"Model: {config.model}\n"
            f"Received: {last_user_content}"
        )

        latency_ms = int((time.perf_counter() - start) * 1000)

        # Provide minimal, deterministic usage metadata
        usage = Usage(
            prompt_tokens=len(messages),
            completion_tokens=len(response_text.split()),
            total_tokens=len(messages) + len(response_text.split()),
        )

        return InferenceResult(
            content=response_text,
            finish_reason="stop",
            usage=usage,
            backend=self.name,
            model=config.model,
            latency_ms=latency_ms,
        )

    def healthcheck(self) -> bool:
        return True


# Type-only import to avoid runtime circular dependency
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from plexa_server.models.message import Message
