from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


EncryptedLogAccessAuditAction = Literal["metadata_list", "payload_read"]


class EncryptedLogAccessAuditEntry(BaseModel):
    """Audit record for instructor access to encrypted session logs."""

    audit_id: str
    requester_user_id: str
    course_id: str
    session_id: str | None = None
    lesson_id: str | None = None
    lesson_version: str | None = None
    target_user_id: str | None = None
    action: EncryptedLogAccessAuditAction
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
