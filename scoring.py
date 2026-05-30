#!/usr/bin/env python3
"""
Robust Evaluation & Scoring System for LM Studio DevBench
Implements statistical rigor, execution-grounded scoring, and failure taxonomy
"""

import json
import re
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import statistics
import numpy as np

try:
    import scipy.stats as stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class FailureType(Enum):
    """Taxonomy of failure types for detailed analysis."""
    HALLUCINATED_API = "hallucinated_api"
    WRONG_ASYNC_USAGE = "wrong_async_usage"
    INCORRECT_JSON_SCHEMA = "incorrect_json_schema"
    OVERVERBOSE_OUTPUT = "oververbose_output"
    MISSED_CONSTRAINT = "missed_constraint"
    SYNTAX_ERROR = "syntax_error"
    LOGIC_ERROR = "logic_error"
    TYPE_ERROR = "type_error"
    MISSING_IMPORT = "missing_import"
    INCORRECT_DEPENDENCY_INJECTION = "incorrect_di"
    STALE_CLOSURE = "stale_closure"
    RACE_CONDITION = "race_condition"
    OTHER = "other"


@dataclass
class ScoreComponents:
    """Separated scoring components."""
    correctness: float = 0.0  # Actual correctness of the answer
    instruction_compliance: float = 0.0  # Following formatting constraints
    reasoning_quality: float = 0.0  # Quality of reasoning/explanation
    code_executability: float = 0.0  # Whether code actually runs
    type_safety: float = 0.0  # TypeScript type correctness
    
    def overall_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Calculate weighted overall score."""
        if weights is None:
            weights = {
                "correctness": 0.4,
                "instruction_compliance": 0.2,
                "reasoning_quality": 0.2,
                "code_executability": 0.15,
                "type_safety": 0.05
            }
        
        return (
            self.correctness * weights.get("correctness", 0.4) +
            self.instruction_compliance * weights.get("instruction_compliance", 0.2) +
            self.reasoning_quality * weights.get("reasoning_quality", 0.2) +
            self.code_executability * weights.get("code_executability", 0.15) +
            self.type_safety * weights.get("type_safety", 0.05)
        )


@dataclass
class StatisticalScore:
    """Score with statistical variance information."""
    mean: float
    std: float
    min: float
    max: float
    median: float
    samples: int
    confidence_interval: Optional[Tuple[float, float]] = None
    confidence_level: float = 0.95
    
    def __str__(self) -> str:
        if self.confidence_interval:
            ci_lower, ci_upper = self.confidence_interval
            return f"{self.mean:.3f} ± {self.std:.3f} (95% CI: [{ci_lower:.3f}, {ci_upper:.3f}], n={self.samples})"
        return f"{self.mean:.3f} ± {self.std:.3f} (n={self.samples})"


@dataclass
class EvaluationResult:
    """Complete evaluation result with all metrics."""
    score_components: ScoreComponents
    overall_score: float
    statistical_score: StatisticalScore
    failures: List[FailureType] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TypeScriptExecutor:
    """Execute TypeScript code for execution-grounded scoring."""
    
    def __init__(self):
        self.has_ts_node = self._check_ts_node()
        self.has_tsc = self._check_tsc()
        self.has_eslint = self._check_eslint()
    
    def _check_ts_node(self) -> bool:
        """Check if ts-node is available."""
        try:
            result = subprocess.run(
                ["ts-node", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _check_tsc(self) -> bool:
        """Check if TypeScript compiler is available."""
        try:
            result = subprocess.run(
                ["tsc", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _check_eslint(self) -> bool:
        """Check if ESLint is available."""
        try:
            result = subprocess.run(
                ["eslint", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def execute_code(self, code: str, timeout: int = 10) -> Tuple[bool, str]:
        """Execute TypeScript code and return (success, output)."""
        if not self.has_ts_node:
            return False, "ts-node not available"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            ts_file = tmpdir_path / "temp.ts"
            ts_file.write_text(code)
            
            try:
                result = subprocess.run(
                    ["ts-node", str(ts_file)],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                return result.returncode == 0, result.stdout + result.stderr
            except subprocess.TimeoutExpired:
                return False, "Execution timeout"
            except Exception as e:
                return False, str(e)
    
    def check_types(self, code: str) -> Tuple[bool, List[str]]:
        """Check TypeScript types using tsc."""
        if not self.has_tsc:
            return True, []  # Assume pass if tsc not available
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            ts_file = tmpdir_path / "temp.ts"
            ts_file.write_text(code)
            tsconfig = tmpdir_path / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions":{"strict":true,"noEmit":true}}')
            
            try:
                result = subprocess.run(
                    ["tsc", "--noEmit", str(ts_file)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return True, []
                else:
                    errors = result.stderr.split('\n')
                    return False, errors
            except Exception as e:
                return False, [str(e)]
    
    def lint_code(self, code: str) -> Tuple[bool, List[str]]:
        """Lint code using ESLint."""
        if not self.has_eslint:
            return True, []  # Assume pass if eslint not available
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            ts_file = tmpdir_path / "temp.ts"
            ts_file.write_text(code)
            eslintrc = tmpdir_path / ".eslintrc.json"
            eslintrc.write_text('{"env":{"node":true,"es6":true},"parserOptions":{"ecmaVersion":2020,"sourceType":"module"},"rules":{}}')
            
            try:
                result = subprocess.run(
                    ["eslint", str(ts_file)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return True, []
                else:
                    errors = result.stdout.split('\n')
                    return False, errors
            except Exception as e:
                return False, [str(e)]


class CodeScorer:
    """Execution-grounded scoring for code tasks."""
    
    def __init__(self):
        self.ts_executor = TypeScriptExecutor()
    
    def score_code(self, code: str, expected_tests: Optional[List[str]] = None) -> ScoreComponents:
        """Score code with execution-grounded metrics."""
        components = ScoreComponents()
        
        # Check syntax and executability
        can_execute, exec_output = self.ts_executor.execute_code(code)
        components.code_executability = 1.0 if can_execute else 0.0
        
        # Check type safety
        type_safe, type_errors = self.ts_executor.check_types(code)
        components.type_safety = 1.0 if type_safe else max(0.0, 1.0 - len(type_errors) * 0.1)
        
        # Check linting
        lint_clean, lint_errors = self.ts_executor.lint_code(code)
        if not lint_clean:
            components.instruction_compliance = max(0.0, 1.0 - len(lint_errors) * 0.05)
        
        # Detect specific failure patterns
        failures = self._detect_failures(code, exec_output, type_errors)
        
        return components, failures
    
    def _detect_failures(self, code: str, exec_output: str, type_errors: List[str]) -> List[FailureType]:
        """Detect specific failure patterns."""
        failures = []
        
        # Check for hallucinated APIs
        common_apis = ["useState", "useEffect", "useQuery", "Injectable", "Controller"]
        for api in common_apis:
            if api in code and "import" not in code[:code.find(api)]:
                failures.append(FailureType.MISSING_IMPORT)
        
        # Check for async/await issues
        if "async" in code and "await" not in code:
            failures.append(FailureType.WRONG_ASYNC_USAGE)
        
        # Check for DI issues in NestJS
        if "@Injectable()" in code and "constructor" not in code:
            failures.append(FailureType.INCORRECT_DEPENDENCY_INJECTION)
        
        # Check for stale closure patterns
        if "useEffect" in code and "[]" in code and "function()" in code:
            failures.append(FailureType.STALE_CLOSURE)
        
        # Check for race conditions
        if "Promise.all" not in code and code.count("await") > 2:
            failures.append(FailureType.RACE_CONDITION)
        
        # Type errors
        if type_errors:
            for error in type_errors:
                if "Type" in error:
                    failures.append(FailureType.TYPE_ERROR)
        
        return failures


class InstructionScorer:
    """Score instruction following separately from content quality."""
    
    def score_instruction_compliance(self, response: str, constraints: Dict[str, Any]) -> float:
        """Score how well response follows formatting constraints."""
        score = 1.0
        
        # Check JSON validity
        if constraints.get("json_only"):
            try:
                json.loads(response)
            except:
                score *= 0.0
        
        # Check exact bullet point count
        if constraints.get("bullet_count"):
            bullet_count = response.count("•") + response.count("-") + response.count("*")
            if bullet_count != constraints["bullet_count"]:
                score *= 0.5
        
        # Check no markdown
        if constraints.get("no_markdown"):
            if "**" in response or "```" in response or "_" in response:
                score *= 0.5
        
        # Check exact sentence count
        if constraints.get("sentence_count"):
            sentence_count = len(re.split(r'[.!?]+', response))
            if sentence_count != constraints["sentence_count"]:
                score *= 0.5
        
        # Check max length
        if constraints.get("max_length"):
            if len(response) > constraints["max_length"]:
                score *= 0.5
        
        return score
    
    def check_json_schema(self, response: str, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Check if JSON response matches expected schema."""
        try:
            data = json.loads(response)
            errors = []
            
            for field, expected_type in schema.items():
                if field not in data:
                    errors.append(f"Missing field: {field}")
                elif not isinstance(data[field], expected_type):
                    errors.append(f"Field {field} has wrong type: expected {expected_type}, got {type(data[field])}")
            
            return len(errors) == 0, errors
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {e}"]


