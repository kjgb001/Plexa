from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, UTC
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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


class InferenceConfigurationError(InferenceError):
    """Raised when inference profile or backend configuration is invalid."""


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

    # Lesson/runtime profile selection
    profile: str = Field(
        ...,
        validation_alias=AliasChoices("profile", "model"),
        description="Server-resolved inference profile identifier.",
    )

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
        default=None, gt=0.0, description="Optional lesson-level request timeout override."
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

    @property
    def model(self) -> str:
        """Compatibility alias for older code that still reads `config.model`."""
        return self.profile


class InferenceProfile(BaseModel):
    """Server-side runtime profile mapping for lesson-selected inference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    backend_id: str
    model: str
    temperature: Optional[float] = Field(default=None, ge=0.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    stop: Optional[List[str]] = None
    timeout_s: Optional[float] = Field(default=None, gt=0.0)
    seed: Optional[int] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class ResolvedInferenceConfig(BaseModel):
    """Concrete runtime configuration after profile resolution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: str
    backend_id: str
    backend_name: str
    model: str
    temperature: Optional[float] = Field(default=None, ge=0.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    stop: Optional[List[str]] = None
    timeout_s: Optional[float] = Field(default=None, gt=0.0)
    seed: Optional[int] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


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


class InferenceChunk(BaseModel):
    """Incremental assistant output from an inference backend."""

    model_config = ConfigDict(extra="forbid")

    content_delta: str = ""
    finish_reason: Optional[FinishReason] = None
    usage: Optional[Usage] = None
    backend: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[int] = Field(default=None, ge=0)


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
    async def generate(
        self,
        messages: List["Message"],
        config: ResolvedInferenceConfig,
    ) -> InferenceResult:
        """Generate the next assistant message.

        Args:
            messages: Canonical ordered message history to provide as context.
            config: Concrete runtime config after profile resolution.

        Returns:
            InferenceResult containing assistant content and optional metadata.

        Raises:
            InferenceError: Any backend failure must be normalized to this family.
        """

    async def stream(
        self,
        messages: List["Message"],
        config: ResolvedInferenceConfig,
    ) -> AsyncIterator[InferenceChunk]:
        """Stream a reply, falling back to one completed chunk by default."""
        result = await self.generate(messages, config)
        yield InferenceChunk(
            content_delta=result.content,
            finish_reason=result.finish_reason,
            usage=result.usage,
            backend=result.backend,
            model=result.model,
            latency_ms=result.latency_ms,
        )

    async def health_check(self) -> bool:
        """Best-effort backend readiness check.

        Default is optimistic (True). Real backends should override with a ping.
        Stub backends can keep the default or return True explicitly.
        """
        return True


# Type-only import to avoid runtime import cycles.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from plexa_server.models.message import Message
