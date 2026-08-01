from __future__ import annotations

from datetime import datetime, UTC
from typing import List

from plexa_server.models.lesson import Lesson
from plexa_server.models.message import Message
from plexa_server.inference.base import InferenceConfig


class LessonRuntimeError(Exception):
    """Raised when a lesson is structurally valid but not runnable."""
    pass


def validate_lesson_runtime(lesson: Lesson) -> None:
    """Validate that a lesson has the fields required for runtime execution.

    Args:
        lesson: Lesson document to validate before creating a session.

    Raises:
        LessonRuntimeError: If the lesson has an empty system prompt, an empty
            model profile, or a non-positive turn limit.
    """

    if not lesson.execution.system_prompt.strip():
        raise LessonRuntimeError("System prompt cannot be empty.")

    if not lesson.execution.profile.strip():
        raise LessonRuntimeError("Inference profile must be specified.")

    if lesson.constraints.turn_limit is not None:
        if lesson.constraints.turn_limit <= 0:
            raise LessonRuntimeError("Turn limit must be positive.")


def build_initial_messages(
    lesson: Lesson,
    session_id: str,
) -> List[Message]:
    """Build the initial transcript for a new session.

    Args:
        lesson: Lesson whose execution settings seed the transcript.
        session_id: Session identifier to assign to the generated messages.

    Returns:
        List[Message]: Ordered starting transcript containing the optional
        initial assistant message. The private system prompt is injected only
        when building server-side inference context.
    """

    messages: List[Message] = []

    if lesson.execution.initial_assistant_message:
        assistant_message = Message(
            message_id="assistant-0",
            session_id=session_id,
            role="assistant",
            content=lesson.execution.initial_assistant_message,
            created_at=datetime.now(UTC),
        )
        messages.append(assistant_message)

    return messages


def freeze_inference_config(lesson: Lesson) -> InferenceConfig:
    """Map lesson execution settings into an immutable inference config.

    Args:
        lesson: Lesson whose execution settings should be frozen for runtime use.

    Returns:
        InferenceConfig: Frozen inference parameters derived from the lesson.
    """

    params = lesson.execution.parameters or {}

    return InferenceConfig(
        model=lesson.execution.profile,
        temperature=params.get("temperature"),
        top_p=params.get("top_p"),
        max_tokens=params.get("max_tokens"),
        stop=params.get("stop"),
        timeout_s=params.get("timeout_s"),
        seed=params.get("seed"),
    )
