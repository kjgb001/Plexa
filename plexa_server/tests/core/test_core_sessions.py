import asyncio
from copy import deepcopy
import pytest
from datetime import datetime, UTC

from plexa_server.inference.stub import StubInference
from plexa_server.inference.base import InferenceError, InferenceProfile
from plexa_server.inference.routing import InferenceRegistry, InferenceRouter
from plexa_server.core.sessions import (
    SessionManager,
    SessionClosedError,
    TurnLimitExceededError,
    SessionCompletionError,
)
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
from plexa_server.tests.fixtures import make_valid_lesson_payload


def run(coro):
    return asyncio.run(coro)


def answer_triggered_mid_reflections(manager, storage, session_id: str):
    session = run(storage.get_session(session_id))
    for hook in session.reflection_hooks:
        if hook.phase == "mid" and hook.triggered_at is not None and not (hook.response_text or "").strip():
            run(manager.save_reflection_response(session_id, hook.hook_id, f"Response for {hook.hook_id}"))


def test_create_session(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    session = run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    assert session.session_id == "s1"
    assert session.turn_count == 0
    assert session.is_active is True
    assert session.title.startswith("New session ")
    assert run(storage.get_session("s1")) is not None


def test_turn_increment_and_message_append(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    assistant_message = run(manager.submit_user_message(
        session_id="s1",
        message_id="m1",
        content="Hello world",
    ))

    session = run(storage.get_session("s1"))

    assert session.turn_count == 1
    assert len(session.messages) == 3
    assert session.title == "Hello world"
    assert session.messages[0].role == "system"
    assert session.messages[1].role == "user"
    assert session.messages[2].role == "assistant"
    assert assistant_message.role == "assistant"


def test_mid_reflection_triggers_after_configured_turn(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    run(manager.submit_user_message(
        session_id="s1",
        message_id="m1",
        content="Hello world",
    ))

    session = run(storage.get_session("s1"))
    hook = next(item for item in session.reflection_hooks if item.hook_id == "mid-checkpoint")

    assert hook.triggered_at is not None
    assert hook.trigger_source == "mid_turn"


def test_mid_reflection_without_trigger_turn_defaults_to_halfway(setup_manager, storage_backend):
    manager, storage = setup_manager()
    payload = make_valid_lesson_payload()
    payload["constraints"] = payload["constraints"].copy()
    payload["constraints"]["turn_limit"] = 5
    payload["reflection"] = payload["reflection"].copy()
    payload["reflection"]["hooks"] = [
        {
            "hook_id": "mid-halfway",
            "prompt": "How is the session going?",
            "phase": "mid",
            "order_index": 0,
        }
    ]
    lesson = Lesson.model_validate(payload)

    session = run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    assert session.reflection_hooks[0].trigger_turn == 3

    run(manager.submit_user_message("s1", "m1", "First turn"))
    run(manager.submit_user_message("s1", "m2", "Second turn"))
    session = run(storage.get_session("s1"))
    assert session.reflection_hooks[0].triggered_at is None

    run(manager.submit_user_message("s1", "m3", "Third turn"))
    session = run(storage.get_session("s1"))
    assert session.reflection_hooks[0].triggered_at is not None
    assert session.reflection_hooks[0].trigger_source == "mid_turn"


def test_carry_forward_mid_reflection_does_not_trigger_on_final_turn(setup_manager, storage_backend):
    manager, storage = setup_manager()
    payload = make_valid_lesson_payload()
    payload["constraints"] = payload["constraints"].copy()
    payload["constraints"]["turn_limit"] = 2
    payload["reflection"] = payload["reflection"].copy()
    payload["reflection"]["hooks"] = [
        {
            "hook_id": "final-carry",
            "prompt": "Carry this if it would otherwise appear at the end.",
            "phase": "mid",
            "order_index": 0,
            "trigger_turn": 2,
            "carry_to_post": True,
        }
    ]
    lesson = Lesson.model_validate(payload)

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    run(manager.submit_user_message("s1", "m1", "First turn"))
    run(manager.submit_user_message("s1", "m2", "Final turn"))
    session = run(storage.get_session("s1"))
    assert session.is_active is False
    assert session.is_completion_started is True
    assert session.reflection_hooks[0].trigger_source == "carry_to_post"
    assert session.reflection_hooks[0].carried_to_post is True


def test_turn_limit_auto_completion_triggers_post_reflections(setup_manager, storage_backend):
    manager, storage = setup_manager()
    payload = make_valid_lesson_payload()
    payload["reflection"] = payload["reflection"].copy()
    payload["reflection"]["hooks"] = [
        {
            "hook_id": "post-final",
            "prompt": "What did this completed session show?",
            "phase": "post",
            "order_index": 0,
        }
    ]
    lesson = Lesson.model_validate(payload)

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    run(manager.submit_user_message("s1", "m1", "First turn"))
    session = run(storage.get_session("s1"))
    assert session.is_completion_started is False
    assert session.reflection_hooks[0].triggered_at is None

    run(manager.submit_user_message("s1", "m2", "Final turn"))
    session = run(storage.get_session("s1"))
    assert session.is_active is False
    assert session.is_completion_started is True
    assert session.completed_at is not None
    assert session.reflection_hooks[0].trigger_source == "soft_complete"


def test_completion_requires_triggered_reflections_before_turn_in(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    session = run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    assert session.is_completion_started is False
    assert session.is_finalized is False

    session = run(manager.begin_completion("s1"))

    assert session.is_completion_started is True
    assert session.completed_at is not None
    assert all(hook.triggered_at is not None for hook in session.reflection_hooks)
    assert session.reflection_hooks[0].carried_to_post is True
    assert session.reflection_hooks[0].trigger_source == "carry_to_post"
    assert session.reflection_hooks[1].trigger_source == "soft_complete"

    with pytest.raises(SessionCompletionError):
        run(manager.turn_in_session("s1"))

    for hook in session.reflection_hooks:
        session = run(manager.save_reflection_response("s1", hook.hook_id, f"Response for {hook.hook_id}"))

    session = run(manager.turn_in_session("s1"))

    assert session.is_finalized is True
    assert session.is_active is False
    assert session.closed_at is not None
    assert session.turned_in_at is not None

    stored = run(storage.get_session("s1"))
    assert stored.is_finalized is True


def test_completion_backfills_missing_post_hooks_from_current_lesson(setup_manager, storage_backend):
    manager, storage = setup_manager()
    current_payload = make_valid_lesson_payload()
    stale_payload = deepcopy(current_payload)
    stale_payload["reflection"] = {"hooks": [], "logging_policy": "default"}

    stale_lesson = Lesson.model_validate(stale_payload)
    current_lesson = Lesson.model_validate(current_payload)

    session = run(manager.create_session(
        session_id="s1",
        lesson=stale_lesson,
        user_id="user-1",
        course_id="CS101"
    ))
    assert session.reflection_hooks == []

    session = run(manager.begin_completion("s1", current_lesson=current_lesson))

    post_hooks = [hook for hook in session.reflection_hooks if hook.phase == "post"]
    assert [hook.hook_id for hook in post_hooks] == ["post-confidence", "post-overconfidence"]
    assert all(hook.trigger_source == "soft_complete" for hook in post_hooks)

    stored = run(storage.get_session("s1"))
    assert len(stored.reflection_hooks) == 3


def test_pending_mid_reflection_blocks_next_message_until_answered(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    run(manager.submit_user_message("s1", "m1", "First turn"))
    session = run(storage.get_session("s1"))
    mid_hook = next(hook for hook in session.reflection_hooks if hook.phase == "mid")
    assert mid_hook.triggered_at is not None

    with pytest.raises(SessionCompletionError):
        run(manager.submit_user_message("s1", "m2", "Second turn"))

    run(manager.save_reflection_response("s1", mid_hook.hook_id, "Mid reflection response."))
    run(manager.submit_user_message("s1", "m2", "Second turn"))

    session = run(storage.get_session("s1"))
    assert session.turn_count == 2


def test_completion_can_resume_before_turn_in(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    run(manager.begin_completion("s1"))
    session = run(manager.resume_after_completion("s1"))

    assert session.is_completion_started is False
    assert session.completed_at is None
    assert session.is_active is True
    assert session.is_finalized is False
    assert all(hook.triggered_at is None for hook in session.reflection_hooks)
    assert all(hook.response_text is None for hook in session.reflection_hooks)

    stored = run(storage.get_session("s1"))
    assert stored.is_completion_started is False


def test_untriggered_reflection_response_is_rejected(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    session = run(storage.get_session("s1"))
    hook = next(item for item in session.reflection_hooks if item.hook_id == "post-confidence")

    with pytest.raises(SessionCompletionError):
        run(manager.save_reflection_response("s1", hook.hook_id, "Too early"))


def test_turn_limit_enforced(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    session = run(storage.get_session("s1"))

    for i in range(session.max_turns):
        run(manager.submit_user_message("s1", f"m{i}", f"Turn {i}"))
        answer_triggered_mid_reflections(manager, storage, "s1")

    session = run(storage.get_session("s1"))
    assert session.is_active is False
    assert session.turn_count == session.max_turns

    with pytest.raises(SessionClosedError):
        run(manager.submit_user_message("s1", "m2", "Second turn"))


def test_closed_session_rejects_messages(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    run(manager.close_session("s1"))

    with pytest.raises(SessionClosedError):
        run(manager.submit_user_message("s1", "m1", "Should fail"))


def test_atomic_rollback_on_inference_failure(setup_manager, storage_backend):
    class FailingInference(StubInference):
        async def generate(self, messages, config):
            raise InferenceError("Backend failure")

    inference = FailingInference()
    manager, storage = setup_manager(inference_backend=inference)

    lesson = Lesson.model_validate(make_valid_lesson_payload())
    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    with pytest.raises(InferenceError):
        run(manager.submit_user_message("s1", "m1", "Trigger failure"))

    session = run(storage.get_session("s1"))

    assert session.turn_count == 0
    assert len(session.messages) == 1
    assert session.is_active is True


def test_initial_system_message_injected(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    session = run(storage.get_session("s1"))

    assert len(session.messages) == 1
    assert session.messages[0].role == "system"
    assert session.messages[0].content == lesson.execution.system_prompt


def test_initial_assistant_message_injected(setup_manager, storage_backend):
    manager, storage = setup_manager()

    payload = make_valid_lesson_payload()
    payload["execution"]["initial_assistant_message"] = "Welcome student."

    lesson = Lesson.model_validate(payload)

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    session = run(storage.get_session("s1"))

    assert len(session.messages) == 2
    assert session.messages[0].role == "system"
    assert session.messages[1].role == "assistant"
    assert session.messages[1].content == "Welcome student."


def test_turn_limit_derived_from_lesson(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    session = run(storage.get_session("s1"))

    assert session.max_turns == lesson.constraints.turn_limit


def test_inference_config_frozen_and_stored(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    config = run(storage.get_inference_config("s1"))

    assert config.model == lesson.execution.profile

    if lesson.execution.parameters:
        assert config.temperature == lesson.execution.parameters.get("temperature")


def test_delete_session_removes_session_and_config(setup_manager, storage_backend):
    manager, storage = setup_manager()
    lesson = Lesson.model_validate(make_valid_lesson_payload())

    run(manager.create_session(
        session_id="s1",
        lesson=lesson,
        user_id="user-1",
        course_id="CS101"
    ))

    assert run(storage.get_session("s1")) is not None
    assert run(storage.get_inference_config("s1")) is not None

    run(manager.delete_session("s1"))

    assert run(storage.get_session("s1")) is None
    assert run(storage.get_inference_config("s1")) is None


def test_session_manager_routes_by_lesson_profile(
    session_storage,
    course_storage,
    artifact_storage,
    storage_backend,
):
    registry = InferenceRegistry()
    registry.register_backend("stub-a", StubInference())
    registry.register_backend("stub-b", StubInference())
    registry.register_profile(InferenceProfile(name="alpha", backend_id="stub-a", model="model-a"))
    registry.register_profile(InferenceProfile(name="beta", backend_id="stub-b", model="model-b"))
    router = InferenceRouter(registry)

    manager = SessionManager(storage=session_storage, inference_router=router)

    course = {
        "course_id": "CS101",
        "title": "Intro to AI",
        "description": "Routing test course",
        "owner_id": "test-owner",
        "instructor_ids": ["test-owner"],
        "enrolled_users": ["user-1"],
        "discoverable": True,
        "lessons": {},
    }
    run(course_storage.save_course(Course.model_validate(course)))

    alpha_payload = make_valid_lesson_payload()
    alpha_payload["execution"]["profile"] = "alpha"
    alpha_lesson = Lesson.model_validate(alpha_payload)
    run(artifact_storage.save_lesson(alpha_lesson))

    beta_payload = make_valid_lesson_payload()
    beta_payload["identity"]["lesson_id"] = "test-beta"
    beta_payload["execution"]["profile"] = "beta"
    beta_lesson = Lesson.model_validate(beta_payload)
    run(artifact_storage.save_lesson(beta_lesson))

    run(manager.create_session(
        session_id="alpha-session",
        lesson=alpha_lesson,
        user_id="user-1",
        course_id="CS101",
    ))
    run(manager.create_session(
        session_id="beta-session",
        lesson=beta_lesson,
        user_id="user-1",
        course_id="CS101",
    ))

    alpha_response = run(manager.submit_user_message("alpha-session", "m1", "hello alpha"))
    beta_response = run(manager.submit_user_message("beta-session", "m2", "hello beta"))

    assert "Model: model-a" in alpha_response.content
    assert "Model: model-b" in beta_response.content