class ReasoningScorer:
    """Score reasoning quality separately from correctness."""
    
    def score_reasoning(self, response: str, expected_concepts: List[str]) -> float:
        """Score reasoning based on presence of key concepts."""
        response_lower = response.lower()
        concept_matches = sum(1 for concept in expected_concepts if concept.lower() in response_lower)
        
        # Base score from concept coverage
        base_score = concept_matches / len(expected_concepts) if expected_concepts else 0.5
        
        # Bonus for structured reasoning (step-by-step)
        has_steps = any(marker in response.lower() for marker in ["step", "first", "then", "finally", "1.", "2.", "3."])
        if has_steps:
            base_score *= 1.1
        
        # Bonus for trade-off analysis
        has_tradeoffs = any(word in response.lower() for word in ["trade-off", "pro", "con", "advantage", "disadvantage"])
        if has_tradeoffs:
            base_score *= 1.05
        
        return min(1.0, base_score)


class MathScorer:
    """Score math problems with numerical comparison."""
    
    def score_math(self, response: str, expected_answer: float, tolerance: float = 0.01) -> float:
        """Score math answer with tolerance."""
        # Extract numbers from response
        numbers = re.findall(r'-?\d+\.?\d*', response)
        if not numbers:
            return 0.0
        
        # Use the last number as the answer
        predicted = float(numbers[-1])
        
        # Check if within tolerance
        if abs(predicted - expected_answer) <= tolerance:
            return 1.0
        elif abs(predicted - expected_answer) <= tolerance * 10:
            return 0.5
        else:
            return 0.0


