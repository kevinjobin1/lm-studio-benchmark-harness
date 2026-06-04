#!/usr/bin/env python3
"""
Evaluator Interface Abstraction Layer
Provides pluggable evaluation strategies
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import json
import re


@dataclass
class EvaluationResult:
    """Result from an evaluator."""

    score: float
    passed: bool
    metadata: Dict[str, Any]
    failures: List[str] = None

    def __post_init__(self):
        if self.failures is None:
            self.failures = []


class Evaluator(ABC):
    """Abstract base class for evaluators."""

    @abstractmethod
    def evaluate(self, prompt: str, response: str, **kwargs) -> EvaluationResult:
        """Evaluate a response against a prompt."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get evaluator name."""
        pass


class JSONSchemaEvaluator(Evaluator):
    """Evaluate JSON responses against a schema."""

    def __init__(self):
        self.name = "json_schema"

    def evaluate(
        self, prompt: str, response: str, schema: Optional[Dict] = None, **kwargs
    ) -> EvaluationResult:
        """Evaluate JSON response against schema."""
        failures = []

        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            return EvaluationResult(
                score=0.0, passed=False, metadata={"error": str(e)}, failures=["invalid_json"]
            )

        if schema:
            errors = self._validate_against_schema(data, schema)
            if errors:
                failures.extend(errors)
                return EvaluationResult(
                    score=0.0, passed=False, metadata={"errors": errors}, failures=failures
                )

        return EvaluationResult(score=1.0, passed=True, metadata={"valid_json": True}, failures=[])

    def _validate_against_schema(self, data: Dict, schema: Dict) -> List[str]:
        """Validate data against schema."""
        errors = []

        for field, expected_type in schema.items():
            if field not in data:
                errors.append(f"missing_field:{field}")
            elif not isinstance(data[field], expected_type):
                errors.append(f"type_mismatch:{field}")

        return errors

    def get_name(self) -> str:
        return self.name


class RegexConstraintEvaluator(Evaluator):
    """Evaluate responses against regex constraints."""

    def __init__(self):
        self.name = "regex_constraint"

    def evaluate(
        self, prompt: str, response: str, constraints: Optional[Dict] = None, **kwargs
    ) -> EvaluationResult:
        """Evaluate response against regex constraints."""
        if not constraints:
            return EvaluationResult(score=1.0, passed=True, metadata={}, failures=[])

        failures = []
        score = 1.0

        # Check exact match constraints
        if "exact_match" in constraints:
            pattern = constraints["exact_match"]
            if not re.search(pattern, response):
                failures.append(f"pattern_not_found:{pattern}")
                score *= 0.5

        # Check forbidden patterns
        if "forbidden" in constraints:
            for pattern in constraints["forbidden"]:
                if re.search(pattern, response):
                    failures.append(f"forbidden_pattern_found:{pattern}")
                    score *= 0.5

        # Check required count
        if "required_count" in constraints:
            pattern = constraints["required_count"]["pattern"]
            expected_count = constraints["required_count"]["count"]
            actual_count = len(re.findall(pattern, response))
            if actual_count != expected_count:
                failures.append(f"count_mismatch:{pattern}:{expected_count}:{actual_count}")
                score *= 0.5

        # Check max length
        if "max_length" in constraints:
            if len(response) > constraints["max_length"]:
                failures.append(f"exceeded_max_length:{constraints['max_length']}")
                score *= 0.5

        # Check min length
        if "min_length" in constraints:
            if len(response) < constraints["min_length"]:
                failures.append(f"below_min_length:{constraints['min_length']}")
                score *= 0.5

        return EvaluationResult(
            score=score,
            passed=score == 1.0,
            metadata={"constraints_checked": list(constraints.keys())},
            failures=failures,
        )

    def get_name(self) -> str:
        return self.name


class KeywordMatchEvaluator(Evaluator):
    """Evaluate responses based on keyword presence."""

    def __init__(self):
        self.name = "keyword_match"

    def evaluate(
        self, prompt: str, response: str, keywords: Optional[List[str]] = None, **kwargs
    ) -> EvaluationResult:
        """Evaluate response based on keyword matches."""
        if not keywords:
            return EvaluationResult(score=0.5, passed=True, metadata={}, failures=[])

        response_lower = response.lower()
        matches = sum(1 for kw in keywords if kw.lower() in response_lower)
        score = matches / len(keywords)

        failures = []
        missing = [kw for kw in keywords if kw.lower() not in response_lower]
        if missing:
            failures.extend([f"missing_keyword:{kw}" for kw in missing])

        return EvaluationResult(
            score=score,
            passed=score > 0.5,
            metadata={"matches": matches, "total": len(keywords), "missing": missing},
            failures=failures,
        )

    def get_name(self) -> str:
        return self.name


class NumericalAnswerEvaluator(Evaluator):
    """Evaluate numerical answers with tolerance."""

    def __init__(self):
        self.name = "numerical_answer"

    def evaluate(
        self,
        prompt: str,
        response: str,
        expected: Optional[float] = None,
        tolerance: float = 0.01,
        **kwargs,
    ) -> EvaluationResult:
        """Evaluate numerical answer."""
        if expected is None:
            return EvaluationResult(score=0.5, passed=True, metadata={}, failures=[])

        # Extract numbers from response
        numbers = re.findall(r"-?\d+\.?\d*", response)
        if not numbers:
            return EvaluationResult(
                score=0.0,
                passed=False,
                metadata={"error": "no_numbers_found"},
                failures=["no_numerical_answer"],
            )

        # Use the last number as the answer
        predicted = float(numbers[-1])

        # Check tolerance
        diff = abs(predicted - expected)
        if diff <= tolerance:
            score = 1.0
            passed = True
        elif diff <= tolerance * 10:
            score = 0.5
            passed = False
        else:
            score = 0.0
            passed = False

        failures = []
        if not passed:
            failures.append(f"numerical_mismatch:{expected}:{predicted}:{diff}")

        return EvaluationResult(
            score=score,
            passed=passed,
            metadata={"expected": expected, "predicted": predicted, "difference": diff},
            failures=failures,
        )

    def get_name(self) -> str:
        return self.name


