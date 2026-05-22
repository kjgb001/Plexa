from typing import Optional, List, Dict, Any, Literal
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
    difficulty: Optional[Literal["introductory", "intermediate", "advanced"]] = None
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

    input_mode: str = "text"
    turn_limit: Optional[int] = None
    allowed_actions: Optional[List[str]] = None
    termination_condition: Optional[str] = None


# Reflection

class LessonReflection(BaseModel):
    """Ordered reflection hooks and logging metadata."""

    hooks: List["LessonReflectionHook"] = Field(default_factory=list)
    logging_policy: Optional[Literal["default", "metadata_only", "disabled"]] = None

    @model_validator(mode="after")
    def validate_hooks(self) -> "LessonReflection":
        """Ensure hook ordering and ids are coherent."""
        seen_ids: set[str] = set()
        normalized = sorted(self.hooks, key=lambda hook: (hook.order_index, hook.hook_id))
        for hook in normalized:
            if hook.hook_id in seen_ids:
                raise ValueError("Reflection hook ids must be unique within a lesson.")
            seen_ids.add(hook.hook_id)
        self.hooks = normalized
        return self


class LessonReflectionHook(BaseModel):
    """A structured reflection hook shown during or after a session."""

    hook_id: str = Field(default_factory=lambda: str(uuid4()))
    prompt: str
    phase: Literal["mid", "post"]
    order_index: int
    trigger_turn: Optional[int] = None
    carry_to_post: bool = False

    @model_validator(mode="after")
    def validate_hook(self) -> "LessonReflectionHook":
        """Ensure timing-specific fields are coherent."""
        if self.phase == "mid":
            if self.trigger_turn is not None and self.trigger_turn <= 0:
                raise ValueError("Mid reflection hooks must use a positive trigger_turn.")
            return self

        if self.trigger_turn is not None:
            raise ValueError("Post reflection hooks may not define trigger_turn.")
        if self.carry_to_post:
            raise ValueError("Post reflection hooks may not enable carry_to_post.")
        return self


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
