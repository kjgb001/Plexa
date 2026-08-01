from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError, model_validator
from uuid import uuid4

from plexa_server.inference.base import InferenceConfig


# Identity

class LessonIdentity(BaseModel):
    """Versioned metadata that uniquely identifies a lesson artifact."""

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

    learning_objective: str
    behavioral_focus: str
    discipline: Optional[List[str]] = None
    difficulty: Optional[Literal["introductory", "intermediate", "advanced"]] = None
    prerequisites: Optional[List[str]] = None
    approximate_time: Optional[str] = None


# Capabilities (Execution)

class LessonCapabilities(BaseModel):
    """Optional execution capabilities exposed to the lesson runtime."""

    model_config = ConfigDict(extra="forbid")

    tools_enabled: bool = False
    browsing_enabled: bool = False


# Execution

class LessonExecution(BaseModel):
    """Prompting and inference settings used to run a lesson."""

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

    input_mode: str = "text"
    turn_limit: Optional[int] = None
    allowed_actions: Optional[List[str]] = None
    termination_condition: Optional[str] = None


# Reflection

class LessonReflection(BaseModel):
    """Ordered reflection hooks and logging metadata."""

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

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
        if not self.execution.system_prompt.strip():
            raise ValueError("System prompt cannot be empty.")
        if not self.execution.profile.strip():
            raise ValueError("Inference profile must be specified.")
        if self.constraints.turn_limit is None or self.constraints.turn_limit <= 0:
            raise ValueError("Lesson turn_limit must be a positive integer.")
        parameters = self.execution.parameters or {}
        try:
            InferenceConfig(
                model=self.execution.profile,
                temperature=parameters.get("temperature"),
                top_p=parameters.get("top_p"),
                max_tokens=parameters.get("max_tokens"),
                stop=parameters.get("stop"),
                timeout_s=parameters.get("timeout_s"),
                seed=parameters.get("seed"),
            )
        except ValidationError as exc:
            raise ValueError("Lesson execution parameters are invalid.") from exc
        for hook in self.reflection.hooks:
            if hook.phase == "mid" and hook.trigger_turn is None and self.constraints.turn_limit <= 1:
                raise ValueError("A mid reflection requires at least two lesson turns.")
            if (
                hook.phase == "mid"
                and hook.trigger_turn is not None
                and hook.trigger_turn >= self.constraints.turn_limit
            ):
                raise ValueError("Mid reflection hooks must trigger before the final turn.")
        return self
