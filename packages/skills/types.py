#!/usr/bin/env python3
"""
Agentic Skills System - Types and Data Classes

Pure function tools for deterministic agentic evaluation.
Skills are immutable at runtime, have versioned schemas, and are
validated against a lockfile for reproducibility.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Protocol
from abc import ABC, abstractmethod
import json


# ── Core Types ────────────────────────────────────────────────────


@dataclass
class SkillContext:
    """Context passed to every skill invocation.

    Provides sandboxed access for skills. NO filesystem access
    outside the sandbox, NO network calls, NO dynamic creation.
    """

    # Environment info (read-only)
    working_directory: str = ""
    model_name: str = ""
    run_id: str = ""

    # Sandboxed state (skills can read/write within this dict only)
    sandbox: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_sandbox_path(self, relative_path: str) -> str:
        """Resolve a path within the sandbox. All file ops are sandbox-scoped."""
        import os

        base = self.sandbox.get("_sandbox_root", "/tmp/lmbench_sandbox")
        return os.path.join(base, relative_path)


@dataclass
class SkillInput:
    """Validated input to a skill invocation."""

    raw: Dict[str, Any]
    _validated: bool = False

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def validate(self, schema: Dict[str, Any]) -> List[str]:
        """Validate input against a JSON schema. Returns list of errors."""
        errors = []
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for field in required:
            if field not in self.raw:
                errors.append(f"Missing required field: {field}")

        for field, prop_schema in properties.items():
            if field in self.raw:
                expected_type = prop_schema.get("type")
                value = self.raw[field]
                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"Field '{field}' expected string, got {type(value).__name__}")
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Field '{field}' expected number, got {type(value).__name__}")
                elif expected_type == "array" and not isinstance(value, list):
                    errors.append(f"Field '{field}' expected array, got {type(value).__name__}")
                elif expected_type == "object" and not isinstance(value, dict):
                    errors.append(f"Field '{field}' expected object, got {type(value).__name__}")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Field '{field}' expected boolean, got {type(value).__name__}")

        if not errors:
            self._validated = True

        return errors


@dataclass
class SkillOutput:
    """Output from a skill invocation."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class Action:
    """A single action taken by a model during agentic evaluation."""

    skill: str
    input: Dict[str, Any]
    order: int = 0  # 0-based order in the sequence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill": self.skill,
            "input": self.input,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], order: int = 0) -> "Action":
        return cls(
            skill=data.get("skill", ""),
            input=data.get("input", {}),
            order=order,
        )


@dataclass
class AgenticResponse:
    """Expected model output format for agentic benchmarks."""

    actions: List[Action] = field(default_factory=list)

    @classmethod
    def from_json(cls, json_str: str) -> "AgenticResponse":
        """Parse a model's JSON response into an AgenticResponse."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return cls(actions=[])

        raw_actions = data.get("actions", [])
        if not isinstance(raw_actions, list):
            return cls(actions=[])

        return cls(actions=[Action.from_dict(a, i) for i, a in enumerate(raw_actions)])

    def to_json(self, indent: int = 2) -> str:
        return json.dumps({"actions": [a.to_dict() for a in self.actions]}, indent=indent)


# ── Skill Interface ───────────────────────────────────────────────


@dataclass
class SkillManifest:
    """Static manifest for a skill — versioned and immutable."""

    name: str
    version: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


class Skill(ABC):
    """Abstract base class for all skills.

    A Skill is a PURE FUNCTION TOOL:
    - Deterministic: same input → same output
    - Sandboxed: no filesystem/network access outside sandbox
    - Versioned: changes require version bump + lockfile update
    - Immutable: cannot be modified at runtime
    """

    def __init__(self):
        self._manifest: Optional[SkillManifest] = None

    @property
    def manifest(self) -> SkillManifest:
        if self._manifest is None:
            self._manifest = self._create_manifest()
        return self._manifest

    @abstractmethod
    def _create_manifest(self) -> SkillManifest:
        """Define the skill's manifest. Called once."""
        ...

    @abstractmethod
    async def run(self, input_data: SkillInput, ctx: SkillContext) -> SkillOutput:
        """Execute the skill with validated input and sandboxed context."""
        ...

    def validate_input(self, input_data: Dict[str, Any]) -> List[str]:
        """Validate raw input against the skill's input schema."""
        inp = SkillInput(raw=input_data)
        return inp.validate(self.manifest.input_schema)

    def to_dict(self) -> Dict[str, Any]:
        m = self.manifest
        return {
            "name": m.name,
            "version": m.version,
            "description": m.description,
            "input_schema": m.input_schema,
            "output_schema": m.output_schema,
            "tags": m.tags,
        }


# ── Agentic Scoring Types ─────────────────────────────────────────


@dataclass
class AgenticScore:
    """Scoring breakdown for agentic/tool-use evaluation."""

    # Validity: is the JSON well-formed, schema-compliant, using real skills?
    validity_score: float = 0.0
    json_valid: bool = False
    schema_valid: bool = False
    skills_exist: bool = False

    # Planning: is the sequence correct and minimal?
    planning_score: float = 0.0
    correct_sequence: bool = False
    unnecessary_steps: int = 0

    # Skill correctness: correct tool chosen, correct parameters?
    skill_correctness_score: float = 0.0
    correct_tool_choices: int = 0
    total_tool_choices: int = 0
    correct_parameters: int = 0
    total_parameters: int = 0

    # Constraint adherence: respects allowed skills, no hallucinations?
    constraint_adherence_score: float = 0.0
    skills_in_allowlist: int = 0
    skills_outside_allowlist: int = 0
    hallucinated_skills: List[str] = field(default_factory=list)

    # Aggregate
    overall_agentic_score: float = 0.0

    def compute_overall(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Compute weighted overall agentic score.

        Default weights:
        - validity: 0.25
        - planning: 0.25
        - skill_correctness: 0.30
        - constraint_adherence: 0.20
        """
        w = weights or {
            "validity": 0.25,
            "planning": 0.25,
            "skill_correctness": 0.30,
            "constraint_adherence": 0.20,
        }

        self.overall_agentic_score = (
            self.validity_score * w["validity"]
            + self.planning_score * w["planning"]
            + self.skill_correctness_score * w["skill_correctness"]
            + self.constraint_adherence_score * w["constraint_adherence"]
        )
        return self.overall_agentic_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validity_score": self.validity_score,
            "json_valid": self.json_valid,
            "schema_valid": self.schema_valid,
            "skills_exist": self.skills_exist,
            "planning_score": self.planning_score,
            "correct_sequence": self.correct_sequence,
            "unnecessary_steps": self.unnecessary_steps,
            "skill_correctness_score": self.skill_correctness_score,
            "correct_tool_choices": self.correct_tool_choices,
            "total_tool_choices": self.total_tool_choices,
            "correct_parameters": self.correct_parameters,
            "total_parameters": self.total_parameters,
            "constraint_adherence_score": self.constraint_adherence_score,
            "skills_in_allowlist": self.skills_in_allowlist,
            "skills_outside_allowlist": self.skills_outside_allowlist,
            "hallucinated_skills": self.hallucinated_skills,
            "overall_agentic_score": self.overall_agentic_score,
        }
