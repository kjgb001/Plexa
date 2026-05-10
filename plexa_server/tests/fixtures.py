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
            "input_mode": "freeform",
            "turn_limit": 5,
        },
        "reflection": {
            "reflection_prompts": [
                "What did you learn?",
                "What surprised you?"
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
            "profile": "kl3m_safe",
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
            "reflection_prompts": [
                "Where did the model express uncertainty appropriately?",
                "Where was it overconfident?",
            ]
        },
    }