class VarianceScorer:
    """Handle multiple-run variance for statistical rigor."""
    
    def __init__(self, num_runs: int = 5, confidence_level: float = 0.95):
        self.num_runs = num_runs
        self.confidence_level = confidence_level
    
    def compute_statistical_score(self, scores: List[float]) -> StatisticalScore:
        """Compute statistical metrics from multiple runs."""
        if not scores:
            return StatisticalScore(0.0, 0.0, 0.0, 0.0, 0.0, 0)
        
        # Calculate confidence interval
        confidence_interval = None
        if len(scores) > 1:
            confidence_interval = self._compute_confidence_interval(scores, self.confidence_level)
        
        return StatisticalScore(
            mean=statistics.mean(scores),
            std=statistics.stdev(scores) if len(scores) > 1 else 0.0,
            min=min(scores),
            max=max(scores),
            median=statistics.median(scores),
            samples=len(scores),
            confidence_interval=confidence_interval,
            confidence_level=self.confidence_level
        )
    
    def _compute_confidence_interval(self, scores: List[float], confidence_level: float) -> Tuple[float, float]:
        """Compute confidence interval using t-distribution."""
        if not SCIPY_AVAILABLE:
            # Fallback to normal approximation if scipy not available
            from math import sqrt
            n = len(scores)
            mean = statistics.mean(scores)
            std = statistics.stdev(scores) if n > 1 else 0.0
            
            # Normal approximation
            z_critical = 1.96  # 95% confidence
            margin_of_error = z_critical * (std / sqrt(n))
            
            ci_lower = mean - margin_of_error
            ci_upper = mean + margin_of_error
            return (ci_lower, ci_upper)
        
        n = len(scores)
        mean = statistics.mean(scores)
        std = statistics.stdev(scores) if n > 1 else 0.0
        
        # Use t-distribution for small samples
        t_critical = stats.t.ppf((1 + confidence_level) / 2, n - 1)
        margin_of_error = t_critical * (std / (n ** 0.5))
        
        ci_lower = mean - margin_of_error
        ci_upper = mean + margin_of_error
        
        return (ci_lower, ci_upper)
    
    def is_reliable(self, stat_score: StatisticalScore, threshold: float = 0.1) -> bool:
        """Check if score is reliable (low variance)."""
        if stat_score.samples < 3:
            return False
        # Coefficient of variation
        cv = stat_score.std / stat_score.mean if stat_score.mean > 0 else float('inf')
        return cv < threshold
    
    def detect_outliers(self, scores: List[float], method: str = "iqr") -> List[int]:
        """Detect outlier indices using specified method."""
        if len(scores) < 4:
            return []
        
        if method == "iqr":
            return self._detect_outliers_iqr(scores)
        elif method == "zscore":
            return self._detect_outliers_zscore(scores)
        else:
            return []
    
    def _detect_outliers_iqr(self, scores: List[float]) -> List[int]:
        """Detect outliers using IQR method."""
        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        
        q1 = sorted_scores[n // 4]
        q3 = sorted_scores[3 * n // 4]
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outliers = []
        for i, score in enumerate(scores):
            if score < lower_bound or score > upper_bound:
                outliers.append(i)
        
        return outliers
    
    def _detect_outliers_zscore(self, scores: List[float], threshold: float = 2.0) -> List[int]:
        """Detect outliers using z-score method."""
        mean = statistics.mean(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 1.0
        
        outliers = []
        for i, score in enumerate(scores):
            if std > 0:
                z_score = abs((score - mean) / std)
                if z_score > threshold:
                    outliers.append(i)
        
        return outliers


class TokenizationAwareMetrics:
    """Tokenization-aware performance metrics."""
    
    @staticmethod
    def normalize_tokens_per_second(tokens_per_second: float, output_length: int) -> float:
        """Normalize tokens/sec by output length to account for verbosity bias."""
        # Longer outputs naturally have lower tokens/sec due to context growth
        # Normalize to a reference length of 100 tokens
        reference_length = 100
        if output_length <= 0:
            return tokens_per_second
        
        # Apply logarithmic normalization
        length_factor = np.log10(reference_length) / np.log10(output_length)
        return tokens_per_second * length_factor
    
    @staticmethod
    def compute_steady_state_speed(token_times: List[float]) -> Tuple[float, float]:
        """Compute steady-state speed and tail latency from token times."""
        if not token_times:
            return 0.0, 0.0
        
        # Skip first few tokens (warmup)
        warmup_tokens = 3
        if len(token_times) <= warmup_tokens:
            return statistics.mean(token_times), max(token_times)
        
        steady_times = token_times[warmup_tokens:]
        steady_speed = 1.0 / statistics.mean(steady_times) if steady_times else 0.0
        tail_latency = max(steady_times)
        
        return steady_speed, tail_latency


class DeveloperRealismScorer:
    """Compute developer realism score for practical utility."""
    
    @staticmethod
    def compute_developer_score(components: ScoreComponents, 
                                 latency_score: float,
                                 verbosity_penalty: float = 0.0) -> float:
        """
        Compute developer realism score.
        
        Formula:
        DeveloperScore = correctness * 0.4 +
                        debugging ability * 0.3 +
                        instruction following * 0.2 +
                        latency score * 0.1
        """
        debugging_ability = components.code_executability * 0.5 + components.type_safety * 0.5
        instruction_following = components.instruction_compliance
        
        score = (
            components.correctness * 0.4 +
            debugging_ability * 0.3 +
            instruction_following * 0.2 +
            latency_score * 0.1
        )
        
        # Apply verbosity penalty
        score *= (1.0 - verbosity_penalty)
        
        return max(0.0, min(1.0, score))


class ComprehensiveEvaluator:
    """Main evaluator combining all scoring components."""
    
    def __init__(self, num_runs: int = 5):
        self.code_scorer = CodeScorer()
        self.instruction_scorer = InstructionScorer()
        self.reasoning_scorer = ReasoningScorer()
        self.math_scorer = MathScorer()
        self.variance_scorer = VarianceScorer(num_runs)
        self.token_metrics = TokenizationAwareMetrics()
        self.developer_scorer = DeveloperRealismScorer()
    
    def evaluate(self, response: str, prompt_data: Dict, 
                 category: str, token_times: Optional[List[float]] = None) -> EvaluationResult:
        """Comprehensive evaluation of a response."""
        components = ScoreComponents()
        failures = []
        
        # Category-specific scoring
        if category == "code":
            components, failures = self.code_scorer.score_code(response)
            # Add reasoning quality for code explanations
            if expected_concepts := prompt_data.get("expected_keywords"):
                components.reasoning_quality = self.reasoning_scorer.score_reasoning(response, expected_concepts)
        
        elif category == "frontend":
            # Similar to code but with different weights
            components, failures = self.code_scorer.score_code(response)
            if expected_concepts := prompt_data.get("expected_keywords"):
                components.reasoning_quality = self.reasoning_scorer.score_reasoning(response, expected_concepts)
        
        elif category == "reasoning":
            if expected_concepts := prompt_data.get("expected_keywords"):
                components.reasoning_quality = self.reasoning_scorer.score_reasoning(response, expected_concepts)
                components.correctness = components.reasoning_quality  # For reasoning, correctness = reasoning quality
        
        elif category == "math":
            if expected_answer := prompt_data.get("expected_answer"):
                components.correctness = self.math_scorer.score_math(response, expected_answer)
        
        elif category == "instruction":
            constraints = prompt_data.get("constraints", {})
            components.instruction_compliance = self.instruction_scorer.score_instruction_compliance(response, constraints)
            if schema := prompt_data.get("json_schema"):
                is_valid, errors = self.instruction_scorer.check_json_schema(response, schema)
                if not is_valid:
                    failures.append(FailureType.INCORRECT_JSON_SCHEMA)
        
        # Calculate overall score
        overall_score = components.overall_score()
        
        # For now, use single-run statistical score
        # In practice, this should be computed from multiple runs
        stat_score = StatisticalScore(overall_score, 0.0, overall_score, overall_score, overall_score, 1)
        
        return EvaluationResult(
            score_components=components,
            overall_score=overall_score,
            statistical_score=stat_score,
            failures=failures
        )
    
    def evaluate_with_variance(self, responses: List[str], prompt_data: Dict,
                               category: str) -> EvaluationResult:
        """Evaluate with multiple runs for variance."""
        if not responses:
            return EvaluationResult(
                score_components=ScoreComponents(),
                overall_score=0.0,
                statistical_score=StatisticalScore(0.0, 0.0, 0.0, 0.0, 0.0, 0)
            )
        
        # Evaluate each response
        evaluations = [self.evaluate(r, prompt_data, category) for r in responses]
        
        # Compute variance for overall scores
        scores = [e.overall_score for e in evaluations]
        stat_score = self.variance_scorer.compute_statistical_score(scores)
        
        # Use mean score components
        mean_components = ScoreComponents(
            correctness=statistics.mean([e.score_components.correctness for e in evaluations]),
            instruction_compliance=statistics.mean([e.score_components.instruction_compliance for e in evaluations]),
            reasoning_quality=statistics.mean([e.score_components.reasoning_quality for e in evaluations]),
            code_executability=statistics.mean([e.score_components.code_executability for e in evaluations]),
            type_safety=statistics.mean([e.score_components.type_safety for e in evaluations])
        )
        
        # Aggregate failures
        all_failures = []
        for e in evaluations:
            all_failures.extend(e.failures)
        
        return EvaluationResult(
            score_components=mean_components,
            overall_score=stat_score.mean,
            statistical_score=stat_score,
            failures=all_failures
        )