class CodeExecutionEvaluator(Evaluator):
    """Evaluate code by execution (if available)."""

    def __init__(self):
        self.name = "code_execution"
        self.has_ts_node = self._check_ts_node()
        self.has_tsc = self._check_tsc()

    def _check_ts_node(self) -> bool:
        """Check if ts-node is available."""
        try:
            import subprocess

            result = subprocess.run(["ts-node", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False

    def _check_tsc(self) -> bool:
        """Check if tsc is available."""
        try:
            import subprocess

            result = subprocess.run(["tsc", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False

    def evaluate(
        self, prompt: str, response: str, language: str = "typescript", **kwargs
    ) -> EvaluationResult:
        """Evaluate code by execution."""
        failures = []

        if not self.has_ts_node and language == "typescript":
            return EvaluationResult(
                score=0.5, passed=True, metadata={"skipped": "ts_node_not_available"}, failures=[]
            )

        # Extract code block
        code_match = re.search(r"```(?:typescript|ts)?\n(.*?)```", response, re.DOTALL)
        if not code_match:
            failures.append("no_code_block")
            return EvaluationResult(
                score=0.0, passed=False, metadata={"error": "no_code_block"}, failures=failures
            )

        code = code_match.group(1)

        # Try to execute
        if self.has_ts_node:
            try:
                import subprocess
                import tempfile

                with tempfile.NamedTemporaryFile(mode="w", suffix=".ts", delete=False) as f:
                    f.write(code)
                    f.flush()

                    result = subprocess.run(
                        ["ts-node", f.name], capture_output=True, text=True, timeout=10
                    )

                    if result.returncode == 0:
                        return EvaluationResult(
                            score=1.0, passed=True, metadata={"executed": True}, failures=[]
                        )
                    else:
                        failures.append("execution_failed")
                        return EvaluationResult(
                            score=0.0,
                            passed=False,
                            metadata={"error": result.stderr},
                            failures=failures,
                        )
            except Exception as e:
                failures.append("execution_error")
                return EvaluationResult(
                    score=0.0, passed=False, metadata={"error": str(e)}, failures=failures
                )

        return EvaluationResult(score=0.5, passed=True, metadata={"skipped": True}, failures=[])

    def get_name(self) -> str:
        return self.name


class CompositeEvaluator(Evaluator):
    """Combine multiple evaluators."""

    def __init__(self, evaluators: List[Evaluator], weights: Optional[List[float]] = None):
        self.evaluators = evaluators
        self.weights = weights if weights else [1.0] * len(evaluators)
        self.name = "composite"

    def evaluate(self, prompt: str, response: str, **kwargs) -> EvaluationResult:
        """Evaluate using all evaluators."""
        results = []
        all_failures = []

        for evaluator in self.evaluators:
            result = evaluator.evaluate(prompt, response, **kwargs)
            results.append(result.score)
            all_failures.extend(result.failures)

        # Weighted average
        if self.weights:
            total_weight = sum(self.weights)
            weighted_score = sum(s * w for s, w in zip(results, self.weights)) / total_weight
        else:
            weighted_score = sum(results) / len(results)

        # All must pass for overall pass
        passed = all(r.passed for r in results)

        return EvaluationResult(
            score=weighted_score,
            passed=passed,
            metadata={
                "individual_scores": results,
                "evaluators": [e.get_name() for e in self.evaluators],
            },
            failures=all_failures,
        )

    def get_name(self) -> str:
        return self.name


class EvaluatorFactory:
    """Factory for creating evaluators."""

    @staticmethod
    def create(evaluator_type: str, **kwargs) -> Evaluator:
        """Create an evaluator by type."""
        evaluators = {
            "json_schema": JSONSchemaEvaluator,
            "regex_constraint": RegexConstraintEvaluator,
            "keyword_match": KeywordMatchEvaluator,
            "numerical_answer": NumericalAnswerEvaluator,
            "code_execution": CodeExecutionEvaluator,
        }

        evaluator_class = evaluators.get(evaluator_type)
        if not evaluator_class:
            raise ValueError(f"Unknown evaluator type: {evaluator_type}")

        return evaluator_class(**kwargs)

    @staticmethod
    def create_composite(config: List[Dict]) -> Evaluator:
        """Create a composite evaluator from config."""
        evaluators = []
        weights = []

        for item in config:
            evaluator = EvaluatorFactory.create(item["type"], **item.get("kwargs", {}))
            evaluators.append(evaluator)
            weights.append(item.get("weight", 1.0))

        return CompositeEvaluator(evaluators, weights)


if __name__ == "__main__":
    # Test evaluators
    json_eval = JSONSchemaEvaluator()
    result = json_eval.evaluate(
        "Output JSON", '{"name": "test", "value": 42}', schema={"name": str, "value": (int, float)}
    )
    print(f"JSON eval: {result.score}, passed: {result.passed}")

    keyword_eval = KeywordMatchEvaluator()
    result = keyword_eval.evaluate(
        "Write about React",
        "React is a JavaScript library for building user interfaces",
        keywords=["react", "javascript", "library"],
    )
    print(f"Keyword eval: {result.score}, passed: {result.passed}")
