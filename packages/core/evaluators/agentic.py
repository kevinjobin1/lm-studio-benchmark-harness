#!/usr/bin/env python3
"""
Agentic Evaluator

Evaluates model tool-use responses across 4 scoring dimensions:
1. Validity (0-1): JSON valid, schema valid, skills exist
2. Planning (0-1): correct sequence, minimal steps
3. Skill Correctness (0-1): correct tool, correct parameters
4. Constraint Adherence (0-1): respects allowlist, no hallucinations

Pure evaluation only. Does NOT execute model-generated code.
"""

import json
import re
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from skills.types import Action, AgenticResponse, AgenticScore


@dataclass
class AgenticEvaluationResult:
    """Complete agentic evaluation result."""

    score: AgenticScore
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class AgenticEvaluator:
    """Evaluates model tool-use responses deterministically.

    Enforces hard constraints:
    - No execution of model-generated code
    - No real filesystem access outside sandbox
    - No network calls in core skills
    - No dynamic skill creation during runtime
    """

    def __init__(self, available_skills: List[str]):
        """
        Args:
            available_skills: Allowlist of skill names the model is allowed to use
        """
        self.allowlist: Set[str] = set(available_skills)

    def evaluate(
        self,
        raw_response: str,
        expected_actions: Optional[List[Action]] = None,
        expected_params: Optional[Dict[str, Dict]] = None,
    ) -> AgenticEvaluationResult:
        """Evaluate a model's agentic response.

        Args:
            raw_response: Raw model output (should be JSON with "actions" array)
            expected_actions: Ground-truth actions for planning comparison
            expected_params: Expected parameters per action (for correctness)

        Returns:
            AgenticEvaluationResult with full scoring breakdown
        """
        errors = []
        warnings = []
        score = AgenticScore()

        # ── 1. VALIDITY ──────────────────────────────────────────
        score.validity_score, resp = self._evaluate_validity(raw_response, errors)

        if resp is None:
            # Invalid JSON means everything else fails
            score.compute_overall()
            return AgenticEvaluationResult(score=score, errors=errors, warnings=warnings)

        actions = resp.actions

        # ── 2. PLANNING ─────────────────────────────────────────
        score.planning_score = self._evaluate_planning(actions, expected_actions, errors, warnings)

        # ── 3. SKILL CORRECTNESS ────────────────────────────────
        score.skill_correctness_score = self._evaluate_skill_correctness(
            actions, expected_params, score, errors
        )

        # ── 4. CONSTRAINT ADHERENCE ─────────────────────────────
        score.constraint_adherence_score = self._evaluate_constraints(actions, score, errors)

        # Compute overall
        score.compute_overall()

        return AgenticEvaluationResult(
            score=score,
            errors=errors,
            warnings=warnings,
            metadata={
                "total_actions": len(actions),
                "allowlist": sorted(self.allowlist),
            },
        )

    # ── 1. Validity ──────────────────────────────────────────────

    def _evaluate_validity(
        self, raw_response: str, errors: List[str]
    ) -> Tuple[float, Optional[AgenticResponse]]:
        """Check JSON validity, schema compliance, and skill existence."""
        valid_count = 0
        total_checks = 3
        score = AgenticScore()

        # Check 1: Valid JSON
        resp = self._parse_json(raw_response)
        if resp is None:
            errors.append("Response is not valid JSON")
            score.json_valid = False
            return 0.0, None

        valid_count += 1
        score.json_valid = True

        # Check 2: Schema valid (has "actions" array)
        if resp.actions is None:
            errors.append("Response missing 'actions' array")
            score.schema_valid = False
            return valid_count / total_checks, resp

        if not isinstance(resp.actions, list):
            errors.append("'actions' is not an array")
            score.schema_valid = False
            return valid_count / total_checks, resp

        valid_count += 1
        score.schema_valid = True

        # Check 3: All referenced skills exist
        for action in resp.actions:
            if action.skill and action.skill not in self.allowlist:
                errors.append(f"Skill '{action.skill}' not in allowlist: {sorted(self.allowlist)}")
                score.skills_exist = False
                return valid_count / total_checks, resp

        valid_count += 1
        score.skills_exist = True

        return valid_count / total_checks, resp

    def _parse_json(self, raw: str) -> Optional[AgenticResponse]:
        """Parse a model response into an AgenticResponse.

        Handles models that wrap JSON in markdown fences or add commentary.
        """
        # Try direct parse
        try:
            return AgenticResponse.from_json(raw)
        except Exception:
            pass

        # Try extracting from markdown fence
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if fence_match:
            try:
                return AgenticResponse.from_json(fence_match.group(1).strip())
            except Exception:
                pass

        # Try finding JSON object with "actions" key
        json_match = re.search(r'\{[^{}]*"actions"\s*:\s*\[[^\]]*\][^{}]*\}', raw, re.DOTALL)
        if json_match:
            try:
                return AgenticResponse.from_json(json_match.group(0))
            except Exception:
                pass

        return None

    # ── 2. Planning ──────────────────────────────────────────────

    def _evaluate_planning(
        self,
        actions: List[Action],
        expected: Optional[List[Action]],
        errors: List[str],
        warnings: List[str],
    ) -> float:
        """Evaluate if the sequence is correct and minimal."""
        if not expected:
            # No ground truth — score based on heuristics
            return self._planning_heuristic(actions, errors)

        exp_skills = [a.skill for a in expected]
        act_skills = [a.skill for a in actions]

        # Perfect match
        if exp_skills == act_skills:
            return 1.0

        # Partial: same skills but wrong order
        if sorted(exp_skills) == sorted(act_skills):
            warnings.append("Correct skills but wrong sequence order")
            return 0.7

        # Check correct sequence (subsequence match)
        correct_sequence = self._is_subsequence(exp_skills, act_skills)
        if correct_sequence:
            # Extra steps reduce score
            extra = len(act_skills) - len(exp_skills)
            if extra == 0:
                return 0.9
            warnings.append(f"{extra} unnecessary step(s) beyond expected")
            return max(0.3, 0.9 - extra * 0.15)

        # Wrong sequence entirely
        errors.append("Incorrect sequence of actions")
        return 0.2

    def _planning_heuristic(self, actions: List[Action], errors: List[str]) -> float:
        """Heuristic planning score when no ground truth is available."""
        if not actions:
            errors.append("No actions provided")
            return 0.0

        skills = [a.skill for a in actions]
        score = 1.0

        # Check for duplicate consecutive actions (likely redundant)
        for i in range(len(skills) - 1):
            if skills[i] == skills[i + 1]:
                score -= 0.1
                errors.append(f"Redundant consecutive '{skills[i]}' at position {i + 1}")

        # Check for silly sequence: write_file before read_file
        write_indices = [i for i, s in enumerate(skills) if s == "write_file"]
        read_indices = [i for i, s in enumerate(skills) if s == "read_file"]
        if read_indices and write_indices and min(write_indices) < min(read_indices):
            score -= 0.1
            errors.append(
                "Writing before reading may be out of order — did you read the input first?"
            )

        # Too many steps is suspicious
        if len(actions) > 10:
            score -= 0.1
            errors.append(f"High step count ({len(actions)}) may indicate over-planning")

        return max(0.0, score)

    @staticmethod
    def _is_subsequence(expected: List[str], actual: List[str]) -> bool:
        """Check if expected is a subsequence of actual (order preserved)."""
        it = iter(actual)
        return all(item in it for item in expected)

    # ── 3. Skill Correctness ─────────────────────────────────────

    def _evaluate_skill_correctness(
        self,
        actions: List[Action],
        expected_params: Optional[Dict[str, Dict]],
        score: AgenticScore,
        errors: List[str],
    ) -> float:
        """Evaluate tool selection and parameter correctness."""
        if not actions:
            return 0.0

        score.total_tool_choices = len(actions)
        correct_tools = 0
        correct_params = 0
        total_params = 0

        for i, action in enumerate(actions):
            # Check tool selection
            if action.skill in self.allowlist:
                correct_tools += 1

            # Check parameter correctness if expected_params provided
            if expected_params and action.skill in expected_params:
                exp = expected_params[action.skill]
                for key, exp_val in exp.items():
                    total_params += 1
                    actual_val = action.input.get(key)
                    if actual_val == exp_val:
                        correct_params += 1
                    else:
                        errors.append(
                            f"Action {i} '{action.skill}': param '{key}' expected "
                            f"'{exp_val}', got '{actual_val}'"
                        )

        score.correct_tool_choices = correct_tools
        score.correct_parameters = correct_params
        score.total_parameters = total_params

        tool_score = correct_tools / len(actions) if actions else 0.0
        param_score = correct_params / total_params if total_params > 0 else 1.0

        return tool_score * 0.5 + param_score * 0.5

    # ── 4. Constraint Adherence ──────────────────────────────────

    def _evaluate_constraints(
        self,
        actions: List[Action],
        score: AgenticScore,
        errors: List[str],
    ) -> float:
        """Check that model respects the skill allowlist with no hallucinations."""
        if not actions:
            return 1.0

        in_list = 0
        out_list = 0
        hallucinated = []

        known_skills = self.allowlist

        for action in actions:
            if action.skill in known_skills:
                in_list += 1
            elif action.skill:
                out_list += 1
                hallucinated.append(action.skill)
                errors.append(f"Hallucinated skill: '{action.skill}' (not in allowlist)")

        score.skills_in_allowlist = in_list
        score.skills_outside_allowlist = out_list
        score.hallucinated_skills = hallucinated

        total = in_list + out_list
        if total == 0:
            return 1.0

        return in_list / total


