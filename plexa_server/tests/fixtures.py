from plexa_server.models.lesson import Lesson


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
