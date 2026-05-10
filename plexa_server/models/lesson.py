from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import AliasChoices, BaseModel, Field, model_validator
from uuid import uuid4


# Identity

class LessonIdentity(BaseModel):
    """Versioned metadata that uniquely identifies a lesson artifact."""

    lesson_id: str = Field(default_factory=lambda: str(uuid4()))
    version: str
    title: str
    author: str
    course: Optional[str] = None
    unit: Optional[str] = None
    license: str
    created_at: Optional[datetime] = None
    tags: Optional[List[str]] = None


# Intent

class LessonIntent(BaseModel):
    """Learning goals and pedagogical framing for a lesson."""

    learning_objective: str
    behavioral_focus: str
    discipline: Optional[List[str]] = None
    difficulty: Optional[str] = None
    prerequisites: Optional[List[str]] = None
    approximate_time: Optional[str] = None


# Capabilities (Execution)

class LessonCapabilities(BaseModel):
    """Optional execution capabilities exposed to the lesson runtime."""

    tools_enabled: bool = False
    browsing_enabled: bool = False


# Execution

class LessonExecution(BaseModel):
    """Prompting and inference settings used to run a lesson."""

    system_prompt: str
    initial_assistant_message: Optional[str] = None
    profile: str = Field(
        validation_alias=AliasChoices("profile", "model_profile"),
        description="Server-resolved inference profile for lesson execution.",
    )
    parameters: Optional[Dict[str, Any]] = None
    capabilities: Optional[LessonCapabilities] = None


# Constraints

class LessonConstraints(BaseModel):
    """Interaction rules that bound a lesson session."""

    input_mode: str
    turn_limit: Optional[int] = None
    allowed_actions: Optional[List[str]] = None
    termination_condition: Optional[str] = None


# Reflection

class LessonReflection(BaseModel):
    """Post-lesson reflection prompts and logging metadata."""

    reflection_prompts: List[str]
    reflection_timing: Optional[str] = None
    logging_policy: Optional[str] = None
    attached_metadata: Optional[Dict[str, Any]] = None


# Top-level Lesson

class Lesson(BaseModel):
    """Top-level lesson document consumed by the runtime and API layers."""

    identity: LessonIdentity
    intent: LessonIntent
    execution: LessonExecution
    constraints: LessonConstraints
    reflection: LessonReflection

    schema_version: str = Field(default="1.0")

    @model_validator(mode="after")
    def validate_lesson(self) -> "Lesson":
        """Run cross-section validation for invariants spanning lesson sections.

        Returns:
            Lesson: The validated lesson instance.
        """
        return self
