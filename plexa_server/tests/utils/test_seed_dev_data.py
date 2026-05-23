import asyncio
from pathlib import Path

from plexa_server.core.sessions import SessionManager
from plexa_server.inference.stub import StubInference
from plexa_server.storage.filesystem import (
    FileSystemArtifactStorage,
    FileSystemCourseStorage,
    FileSystemSessionStorage,
)
from plexa_server.tests.fixtures import SEEDED_LESSON_SPECS
from plexa_server.utils.seed_dev_data import seed_storages


def run(coro):
    return asyncio.run(coro)


def test_seeded_cs101_lessons_cover_user_reflection_states(tmp_path: Path):
    artifact_storage = FileSystemArtifactStorage(tmp_path)
    course_storage = FileSystemCourseStorage(tmp_path)
    session_storage = FileSystemSessionStorage(tmp_path)
    manager = SessionManager(storage=session_storage, inference_backend=StubInference())

    run(seed_storages(artifact_storage, course_storage))

    course = run(course_storage.get_course("CS101"))
    assert course is not None

    lessons = {
        lesson_id: run(artifact_storage.load_lesson(lesson_id, version))
        for lesson_id, version in course.lessons.items()
    }
    expected_cs101_lessons = {
        "default",
        "The Danger of Hallucinations",
        "The Power of Prompt Engineering",
        "Managing Context Decay",
        "Context Windows and Tradeoffs",
    }
    assert set(lessons) == expected_cs101_lessons
    assert all(lesson is not None for lesson in lessons.values())
    assert all(
        lessons[lesson_id].identity.version == SEEDED_LESSON_SPECS[lesson_id]["version"]
        for lesson_id in expected_cs101_lessons
    )

    no_hooks = run(
        manager.create_session(
            session_id="seed-default",
            lesson=lessons["default"],
            user_id="tester",
            course_id="CS101",
        )
    )
    assert no_hooks.reflection_hooks == []
    no_hooks = run(manager.begin_completion(no_hooks.session_id))
    no_hooks = run(manager.turn_in_session(no_hooks.session_id))
    assert no_hooks.is_finalized is True

    explicit_mid = run(
        manager.create_session(
            session_id="seed-explicit-mid",
            lesson=lessons["The Danger of Hallucinations"],
            user_id="tester",
            course_id="CS101",
        )
    )
    run(manager.submit_user_message(explicit_mid.session_id, "m1", "Check hallucination risk."))
    explicit_mid = run(session_storage.get_session(explicit_mid.session_id))
    explicit_mid_hook = next(hook for hook in explicit_mid.reflection_hooks if hook.hook_id == "hallucination-mid-check")
    assert explicit_mid_hook.triggered_at is not None
    assert explicit_mid_hook.trigger_source == "mid_turn"
    explicit_mid = run(manager.begin_completion(explicit_mid.session_id))
    explicit_post_hook = next(hook for hook in explicit_mid.reflection_hooks if hook.hook_id == "hallucination-post-summary")
    assert explicit_post_hook.trigger_source == "soft_complete"

    default_mid = run(
        manager.create_session(
            session_id="seed-default-mid",
            lesson=lessons["The Power of Prompt Engineering"],
            user_id="tester",
            course_id="CS101",
        )
    )
    default_mid_hook = default_mid.reflection_hooks[0]
    assert default_mid_hook.hook_id == "prompt-halfway-check"
    assert default_mid_hook.trigger_turn == 3
    run(manager.submit_user_message(default_mid.session_id, "m1", "First prompt."))
    run(manager.submit_user_message(default_mid.session_id, "m2", "Second prompt."))
    default_mid = run(session_storage.get_session(default_mid.session_id))
    assert default_mid.reflection_hooks[0].triggered_at is None
    run(manager.submit_user_message(default_mid.session_id, "m3", "Third prompt."))
    default_mid = run(session_storage.get_session(default_mid.session_id))
    assert default_mid.reflection_hooks[0].trigger_source == "mid_turn"

    carried_mid = run(
        manager.create_session(
            session_id="seed-carried-mid",
            lesson=lessons["Managing Context Decay"],
            user_id="tester",
            course_id="CS101",
        )
    )
    carried_mid = run(manager.begin_completion(carried_mid.session_id))
    carried_hook = next(hook for hook in carried_mid.reflection_hooks if hook.hook_id == "context-carry-forward")
    carried_post_hook = next(hook for hook in carried_mid.reflection_hooks if hook.hook_id == "context-post-review")
    assert carried_hook.carried_to_post is True
    assert carried_hook.trigger_source == "carry_to_post"
    assert carried_post_hook.trigger_source == "soft_complete"
    assert carried_hook.trigger_turn == 2

    metadata_only = run(
        manager.create_session(
            session_id="seed-metadata-only",
            lesson=lessons["Context Windows and Tradeoffs"],
            user_id="tester",
            course_id="CS101",
        )
    )
    assert metadata_only.logging_policy == "metadata_only"
    assert metadata_only.reflection_hooks[0].hook_id == "context-window-post"
    metadata_only = run(manager.begin_completion(metadata_only.session_id))
    assert metadata_only.reflection_hooks[0].trigger_source == "soft_complete"
