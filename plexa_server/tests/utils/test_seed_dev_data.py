import asyncio

from plexa_server.core.sessions import SessionManager
from plexa_server.inference.stub import StubInference
from plexa_server.utils.dev_seed_data import SEEDED_COURSE_SPECS, SEEDED_LESSON_SPECS
from plexa_server.utils.seed_dev_data import seed_storages


def run(coro):
    return asyncio.run(coro)


def seeded_lesson_course_id(lesson_id: str) -> str:
    for course_spec in SEEDED_COURSE_SPECS:
        if lesson_id in course_spec["lesson_ids"]:
            title = course_spec["course_title"]
            return "CS101" if title == "default" else title
    raise AssertionError(f"No seeded course owns {lesson_id}.")


def test_seeded_lessons_have_distinct_goal_oriented_content(
    artifact_storage,
    course_storage,
):
    run(seed_storages(artifact_storage, course_storage))

    lessons = {
        lesson_id: run(
            artifact_storage.load_lesson(
                lesson_id,
                spec["version"],
                course_id=seeded_lesson_course_id(lesson_id),
            )
        )
        for lesson_id, spec in SEEDED_LESSON_SPECS.items()
    }
    assert all(lesson is not None for lesson in lessons.values())

    content_anchors = {
        "default": ("controlled-comparison", "vague request"),
        "The Danger of Hallucinations": (
            "source-grounded hallucination audit",
            "Unverified AI summary",
        ),
        "The Power of Prompt Engineering": (
            "prompt-design coach",
            "200-word orientation handout",
        ),
        "Managing Context Decay": (
            "context-management coach",
            "Workshop requirements",
        ),
        "Context Windows and Tradeoffs": (
            "context-window tradeoffs",
            "Original brief",
        ),
        "Prompt Engineering for Data Viz": (
            "data-visualization prompt coach",
            "| Month | Tickets",
        ),
        "LLM Assisted Data Evaluation": (
            "analytical-review coach",
            "| Cohort | Students",
        ),
    }

    system_prompts: set[str] = set()
    initial_messages: set[str] = set()
    learning_objectives: set[str] = set()
    behavioral_focuses: set[str] = set()
    for lesson_id, lesson in lessons.items():
        system_prompt = lesson.execution.system_prompt
        initial_message = lesson.execution.initial_assistant_message
        assert initial_message is not None
        assert system_prompt != "You are a helpful assistant."
        assert lesson.intent.learning_objective != "Understand model response patterns."
        assert lesson.intent.behavioral_focus != "Critical reasoning"
        assert initial_message.startswith("**Goal**\n")
        assert "\n\n**Deliverable**\n" in initial_message
        assert "\n\n**Start here**\n" in initial_message
        assert "Track the student's progress across the conversation" in system_prompt
        assert "begin with 'Goal complete.'" in system_prompt
        assert "Do not ask an open-ended 'what next' question" in system_prompt
        assert "do not claim the session is submitted" in system_prompt

        system_anchor, initial_anchor = content_anchors[lesson_id]
        assert system_anchor in system_prompt
        assert initial_anchor in initial_message

        system_prompts.add(system_prompt)
        initial_messages.add(initial_message)
        learning_objectives.add(lesson.intent.learning_objective)
        behavioral_focuses.add(lesson.intent.behavioral_focus)

    lesson_count = len(SEEDED_LESSON_SPECS)
    assert len(system_prompts) == lesson_count
    assert len(initial_messages) == lesson_count
    assert len(learning_objectives) == lesson_count
    assert len(behavioral_focuses) == lesson_count


def test_seeded_cs101_lessons_cover_user_reflection_states(
    artifact_storage,
    course_storage,
    session_storage,
):
    manager = SessionManager(storage=session_storage, inference_backend=StubInference())

    run(seed_storages(artifact_storage, course_storage))

    course = run(course_storage.get_course("CS101"))
    assert course is not None

    lessons = {
        lesson_id: run(artifact_storage.load_lesson(lesson_id, version, course_id="CS101"))
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
