from plexa_server.models.lesson import Lesson


SEEDED_LESSON_SPECS = {
    "default": {
        "version": "default",
        "profile": "default",
        "turn_limit": 3,
        "reflection": {
            "hooks": [],
            "logging_policy": "default",
        },
    },
    "The Danger of Hallucinations": {
        "version": "0.1.0",
        "profile": "reasoning",
        "turn_limit": 3,
        "reflection": {
            "hooks": [
                {
                    "hook_id": "hallucination-mid-check",
                    "prompt": "Pause and identify where the model showed uncertainty or overconfidence.",
                    "phase": "mid",
                    "order_index": 0,
                    "trigger_turn": 1,
                    "carry_to_post": False,
                },
                {
                    "hook_id": "hallucination-post-summary",
                    "prompt": "Summarize the strongest hallucination risk you observed.",
                    "phase": "post",
                    "order_index": 1,
                },
            ],
            "logging_policy": "default",
        },
    },
    "The Power of Prompt Engineering": {
        "version": "0.3.0",
        "profile": "default",
        "turn_limit": 5,
        "reflection": {
            "hooks": [
                {
                    "hook_id": "prompt-halfway-check",
                    "prompt": "At the midpoint, describe how your prompt changed the answer quality.",
                    "phase": "mid",
                    "order_index": 0,
                    "carry_to_post": False,
                },
            ],
            "logging_policy": "default",
        },
    },
    "Managing Context Decay": {
        "version": "0.2.0",
        "profile": "reasoning",
        "turn_limit": 4,
        "reflection": {
            "hooks": [
                {
                    "hook_id": "context-carry-forward",
                    "prompt": "If context degraded, explain what information should be restored before continuing.",
                    "phase": "mid",
                    "order_index": 0,
                    "trigger_turn": 2,
                    "carry_to_post": True,
                },
                {
                    "hook_id": "context-post-review",
                    "prompt": "Review how context management affected the final response.",
                    "phase": "post",
                    "order_index": 1,
                },
            ],
            "logging_policy": "default",
        },
    },
    "Context Windows and Tradeoffs": {
        "version": "0.1.0",
        "profile": "fast",
        "turn_limit": 3,
        "reflection": {
            "hooks": [
                {
                    "hook_id": "context-window-post",
                    "prompt": "What tradeoff did you see between concise context and useful context?",
                    "phase": "post",
                    "order_index": 0,
                },
            ],
            "logging_policy": "metadata_only",
        },
    },
    "Prompt Engineering for Data Viz": {
        "version": "0.2.0",
        "profile": "fast",
        "turn_limit": 6,
        "reflection": {
            "hooks": [
                {
                    "hook_id": "dataviz-prompt-mid-audience",
                    "prompt": "Pause and describe how your prompt clarified the chart audience.",
                    "phase": "mid",
                    "order_index": 0,
                    "trigger_turn": 1,
                    "carry_to_post": False,
                },
                {
                    "hook_id": "dataviz-prompt-mid-encoding",
                    "prompt": "What visual encoding instruction most improved the generated chart plan?",
                    "phase": "mid",
                    "order_index": 1,
                    "trigger_turn": 3,
                    "carry_to_post": False,
                },
                {
                    "hook_id": "dataviz-prompt-post-specificity",
                    "prompt": "Which prompt detail had the biggest effect on visualization quality?",
                    "phase": "post",
                    "order_index": 2,
                },
                {
                    "hook_id": "dataviz-prompt-post-revision",
                    "prompt": "What would you revise in your prompt before using it with a new dataset?",
                    "phase": "post",
                    "order_index": 3,
                },
            ],
            "logging_policy": "default",
        },
    },
    "LLM Assisted Data Evaluation": {
        "version": "0.4.0",
        "profile": "reasoning",
        "turn_limit": 8,
        "reflection": {
            "hooks": [
                {
                    "hook_id": "llm-data-mid-claim-check",
                    "prompt": "Pause and identify one model claim that needs evidence from the data.",
                    "phase": "mid",
                    "order_index": 0,
                    "trigger_turn": 1,
                    "carry_to_post": False,
                },
                {
                    "hook_id": "llm-data-mid-missing-context",
                    "prompt": "What dataset context is missing or under-specified in the evaluation so far?",
                    "phase": "mid",
                    "order_index": 1,
                    "trigger_turn": 2,
                    "carry_to_post": False,
                },
                {
                    "hook_id": "llm-data-mid-bias-check",
                    "prompt": "Where might the model be over-weighting a pattern that is not actually supported?",
                    "phase": "mid",
                    "order_index": 2,
                    "trigger_turn": 3,
                    "carry_to_post": False,
                },
                {
                    "hook_id": "llm-data-mid-next-test",
                    "prompt": "What follow-up test would you ask for before trusting the evaluation?",
                    "phase": "mid",
                    "order_index": 3,
                    "trigger_turn": 4,
                    "carry_to_post": False,
                },
                {
                    "hook_id": "llm-data-post-evidence",
                    "prompt": "Which final conclusion was best supported by explicit evidence?",
                    "phase": "post",
                    "order_index": 4,
                },
                {
                    "hook_id": "llm-data-post-weakest-link",
                    "prompt": "What was the weakest part of the model-assisted evaluation?",
                    "phase": "post",
                    "order_index": 5,
                },
                {
                    "hook_id": "llm-data-post-human-review",
                    "prompt": "Where did human review add value beyond the model output?",
                    "phase": "post",
                    "order_index": 6,
                },
                {
                    "hook_id": "llm-data-post-next-workflow",
                    "prompt": "How would you change your workflow for the next model-assisted data task?",
                    "phase": "post",
                    "order_index": 7,
                },
            ],
            "logging_policy": "default",
        },
    },
}

