#!/usr/bin/env python3
"""
lesson_generator.py

A backend-agnostic "content compiler" for Plexa lessons.

- Takes a flat input dict (or CLI args / JSON input),
- Isolates entries into category dicts (identity, intent, execution, constraints, reflection),
- Stores each category dict as a class attribute,
- Validates + sanity checks,
- Emits a structured lesson JSON object (and optionally writes it to disk).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional


# Helpers

def now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_spdx_like(s: str) -> bool:
    # Not a full SPDX validator; just catches the most common “lol what is this” cases.
    return bool(re.fullmatch(r"[A-Za-z0-9.\-+]+", s.strip()))


def extract_category(
    raw: Mapping[str, Any],
    keys: Iterable[str],
    *,
    required: Iterable[str] = (),
    drop_none: bool = True,
        ) -> Dict[str, Any]:
    """
    Pulls a subset of keys from `raw` into a new dict.

    - keys: all keys that belong to the category
    - required: subset of keys that must be present and non-empty
    - drop_none: if True, removes keys whose value is None

    This is intentionally dumb + deterministic.
    """
    out: Dict[str, Any] = {}
    for k in keys:
        if k in raw:
            out[k] = raw[k]
    if drop_none:
        out = {k: v for k, v in out.items() if v is not None}

    missing = []
    for rk in required:
        if rk not in out or out[rk] in ("", [], {}, None):
            missing.append(rk)
    if missing:
        raise ValueError(f"Missing required fields in category: {missing}")

    return out


def clamp_float(name: str, v: float, lo: float, hi: float) -> float:
    if not (lo <= v <= hi):
        raise ValueError(f"{name} must be in [{lo}, {hi}] but got {v}")
    return v


def clamp_int(name: str, v: int, lo: int, hi: int) -> int:
    if not (lo <= v <= hi):
        raise ValueError(f"{name} must be in [{lo}, {hi}] but got {v}")
    return v


# Schema keys (v0.1)

IDENTITY_KEYS = (
    "lesson_id",
    "version",
    "title",
    "author",
    "course",
    "unit",
    "license",
    "created_at",
    "tags",
)

INTENT_KEYS = (
    "learning_objective",
    "behavioral_focus",
    "discipline",
    "difficulty",
    "prerequisites",
    "approximate_time"
)

EXECUTION_KEYS = (
    "system_prompt",
    "initial_assistant_message",
    "model_profile",
    "parameters",
    "capabilities",
)

CONSTRAINTS_KEYS = (
    "input_mode",
    "turn_limit",
    "allowed_actions",
    "termination_condition",
)

REFLECTION_KEYS = (
    "reflection_prompts",
    "reflection_timing",
    "logging_policy",
    "attached_metadata",
)

DEFAULT_REQUIRED = {
    "identity": ("version", "title", "author", "license"),
    "intent": ("learning_objective", "behavioral_focus"),
    "execution": ("system_prompt", "model_profile"),
    "constraints": ("input_mode",),
    "reflection": ("reflection_prompts",),
}


# Core class

@dataclass
class LessonSpec:
    """
    Stores each category as its own dict attribute, created from a flat raw input.

    The JSON generator uses these dicts to build the structured lesson object.
    """
    raw: Dict[str, Any]
    schema_version: str = "0.1"

    identity: Dict[str, Any] = field(init=False, default_factory=dict)
    intent: Dict[str, Any] = field(init=False, default_factory=dict)
    execution_envelope: Dict[str, Any] = field(init=False, default_factory=dict)
    interaction_constraints: Dict[str, Any] = field(init=False, default_factory=dict)
    reflection_and_logging: Dict[str, Any] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        # 1) Build category dicts via helper
        self.identity = extract_category(
            self.raw,
            IDENTITY_KEYS,
            required=DEFAULT_REQUIRED["identity"],
        )
        self.intent = extract_category(
            self.raw,
            INTENT_KEYS,
            required=DEFAULT_REQUIRED["intent"],
        )
        self.execution_envelope = extract_category(
            self.raw,
            EXECUTION_KEYS,
            required=DEFAULT_REQUIRED["execution"],
        )
        self.interaction_constraints = extract_category(
            self.raw,
            CONSTRAINTS_KEYS,
            required=DEFAULT_REQUIRED["constraints"],
        )
        self.reflection_and_logging = extract_category(
            self.raw,
            REFLECTION_KEYS,
            required=DEFAULT_REQUIRED["reflection"],
        )

        # 2) Fill defaults that must exist if omitted
        self._apply_defaults()

        # 3) Sanity checks
        self._validate()

        # 4) Attach minimal metadata defaults (stable fields)
        self._normalize_metadata()

    def _apply_defaults(self) -> None:
        # Identity defaults
        if "lesson_id" not in self.identity:
            self.identity["lesson_id"] = str(uuid.uuid4())
        if "created_at" not in self.identity:
            self.identity["created_at"] = now_iso_utc()
        if "tags" in self.identity and isinstance(self.identity["tags"], str):
            # allow comma-separated string
            self.identity["tags"] = [t.strip() for t in self.identity["tags"].split(",") if t.strip()]

        # Execution defaults
        self.execution_envelope.setdefault("parameters", {})
        self.execution_envelope.setdefault("capabilities", {"tools_enabled": False, "browsing_enabled": False})

        # Constraints defaults
        self.interaction_constraints.setdefault("turn_limit", None)
        self.interaction_constraints.setdefault("allowed_actions", None)
        self.interaction_constraints.setdefault("termination_condition", None)

        # Reflection defaults
        self.reflection_and_logging.setdefault("reflection_timing", "post")
        self.reflection_and_logging.setdefault("logging_policy", {
            "transcript_logged": True,
            "metadata_logged": True,
            "anonymization_level": "basic",
        })
        self.reflection_and_logging.setdefault("attached_metadata", {})

    def _validate(self) -> None:
        # Identity
        if not is_spdx_like(str(self.identity.get("license", ""))):
            raise ValueError(f"license should look like an SPDX identifier (got {self.identity.get('license')!r})")

        # Intent
        difficulty = self.intent.get("difficulty")
        if difficulty is not None:
            allowed = {"introductory", "intermediate", "advanced", "intro", "mid", "high"}
            if str(difficulty).lower() not in allowed:
                raise ValueError(f"difficulty must be one of {sorted(allowed)} (got {difficulty!r})")

        discipline = self.intent.get("discipline")
        if discipline is not None and not isinstance(discipline, (list, tuple, str)):
            raise ValueError("discipline must be a string or list of strings")

        # Execution envelope
        params = self.execution_envelope.get("parameters", {})
        if not isinstance(params, dict):
            raise ValueError("parameters must be a dict")

        # Sanity ranges (tweak as needed)
        if "temperature" in params:
            params["temperature"] = clamp_float("parameters.temperature", float(params["temperature"]), 0.0, 2.0)
        if "top_p" in params:
            params["top_p"] = clamp_float("parameters.top_p", float(params["top_p"]), 0.0, 1.0)
        if "max_tokens" in params:
            params["max_tokens"] = clamp_int("parameters.max_tokens", int(params["max_tokens"]), 1, 8192)
        if "context_window" in params:
            params["context_window"] = clamp_int("parameters.context_window", int(params["context_window"]), 256, 200000)

        caps = self.execution_envelope.get("capabilities", {})
        if not isinstance(caps, dict):
            raise ValueError("capabilities must be a dict")
        for k in ("tools_enabled", "browsing_enabled"):
            if k in caps and not isinstance(caps[k], bool):
                raise ValueError(f"capabilities.{k} must be boolean")

        # Interaction constraints
        input_mode = str(self.interaction_constraints.get("input_mode", "")).lower()
        if input_mode not in {"free", "guided", "fixed"}:
            raise ValueError("input_mode must be one of: free, guided, fixed")

        turn_limit = self.interaction_constraints.get("turn_limit")
        if turn_limit is not None:
            self.interaction_constraints["turn_limit"] = clamp_int("turn_limit", int(turn_limit), 1, 100)

        # Reflection
        rps = self.reflection_and_logging.get("reflection_prompts")
        if not isinstance(rps, list) or not all(isinstance(x, str) and x.strip() for x in rps):
            raise ValueError("reflection_prompts must be a non-empty list of non-empty strings")

        timing = str(self.reflection_and_logging.get("reflection_timing", "post")).lower()
        if timing not in {"post", "mid", "mixed"}:
            raise ValueError("reflection_timing must be one of: post, mid, mixed")

    def _normalize_metadata(self) -> None:
        """
        Ensure attached_metadata contains stable minimal identifiers.
        instance_id is intentionally NOT generated here (that’s runtime/instantiation).
        """
        meta = self.reflection_and_logging.setdefault("attached_metadata", {})
        if not isinstance(meta, dict):
            raise ValueError("attached_metadata must be a dict")

        meta.setdefault("lesson_id", self.identity["lesson_id"])
        meta.setdefault("lesson_version", self.identity["version"])


    # JSON building + output

    def to_json_obj(self) -> Dict[str, Any]:
        """
        Builds the structured JSON object with category top-level keys.
        """
        return {
            "schema_version": self.schema_version,
            "identity": self.identity,
            "pedagogical_intent": self.intent,
            "execution_envelope": self.execution_envelope,
            "interaction_constraints": self.interaction_constraints,
            "reflection_and_logging": self.reflection_and_logging,
        }

    def to_json_str(self, *, pretty: bool = True) -> str:
        obj = self.to_json_obj()
        if pretty:
            return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False)
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

    def write_json(self, path: str | Path, *, pretty: bool = True, overwrite: bool = False) -> Path:
        out_path = Path(path)
        if out_path.exists() and not overwrite:
            raise FileExistsError(f"Refusing to overwrite existing file: {out_path}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(self.to_json_str(pretty=pretty), encoding="utf-8")
        return out_path


# CLI

def _load_raw_input(input_json_path: Path) -> Dict[str, Any]:
    data = json.loads(input_json_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be a single JSON object (a dict at top-level).")
    return data


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a Plexa lesson JSON artifact from a flat input JSON dict."
    )
    parser.add_argument(
        "--in",
        dest="in_path",
        required=True,
        help="Path to a flat input JSON file (dict) of lesson parameters.",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        required=True,
        help="Path to write the generated lesson JSON file.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON (no pretty indentation).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output file if it exists.",
    )

    args = parser.parse_args()
    raw = _load_raw_input(Path(args.in_path))
    lesson = LessonSpec(raw=raw)
    lesson.write_json(args.out_path, pretty=(not args.compact), overwrite=args.overwrite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
