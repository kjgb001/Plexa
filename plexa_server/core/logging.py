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
    payload = {
        "schema_version": "1",
        "logged_at": datetime.now(UTC).isoformat(),
        "session": session.model_dump(mode="json"),
    }
    if inference_config is not None:
        payload["inference_config"] = inference_config.model_dump(mode="json")
    return payload
