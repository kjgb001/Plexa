from __future__ import annotations

from datetime import datetime, UTC
from typing import List

from plexa_server.models.lesson import Lesson
from plexa_server.models.message import Message
from plexa_server.inference.base import InferenceConfig


class LessonRuntimeError(Exception):
    pass


def validate_lesson_runtime(lesson: Lesson) -> None:
    """
    Perform runtime validation beyond schema-level checks.
    """

    if not lesson.execution.system_prompt.strip():
        raise LessonRuntimeError("System prompt cannot be empty.")

    if not lesson.execution.model_profile.strip():
        raise LessonRuntimeError("Model profile must be specified.")

    if lesson.constraints.turn_limit is not None:
        if lesson.constraints.turn_limit <= 0:
            raise LessonRuntimeError("Turn limit must be positive.")


def build_initial_messages(
    lesson: Lesson,
    session_id: str,
) -> List[Message]:
    """
    Construct the deterministic initial message list.
    """

    messages: List[Message] = []

    system_message = Message(
        message_id="system-0",
        session_id=session_id,
        role="system",
        content=lesson.execution.system_prompt,
        created_at=datetime.now(UTC),
    )

    messages.append(system_message)

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
    """
    Convert lesson execution settings into a frozen InferenceConfig.
    """

    params = lesson.execution.parameters or {}

    return InferenceConfig(
        model=lesson.execution.model_profile,
        temperature=params.get("temperature"),
        top_p=params.get("top_p"),
        max_tokens=params.get("max_tokens"),
        stop=params.get("stop"),
        timeout_s=params.get("timeout_s", 30.0),
        seed=params.get("seed"),
    )
