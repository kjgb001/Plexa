from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, UTC
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# Errors (normalized boundary)

class InferenceError(RuntimeError):
    """Base class for all inference-layer errors.

    Core logic should only catch InferenceError (or subclasses) so that backend-
    specific exceptions never leak across the inference boundary.
    """


class InferenceTimeout(InferenceError):
    """Raised when the inference backend does not respond within timeout."""


class InferenceBackendUnavailable(InferenceError):
    """Raised when the inference backend is unreachable or unhealthy."""


class InferenceMalformedResponse(InferenceError):
    """Raised when the backend response is missing required fields or is invalid."""


class InferenceRejected(InferenceError):
    """Raised when the backend rejects the request (bad input, auth, etc.)."""


# Core DTOs (backend-agnostic)

FinishReason = Literal[
    "stop",
    "length",
    "content_filter",
    "tool_calls",
    "error",
    "unknown",
]


class InferenceConfig(BaseModel):
    """Frozen inference parameters.

    This should be constructed from lesson constraints and treated as immutable
    for the lifetime of a session/lesson instance.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Model routing / selection
    model: str = Field(..., description="Backend model identifier/name.")

    # Sampling controls
    temperature: Optional[float] = Field(
        default=None, ge=0.0, description="Sampling temperature."
    )
    top_p: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Nucleus sampling probability mass."
    )

    # Output limits
    max_tokens: Optional[int] = Field(
        default=None, gt=0, description="Max tokens to generate (backend dependent)."
    )

    # Stop conditions (best-effort depending on backend support)
    stop: Optional[List[str]] = Field(
        default=None, description="Stop sequences."
    )

    # Timeouts
    timeout_s: Optional[float] = Field(
        default=30.0, gt=0.0, description="Request timeout in seconds."
    )

    # Future-proofing knobs (not all backends will support these)
    seed: Optional[int] = Field(
        default=None, description="Determinism seed if backend supports it."
    )

    # Optional backend hints (kept generic; adapters may ignore)
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Backend-agnostic extra hints; adapters may ignore.",
    )


class Usage(BaseModel):
    """Token usage, when known."""

    model_config = ConfigDict(extra="ignore")

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class InferenceResult(BaseModel):
    """A single assistant completion result."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., description="Assistant message content.")
    finish_reason: FinishReason = Field(default="unknown")

    # Optional metadata for logging/observability
    usage: Optional[Usage] = None
    backend: Optional[str] = Field(
        default=None, description="Adapter/backend name (e.g., 'openllm', 'stub')."
    )
    model: Optional[str] = Field(
        default=None, description="Resolved model name/ID used by backend."
    )
    latency_ms: Optional[int] = Field(
        default=None, ge=0, description="End-to-end latency in milliseconds."
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Inference adapter interface

class InferenceBackend(ABC):
    """Abstract base class for inference adapters.

    This interface must remain backend-agnostic and stateless with respect to
    Plexa session authority. Adapters may hold configuration (e.g., base_url),
    but must not own or mutate Plexa session state.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable adapter name used for logging and debugging."""

    @abstractmethod
    def generate(self, messages: List["Message"], config: InferenceConfig) -> InferenceResult:
        """Generate the next assistant message.

        Args:
            messages: Canonical ordered message history to provide as context.
            config: Frozen inference parameters (lesson-defined).

        Returns:
            InferenceResult containing assistant content and optional metadata.

        Raises:
            InferenceError: Any backend failure must be normalized to this family.
        """

    def health_check(self) -> bool:
        """Best-effort backend readiness check.

        Default is optimistic (True). Real backends should override with a ping.
        Stub backends can keep the default or return True explicitly.
        """
        return True


# Type-only import to avoid runtime import cycles.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from plexa_server.models.message import Message
