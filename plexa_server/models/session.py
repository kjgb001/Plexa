from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, UTC
from uuid import uuid4

from plexa_server.models.message import Message
from plexa_server.models.lesson import Lesson
from plexa_server.inference.base import InferenceConfig


class SessionReflectionHook(BaseModel):
    """Frozen reflection hook state attached to a session."""

    hook_id: str
    prompt: str
    phase: Literal["mid", "post"]
    order_index: int
    trigger_turn: int | None = None
    carry_to_post: bool = False
    carried_to_post: bool = False
    triggered_at: datetime | None = None
    trigger_source: Literal["mid_turn", "soft_complete", "carry_to_post"] | None = None
    postponed_at: datetime | None = None
    response_text: str | None = None
    first_answered_at: datetime | None = None
    last_updated_at: datetime | None = None


class Session(BaseModel):
    """Persisted state for a user's lesson conversation."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = "Untitled session"
    user_id: str

    lesson_id: str
    lesson_version: str
    course_id: str

    messages: List[Message] = Field(default_factory=list)
    lesson_snapshot: Lesson | None = None
    frozen_inference_config: InferenceConfig | None = None
    lesson_artifact_revision: int = 1
    lesson_content_sha256: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    closed_at: Optional[datetime] = None

    turn_count: int = 0
    max_turns: Optional[int] = None

    is_active: bool = True
    is_completion_started: bool = False
    completed_at: Optional[datetime] = None
    is_finalized: bool = False
    turned_in_at: Optional[datetime] = None
    logging_policy: Literal["default", "metadata_only", "disabled"] = "default"
    transcript_available: bool = True
    transcript_unavailable_reason: str | None = None
    persistence_revision: int = 0
    reflection_hooks: List[SessionReflectionHook] = Field(default_factory=list)
