from __future__ import annotations

import time
from typing import List

from plexa_server.inference.base import (
    InferenceBackend,
    InferenceResult,
    ResolvedInferenceConfig,
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
        """Return the stable backend identifier used in result metadata.

        Returns:
            str: Stable backend name for the stub adapter.
        """
        return "stub"

    async def generate(
        self,
        messages: List["Message"],
        config: ResolvedInferenceConfig,
    ) -> InferenceResult:
        """Generate a deterministic assistant reply from the latest user message.

        Args:
            messages: Ordered transcript supplied to the backend.
            config: Frozen inference config for the current session.

        Returns:
            InferenceResult: Deterministic assistant reply with usage metadata.
        """
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

    async def health_check(self) -> bool:
        """Report stub readiness for health and readiness checks.

        Returns:
            bool: Always `True` for the in-process stub backend.
        """
        return True


# Type-only import to avoid runtime circular dependency
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from plexa_server.models.message import Message