# ── Convenience Functions ─────────────────────────────────────────


def evaluate_agentic_response(
    raw_response: str,
    available_skills: List[str],
    expected_actions: Optional[List[Action]] = None,
    expected_params: Optional[Dict[str, Dict]] = None,
) -> AgenticEvaluationResult:
    """Convenience function for evaluating agentic responses."""
    evaluator = AgenticEvaluator(available_skills=available_skills)
    return evaluator.evaluate(raw_response, expected_actions, expected_params)


def get_hallucination_rate(result: AgenticEvaluationResult) -> float:
    """Get the hallucination rate (invalid tool usage) from a result."""
    s = result.score
    if s.total_tool_choices == 0:
        return 0.0
    return s.skills_outside_allowlist / s.total_tool_choices


if __name__ == "__main__":
    # Quick test
    evaluator = AgenticEvaluator(available_skills=["read_file", "write_file", "json_parse", "diff"])

    # Valid response
    response = json.dumps(
        {
            "actions": [
                {"skill": "read_file", "input": {"path": "src/index.ts"}},
                {"skill": "diff", "input": {"a": "old", "b": "new"}},
            ]
        }
    )

    result = evaluator.evaluate(response)
    print(f"Overall agentic score: {result.score.compute_overall():.2%}")
    print(f"Validity: {result.score.validity_score:.2%}")
    print(f"Planning: {result.score.planning_score:.2%}")
    print(f"Skill correctness: {result.score.skill_correctness_score:.2%}")
    print(f"Constraint adherence: {result.score.constraint_adherence_score:.2%}")
    if result.errors:
        print(f"Errors: {result.errors}")
