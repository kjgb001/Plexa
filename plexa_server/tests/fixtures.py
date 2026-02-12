from plexa_server.models.lesson import Lesson

def make_valid_lesson_payload() -> Lesson:
    return {
        "identity": {
            "version": "0.1.0",
            "title": "Calibration Under Uncertainty",
            "author": "Kellan",
            "course": "Test",
            "unit": "1",
            "license": "MIT",
            "lesson_id": "83432ad8-454d-4d7b-9114-07ac37926ca0"
        },
        "intent": {
            "learning_objective": "Practice evaluating uncertainty and confidence.",
            "behavioral_focus": "calibration",
            "discipline": ["philosophy", "cs"],
            "difficulty": "introductory",
        },
        "execution": {
            "system_prompt": "You are a careful tutor. If uncertain, say so.",
            "model_profile": "kl3m_safe",
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
            "turn_limit": 8,
        },
        "reflection": {
            "reflection_prompts": [
                "Where did the model express uncertainty appropriately?",
                "Where was it overconfident?",
            ]
        },
    }