SEEDED_COURSE_SPECS = [
    {
        "course_title": "default",
        "course_description": "default",
        "owner_id": "instructor",
        "instructor": "instructor",
        "lesson_ids": [
            "default",
            "The Danger of Hallucinations",
            "The Power of Prompt Engineering",
            "Managing Context Decay",
            "Context Windows and Tradeoffs",
        ],
        "lesson_timeline": [
            {
                "lesson_id": "The Danger of Hallucinations",
                "lesson_version": "0.1.0",
                "starts_at": "2026-01-01T00:00:00Z",
            }
        ],
    },
    {
        "course_title": "Data Visualization",
        "course_description": "Using AI for accelerated visualization",
        "owner_id": "instructor",
        "instructor": "instructor",
        "lesson_ids": [
            "Prompt Engineering for Data Viz",
            "LLM Assisted Data Evaluation",
        ],
        "lesson_timeline": [],
    },
    {
        "course_title": "AI Writing Studio",
        "course_description": "An empty course for portal navigation testing",
        "owner_id": "instructor",
        "instructor": "instructor",
        "lesson_ids": [],
        "lesson_timeline": [],
    },
    {
        "course_title": "Prompt Lab",
        "course_description": "An empty course for sidebar overflow testing",
        "owner_id": "instructor",
        "instructor": "instructor",
        "lesson_ids": [],
        "lesson_timeline": [],
    },
    {
        "course_title": "Reasoning Workshop",
        "course_description": "An empty course for instructor portal layout testing",
        "owner_id": "instructor",
        "instructor": "instructor",
        "lesson_ids": [],
        "lesson_timeline": [],
    },
]


def valid_course():
    return {
        "course_id": "CS101",
        "title": "Intro to AI",
        "description": "Foundations of language models",
        "instructor": "Dr. Test",
        "term": "Fall 2026",
        "owner_id": "ignored",
        "enrolled_users": ["tester","Alice", "Bob"],
        "discoverable": True,
        "lessons": {},
    }


def seeded_course_base_payload():
    payload = valid_course()
    payload["owner_id"] = "instructor"
    payload["instructor"] = "instructor"
    if "tester" not in payload["enrolled_users"]:
        payload["enrolled_users"].append("tester")
    return payload


def valid_lesson():
    return {
        "identity": {
            "lesson_id": "test",
            "version": "0.1.0",
            "title": "Introduction to LLM Behavior",
            "author": "Test Author",
            "license": "MIT",
        },
        "intent": {
            "learning_objective": "Understand model response patterns.",
            "behavioral_focus": "Critical reasoning",
        },
        "execution": {
            "system_prompt": "You are a helpful assistant.",
            "profile": "default",
        },
        "constraints": {
            "input_mode": "text",
            "turn_limit": 5,
        },
        "reflection": {
            "hooks": [
                {
                    "hook_id": "post-summary",
                    "prompt": "What did you learn?",
                    "phase": "post",
                    "order_index": 0,
                },
                {
                    "hook_id": "post-surprise",
                    "prompt": "What surprised you?",
                    "phase": "post",
                    "order_index": 1,
                },
            ]
        },
        "schema_version": "1.0"
    }


def make_valid_lesson_payload() -> Lesson:
    return {
        "identity": {
            "lesson_id": "test",
            "version": "0.1.0",
            "title": "Calibration Under Uncertainty",
            "author": "Kellan",
            "course": "Test",
            "unit": "1",
            "license": "MIT",
        },
        "intent": {
            "learning_objective": "Practice evaluating uncertainty and confidence.",
            "behavioral_focus": "calibration",
            "discipline": ["philosophy", "cs"],
            "difficulty": "introductory",
        },
        "execution": {
            "system_prompt": "You are a careful tutor. If uncertain, say so.",
            "profile": "reasoning",
            "parameters": {
                "temperature": 0.4,
                "top_p": 0.9,
                "max_tokens": 800,
            },
            "capabilities": {
                "tools_enabled": False,
                "browsing_enabled": False,
            },
        },
        "constraints": {
            "input_mode": "text",
            "turn_limit": 2,
        },
        "reflection": {
            "hooks": [
                {
                    "hook_id": "mid-checkpoint",
                    "prompt": "Pause and assess where uncertainty is being handled well so far.",
                    "phase": "mid",
                    "order_index": 0,
                    "trigger_turn": 1,
                    "carry_to_post": True,
                },
                {
                    "hook_id": "post-confidence",
                    "prompt": "Where did the model express uncertainty appropriately?",
                    "phase": "post",
                    "order_index": 1,
                },
                {
                    "hook_id": "post-overconfidence",
                    "prompt": "Where was it overconfident?",
                    "phase": "post",
                    "order_index": 2,
                },
            ],
            "logging_policy": "default",
        },
    }


def make_seeded_lesson_payload(lesson_id: str, lesson_version: str) -> dict:
    """Return a seeded lesson payload for the supplied lesson identifier."""
    payload = valid_lesson()
    spec = SEEDED_LESSON_SPECS.get(lesson_id, {"profile": "default"})
    payload["identity"]["lesson_id"] = lesson_id
    payload["identity"]["title"] = (
        "Default Reflection-Free Lesson" if lesson_id == "default" else lesson_id
    )
    payload["identity"]["version"] = lesson_version

    payload["execution"]["profile"] = spec["profile"]
    if "turn_limit" in spec:
        payload["constraints"]["turn_limit"] = spec["turn_limit"]
    if "reflection" in spec:
        payload["reflection"] = spec["reflection"]
    return payload
