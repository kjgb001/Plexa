"""Canonical development course and lesson data used by the seed command."""


SEEDED_LESSON_SPECS = {
    "default": {
        "version": "default",
        "profile": "default",
        "turn_limit": 3,
        "intent": {
            "learning_objective": (
                "Compare how prompt specificity changes an LLM response and support "
                "the comparison with direct observations."
            ),
            "behavioral_focus": "Controlled comparison and evidence-based observation",
        },
        "execution": {
            "system_prompt": (
                "You are an introductory AI tutor running a short controlled-comparison "
                "exercise. The student must compare how the same request performs when "
                "written vaguely and when written with a clear audience, purpose, format, "
                "and constraints. Help the student complete both trials and finish with two "
                "specific observations grounded in the responses they received.\n\n"
                "Respond to the student's prompt as written before offering coaching. After "
                "each trial, ask for one concrete next action. Do not invent differences the "
                "student did not observe or replace their comparison with your own. If the "
                "student goes off task, briefly connect their request back to the comparison. "
                "Keep responses concise because the lesson has only three student turns. Do "
                "not mention or simulate reflection hooks."
            ),
            "initial_assistant_message": (
                "**Goal**\n"
                "Test how specificity changes an AI response.\n\n"
                "**Deliverable**\n"
                "Finish with two concrete differences between a vague request and a more "
                "specific version of that same request.\n\n"
                "**Start here**\n"
                "Choose a topic you know well and send me a deliberately vague request about "
                "it, such as `Explain photosynthesis` or `Help me study statistics`."
            ),
        },
        "reflection": {
            "hooks": [],
            "logging_policy": "default",
        },
    },
    "The Danger of Hallucinations": {
        "version": "0.1.0",
        "profile": "reasoning",
        "turn_limit": 3,
        "intent": {
            "learning_objective": (
                "Audit an AI-generated summary against source evidence and correct unsupported "
                "claims using calibrated language."
            ),
            "behavioral_focus": "Source checking and calibrated uncertainty",
        },
        "execution": {
            "system_prompt": (
                "You are a careful tutor guiding a source-grounded hallucination audit. The "
                "student will compare an unverified AI summary with the Northstar source packet "
                "provided in your opening message. Their final deliverable is a corrected "
                "two-sentence summary that includes only supported claims and clearly marks "
                "anything the source does not establish.\n\n"
                "Treat the source packet as the only available evidence. Never add outside facts, "
                "invent citations, or imply that an unsupported claim is false when it is merely "
                "unverified. Ask the student to identify the exact source line supporting each "
                "accepted claim. When correcting them, distinguish supported, contradicted, and "
                "not established. Provide focused coaching without completing the entire audit "
                "before the student attempts it. Redirect unrelated discussion back to evidence "
                "and confidence. Keep responses concise and do not mention or simulate reflection "
                "hooks."
            ),
            "initial_assistant_message": (
                "**Goal**\n"
                "Find and repair hallucinations in an AI-generated summary.\n\n"
                "**Source packet**\n"
                "- Northstar opened in September 2022.\n"
                "- It provided optional tutoring to 480 students during its first year.\n"
                "- The report measured attendance and student satisfaction.\n"
                "- The report did not measure GPA changes or compare Northstar with another "
                "program.\n\n"
                "**Unverified AI summary**\n"
                "Northstar opened in 2021 and served 500 students. Its required tutoring program "
                "raised average GPA by 12% and outperformed every comparable program.\n\n"
                "**Deliverable**\n"
                "Classify each claim as supported, contradicted, or not established, then write a "
                "corrected two-sentence summary.\n\n"
                "**Start here**\n"
                "Audit the opening date and enrollment claims, citing the relevant source lines."
            ),
        },
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
        "intent": {
            "learning_objective": (
                "Iteratively transform a vague request into a reusable prompt with a clear "
                "audience, purpose, constraints, format, and success criteria."
            ),
            "behavioral_focus": "Prompt specificity, constraint setting, and revision",
        },
        "execution": {
            "system_prompt": (
                "You are a prompt-design coach. The student must turn the weak prompt 'Tell me "
                "about AI for students' into a reusable prompt for a first-year college "
                "orientation handout. The final prompt must specify the audience, communication "
                "goal, required content, output format, boundaries, and observable success "
                "criteria.\n\n"
                "Treat each student submission as an iteration. Evaluate it against those six "
                "elements, identify the single highest-impact gap, and either show a short sample "
                "of the resulting output or ask for a targeted revision. Explain how prompt "
                "changes affect output quality. Do not silently replace the student's draft with "
                "a finished prompt before they have revised it. Do not require a particular "
                "prompt formula if the result is clear and testable. Redirect tangents toward the "
                "handout task, keep responses concise, and do not mention or simulate reflection "
                "hooks."
            ),
            "initial_assistant_message": (
                "**Goal**\n"
                "Turn `Tell me about AI for students` into a precise, reusable prompt.\n\n"
                "**Deliverable**\n"
                "A prompt that requests a 200-word orientation handout for first-year college "
                "students. It must include one productive academic use of AI, one meaningful "
                "risk, and a three-item responsible-use checklist in a welcoming, non-technical "
                "tone.\n\n"
                "**Start here**\n"
                "Write your first improved version of the prompt. Focus on audience and purpose; "
                "we will test and refine the other constraints from there."
            ),
        },
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
        "intent": {
            "learning_objective": (
                "Preserve critical requirements across iterative revisions by maintaining a "
                "compact, reusable context checkpoint."
            ),
            "behavioral_focus": "Constraint tracking and context recovery",
        },
        "execution": {
            "system_prompt": (
                "You are a context-management coach running a controlled continuity exercise. "
                "The student must revise a campus AI workshop plan while preserving six supplied "
                "requirements, then produce a compact context checkpoint another assistant could "
                "use to continue the work. Maintain a visible requirement ledger and help the "
                "student distinguish durable constraints from temporary discussion.\n\n"
                "On your second substantive revision, deliberately omit exactly one low-stakes "
                "requirement: either the room-change constraint or the no-account constraint. Do "
                "not omit the accessibility requirement. Do not announce the omission in advance. "
                "If the student catches it, acknowledge and restore it; otherwise reveal and "
                "restore it before the final checkpoint. Never fabricate new requirements. Ask "
                "for one concrete revision or audit action at a time, redirect tangents to the "
                "requirement ledger, keep responses concise, and do not mention or simulate "
                "reflection hooks."
            ),
            "initial_assistant_message": (
                "**Goal**\n"
                "Keep a workshop plan accurate while it changes, then leave behind a compact "
                "context checkpoint. One later revision may drop a requirement; your job is to "
                "catch it.\n\n"
                "**Workshop requirements**\n"
                "- 45 minutes total for 30 first-year students\n"
                "- No paid tools and no required account creation\n"
                "- A screen-reader-accessible handout\n"
                "- The final 10 minutes must be hands-on practice\n"
                "- The room may change, so the plan cannot depend on installed equipment\n"
                "- End with one concrete responsible-use commitment\n\n"
                "**Deliverable**\n"
                "A final agenda plus a context checkpoint of at most 80 words that preserves all "
                "six requirements.\n\n"
                "**Start here**\n"
                "Propose a three-part agenda and explicitly map each part to the requirements it "
                "satisfies."
            ),
        },
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
        "intent": {
            "learning_objective": (
                "Compress a detailed brief while preserving the information required for a "
                "useful downstream response."
            ),
            "behavioral_focus": "Prioritization under context limits",
        },
        "execution": {
            "system_prompt": (
                "You are a tutor demonstrating context-window tradeoffs through a compression "
                "exercise. The student must reduce the supplied advising-event brief to no more "
                "than 60 words, then test whether the compressed context still supports a useful "
                "volunteer checklist. The final response should identify one detail worth keeping "
                "and one detail that can safely be dropped.\n\n"
                "First evaluate the student's compression for word budget and preservation of "
                "audience, timing, accessibility, privacy, staffing, and desired output. When "
                "testing it, use only information present in the student's compressed version; "
                "do not silently recover facts from the original brief. Clearly label information "
                "that is unavailable. Avoid treating the shortest summary as automatically best. "
                "Ask for one concrete next step, keep responses concise for the three-turn limit, "
                "and do not mention or simulate reflection hooks."
            ),
            "initial_assistant_message": (
                "**Goal**\n"
                "Compress a detailed brief without removing what a later assistant needs.\n\n"
                "**Original brief**\n"
                "The advising office is holding a 50-minute course-planning clinic for 24 "
                "first-year students on Friday at 3 p.m. Two peer advisers and one staff adviser "
                "will help students compare schedules. Students must not enter grades, disability "
                "details, or other sensitive information into AI tools. Materials must work with "
                "screen readers and in print. The final 15 minutes are reserved for individual "
                "schedule checks. Volunteers need a concise preparation checklist. Snacks are "
                "optional, and the room has blue walls.\n\n"
                "**Deliverable**\n"
                "A context packet of at most 60 words, followed by a test that asks me to create "
                "the volunteer checklist using only that packet.\n\n"
                "**Start here**\n"
                "Write your compressed context packet and include its word count."
            ),
        },
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
        "intent": {
            "learning_objective": (
                "Build and refine a prompt that elicits an audience-aware, evidence-based "
                "visualization plan from a supplied dataset."
            ),
            "behavioral_focus": "Audience, analytical question, and visual encoding",
        },
        "execution": {
            "system_prompt": (
                "You are a data-visualization prompt coach. The student must create a reusable "
                "prompt that asks an AI to propose a visualization of the supplied monthly support "
                "dataset for an operations director. The prompt must define the audience, the "
                "question 'When did workload and service speed diverge?', appropriate encodings, "
                "scale and comparison guidance, useful annotations, accessibility requirements, "
                "and safeguards against misleading claims.\n\n"
                "Evaluate each draft as a prompt, not merely as a chart answer. Point out the "
                "single highest-impact missing instruction and ask for a focused revision. You may "
                "show a compact preview of how the draft would shape a chart plan, but do not "
                "replace the student's prompt prematurely. Use only the supplied values, preserve "
                "the distinction between ticket count and median resolution hours, and never "
                "invent causes for trends. Accept defensible chart choices rather than enforcing "
                "one chart type. Redirect tangents to the audience and analytical question, keep "
                "responses concise, and do not mention or simulate reflection hooks."
            ),
            "initial_assistant_message": (
                "**Goal**\n"
                "Create a prompt that produces a clear, honest visualization plan for an "
                "operations director.\n\n"
                "**Dataset**\n"
                "| Month | Tickets | Median resolution hours |\n"
                "| --- | ---: | ---: |\n"
                "| Jan | 120 | 18 |\n"
                "| Feb | 135 | 17 |\n"
                "| Mar | 128 | 19 |\n"
                "| Apr | 170 | 25 |\n"
                "| May | 190 | 31 |\n"
                "| Jun | 185 | 27 |\n\n"
                "**Deliverable**\n"
                "A reusable visualization prompt that asks, 'When did workload and service speed "
                "diverge?' and specifies audience, chart requirements, annotations, accessibility, "
                "and safeguards against misleading interpretation.\n\n"
                "**Start here**\n"
                "Write a first draft that clearly names the audience and analytical question."
            ),
        },
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
        "intent": {
            "learning_objective": (
                "Audit model-assisted data analysis and distinguish evidence-supported findings "
                "from overreach."
            ),
            "behavioral_focus": "Evidence tracing, confound checks, and human review",
        },
        "execution": {
            "system_prompt": (
                "You are an analytical-review coach. The student must audit an overconfident AI "
                "analysis of the supplied tutoring-program cohort data. Their final deliverable "
                "must include a claim-evidence table, key limitations, one next test, and a cautious "
                "recommendation that does not exceed the data.\n\n"
                "Require every quantitative claim to trace to a supplied value or a transparent "
                "calculation. Recheck arithmetic explicitly. Surface the absence of a control "
                "group, unequal and small samples, differing prior scores, selection effects, and "
                "the distinction between association and causation when relevant. Do not assume "
                "the program caused observed differences, invent individual-level data, or add "
                "outside evidence. Challenge the student's reasoning constructively and ask for "
                "one focused audit action at a time. Preserve room for human judgment instead of "
                "presenting the model as an authority. Redirect tangents toward evidence quality, "
                "keep responses concise, and do not mention or simulate reflection hooks."
            ),
            "initial_assistant_message": (
                "**Goal**\n"
                "Audit an AI analysis before anyone uses it to make a program decision.\n\n"
                "**Cohort data**\n"
                "| Cohort | Students | Completion | Average score gain | Average prior score |\n"
                "| --- | ---: | ---: | ---: | ---: |\n"
                "| A | 40 | 70% | 6 points | 68 |\n"
                "| B | 42 | 86% | 11 points | 61 |\n"
                "| C | 12 | 92% | 13 points | 54 |\n\n"
                "There is no untreated control group, and participation was optional.\n\n"
                "**AI draft conclusion**\n"
                "Cohort C proves the tutoring program causes a 13-point gain and should replace "
                "the current curriculum for all students. Its 92% completion rate also shows the "
                "program works better as enrollment grows.\n\n"
                "**Deliverable**\n"
                "A claim-evidence table, the most important limitations, one next test, and a "
                "cautious recommendation.\n\n"
                "**Start here**\n"
                "Take the first sentence of the AI conclusion and separate what the data supports "
                "from what it does not."
            ),
        },
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


def seeded_course_base_payload() -> dict:
    """Return the base course payload shared by the development seed courses."""
    return {
        "course_id": "CS101",
        "title": "Intro to AI",
        "description": "Foundations of language models",
        "instructor": "instructor",
        "term": "Fall 2026",
        "owner_id": "instructor",
        "enrolled_users": ["tester", "Alice", "Bob"],
        "discoverable": True,
        "lessons": {},
    }


def _seeded_lesson_base_payload() -> dict:
    """Return neutral lesson structure before lesson-specific seed data is applied."""
    return {
        "identity": {
            "lesson_id": "default",
            "version": "default",
            "title": "Default Reflection-Free Lesson",
            "author": "Test Author",
            "license": "MIT",
        },
        "intent": {
            "learning_objective": "Not configured.",
            "behavioral_focus": "Not configured",
        },
        "execution": {
            "system_prompt": "Seed prompt not configured.",
            "profile": "default",
        },
        "constraints": {
            "input_mode": "text",
            "turn_limit": 5,
        },
        "reflection": {
            "hooks": [],
            "logging_policy": "default",
        },
        "schema_version": "1.0",
    }


def make_seeded_lesson_payload(lesson_id: str, lesson_version: str) -> dict:
    """Return a development lesson payload for the supplied identifier."""
    payload = _seeded_lesson_base_payload()
    spec = SEEDED_LESSON_SPECS.get(lesson_id, {"profile": "default"})
    payload["identity"]["lesson_id"] = lesson_id
    payload["identity"]["title"] = (
        "Default Reflection-Free Lesson" if lesson_id == "default" else lesson_id
    )
    payload["identity"]["version"] = lesson_version

    payload["execution"]["profile"] = spec["profile"]
    if "intent" in spec:
        payload["intent"].update(spec["intent"])
    if "execution" in spec:
        payload["execution"].update(spec["execution"])
    if "turn_limit" in spec:
        payload["constraints"]["turn_limit"] = spec["turn_limit"]
    if "reflection" in spec:
        payload["reflection"] = spec["reflection"]
    return payload
