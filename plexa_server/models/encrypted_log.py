from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


EncryptedLogEventType = Literal["created", "message_commit", "closed"]


class EncryptedLogMetadata(BaseModel):
    """Plaintext metadata describing an encrypted session log artifact."""

    instance_id: str
    user_id: str
    course_id: str
    lesson_id: str
    lesson_version: str
    course_owner_id: str
    authorized_instructor_ids: list[str] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None
    turned_in_at: datetime | None = None

    turn_count: int = 0
    is_active: bool = True

    log_version: int = 1
    artifact_sha256: str
    last_event_type: EncryptedLogEventType
    last_event_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    key_id: str
