from __future__ import annotations

from datetime import UTC, datetime

from plexa_server.inference.base import InferenceConfig
from plexa_server.models.session import Session


def build_session_log_payload(
    session: Session,
    inference_config: InferenceConfig | None = None,
) -> dict:
    """Build the canonical structured encrypted-log payload for a session.

    Args:
        session: Session whose runtime state should be logged.
        inference_config: Frozen inference config associated with the session.

    Returns:
        dict: JSON-serializable session log payload.
    """
    session_summary = session.model_dump(
        mode="json",
        exclude={
            "messages",
            "reflection_hooks",
            "lesson_snapshot",
            "frozen_inference_config",
        },
    )
    payload = {
        "schema_version": "1",
        "logged_at": datetime.now(UTC).isoformat(),
        "logging_policy": session.logging_policy,
        "session": session_summary,
    }
    if session.logging_policy == "default":
        payload["transcript"] = [
            message.model_dump(mode="json")
            for message in session.messages
            if message.role != "system"
        ]
        payload["reflections"] = [hook.model_dump(mode="json") for hook in session.reflection_hooks]
    if session.logging_policy == "default" and inference_config is not None:
        payload["inference_config"] = inference_config.model_dump(mode="json")
    return payload
