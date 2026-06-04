#!/usr/bin/env python3
"""
Coding Agent Scoring Rubric

High-impact, specialized scoring for coding agents.
Measures what actually matters for developer utility:

1. API Hallucination Penalty — heavily penalize hallucinated APIs/functions
2. Import Correctness — verify imports exist and are correct
3. Refactoring Quality — measure if changes improve code structure
4. Diff Accuracy — verify the diff between original and fixed code is minimal
5. Type Safety Score — TypeScript-specific correctness
6. Error Handling Score — proper try/catch, error boundaries
7. Testability Score — code is structured for testing

Scores are weighted toward pragmatic developer outcomes, not
academic evaluation metrics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum


# ── Known TypeScript/NestJS APIs ──────────────────────────────────

KNOWN_NESTJS_APIS: Set[str] = {
    "Injectable",
    "Controller",
    "Module",
    "Get",
    "Post",
    "Put",
    "Delete",
    "Patch",
    "Param",
    "Body",
    "Query",
    "Headers",
    "Req",
    "Res",
    "Next",
    "UseGuards",
    "UseInterceptors",
    "UsePipes",
    "UseFilters",
    "ExecutionContext",
    "CallHandler",
    "NestInterceptor",
    "CanActivate",
    "AuthGuard",
    "PassportStrategy",
    "PipeTransform",
    "ArgumentMetadata",
    "BadRequestException",
    "NotFoundException",
    "UnauthorizedException",
    "ForbiddenException",
    "ConflictException",
    "InternalServerErrorException",
    "SetMetadata",
    "Reflector",
    "ReflectMetadata",
    "Inject",
    "Injectable",
    "forwardRef",
    "OnModuleInit",
    "JwtService",
    "ConfigService",
    "PrismaService",
    "ClientKafka",
    "ClientProxy",
    "MessagePattern",
    "EventPattern",
    "Ctx",
    "KafkaContext",
    "Payload",
    "CacheInterceptor",
    "CacheKey",
    "CacheTTL",
    "ValidationPipe",
    "ParseIntPipe",
    "ParseUUIDPipe",
    "ClassSerializerInterceptor",
    "SerializeOptions",
    "Interceptor",
    "Middleware",
    "NestMiddleware",
}

KNOWN_REACT_APIS: Set[str] = {
    "useState",
    "useEffect",
    "useCallback",
    "useMemo",
    "useRef",
    "useContext",
    "useReducer",
    "useLayoutEffect",
    "useImperativeHandle",
    "createContext",
    "createRef",
    "forwardRef",
    "memo",
    "Fragment",
    "Suspense",
    "lazy",
    "StrictMode",
    "Component",
    "PureComponent",
    "createElement",
    "cloneElement",
    "isValidElement",
}

KNOWN_TYPESCRIPT_APIS: Set[str] = {
    "Partial",
    "Required",
    "Readonly",
    "Record",
    "Pick",
    "Omit",
    "Exclude",
    "Extract",
    "NonNullable",
    "ReturnType",
    "Parameters",
    "ConstructorParameters",
    "InstanceType",
    "Awaited",
    "Promise",
    "Array",
    "Map",
    "Set",
    "WeakMap",
    "WeakSet",
    "async",
    "await",
    "Promise.all",
    "Promise.allSettled",
    "Promise.race",
    "console.log",
    "console.error",
    "console.warn",
    "JSON.parse",
    "JSON.stringify",
    "fetch",
    "Response",
    "Request",
    "Headers",
    "Error",
    "TypeError",
    "RangeError",
    "SyntaxError",
}


# ── Types ──────────────────────────────────────────────────────────


class ImportCategory(Enum):
    CORRECT = "correct"
    MISSING = "missing"
    UNUSED = "unused"
    HALLUCINATED = "hallucinated"
    INCORRECT_PATH = "incorrect_path"


@dataclass
class ImportCheck:
    """Result of checking a single import."""

    name: str
    from_path: str
    category: ImportCategory
    suggestion: str = ""


@dataclass
class RefactoringMetrics:
    """Metrics for refactoring quality."""

    lines_added: int = 0
    lines_removed: int = 0
    complexity_before: int = 0
    complexity_after: int = 0
    duplicated_lines_removed: int = 0
    extracted_functions: int = 0
    renamed_symbols: int = 0

    @property
    def net_lines(self) -> int:
        return self.lines_added - self.lines_removed

    @property
    def complexity_delta(self) -> int:
        return self.complexity_after - self.complexity_before

    @property
    def is_net_improvement(self) -> bool:
        """True if refactoring reduced complexity without bloating code."""
        return self.complexity_delta <= 0 and self.net_lines <= 10


@dataclass
class CodingAgentScore:
    """Complete coding agent scoring breakdown."""

    # 1. API Hallucination (weight: 0.25)
    api_hallucination_score: float = 1.0
    hallucinated_apis: List[str] = field(default_factory=list)
    correct_apis_used: int = 0
    total_apis_used: int = 0

    # 2. Import Correctness (weight: 0.15)
    import_correctness_score: float = 1.0
    imports_checked: List[ImportCheck] = field(default_factory=list)

    # 3. Refactoring Quality (weight: 0.20)
    refactoring_score: float = 0.5
    refactoring: RefactoringMetrics = field(default_factory=RefactoringMetrics)

    # 4. Diff Accuracy (weight: 0.15)
    diff_accuracy_score: float = 1.0
    diff_noise_lines: int = 0
    diff_total_lines: int = 0

    # 5. Type Safety (weight: 0.10)
    type_safety_score: float = 1.0
    any_types_found: int = 0
    implicit_any_count: int = 0

    # 6. Error Handling (weight: 0.10)
    error_handling_score: float = 0.5
    has_try_catch: bool = False
    has_error_boundary: bool = False
    has_validation: bool = False

    # 7. Testability (weight: 0.05)
    testability_score: float = 0.5
    has_dependency_injection: bool = False
    has_interfaces: bool = False
    functions_are_pure: int = 0
    total_functions: int = 0

    # Aggregate
    overall_coding_score: float = 0.0

    def compute(self) -> float:
        """Compute weighted overall coding agent score."""
        weights = {
            "api_hallucination": 0.25,
            "import_correctness": 0.15,
            "refactoring": 0.20,
            "diff_accuracy": 0.15,
            "type_safety": 0.10,
            "error_handling": 0.10,
            "testability": 0.05,
        }

        self.overall_coding_score = (
            self.api_hallucination_score * weights["api_hallucination"]
            + self.import_correctness_score * weights["import_correctness"]
            + self.refactoring_score * weights["refactoring"]
            + self.diff_accuracy_score * weights["diff_accuracy"]
            + self.type_safety_score * weights["type_safety"]
            + self.error_handling_score * weights["error_handling"]
            + self.testability_score * weights["testability"]
        )
        return self.overall_coding_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_hallucination_score": self.api_hallucination_score,
            "hallucinated_apis": self.hallucinated_apis,
            "import_correctness_score": self.import_correctness_score,
            "refactoring_score": self.refactoring_score,
            "diff_accuracy_score": self.diff_accuracy_score,
            "type_safety_score": self.type_safety_score,
            "error_handling_score": self.error_handling_score,
            "testability_score": self.testability_score,
            "overall_coding_score": self.overall_coding_score,
        }


# ── Evaluator ──────────────────────────────────────────────────────


class CodingAgentEvaluator:
    """Evaluates coding agent responses with developer-utility-focused scoring.

    Key principles:
    - Heavily penalize hallucinated APIs (common LLM failure mode)
    - Reward correct, minimal diffs
    - Check imports against known packages
    - Measure refactoring quality (did it improve structure?)
    - Type safety matters for production code
    """

    # All known APIs combined
    ALL_KNOWN = KNOWN_NESTJS_APIS | KNOWN_REACT_APIS | KNOWN_TYPESCRIPT_APIS

    def evaluate(
        self,
        generated_code: str,
        original_code: Optional[str] = None,
        expected_imports: Optional[List[str]] = None,
        language: str = "typescript",
    ) -> CodingAgentScore:
        """Evaluate coding agent output.

        Args:
            generated_code: The code produced by the model
            original_code: Original code (if refactoring/fixing)
            expected_imports: Import names that should be present
            language: 'typescript' or 'python'
        """
        score = CodingAgentScore()

        # 1. API Hallucination Check
        score.api_hallucination_score = self._check_api_hallucination(
            generated_code, language, score
        )

        # 2. Import Correctness
        score.import_correctness_score = self._check_imports(
            generated_code, expected_imports or [], score, language
        )

        # 3. Refactoring Quality
        if original_code:
            score.refactoring_score = self._check_refactoring(original_code, generated_code, score)

        # 4. Diff Accuracy
        if original_code:
            score.diff_accuracy_score = self._check_diff_accuracy(
                original_code, generated_code, score
            )

        # 5. Type Safety (TypeScript only)
        if language == "typescript":
            score.type_safety_score = self._check_type_safety(generated_code, score)

        # 6. Error Handling
        score.error_handling_score = self._check_error_handling(generated_code, score)

        # 7. Testability
        score.testability_score = self._check_testability(generated_code, score)

        score.compute()
        return score

    # ── 1. API Hallucination ─────────────────────────────────────────

    def _check_api_hallucination(self, code: str, language: str, score: CodingAgentScore) -> float:
        """Detect hallucinated API calls. Heavily penalized."""
        import re

        # Extract identifiers that look like API calls
        # Pattern: PascalCase functions or camelCase methods on objects
        api_patterns = re.findall(r"\b([A-Z][a-zA-Z]+)\b", code)
        method_patterns = re.findall(r"\.(\w+)\s*\(", code)

        all_calls = set(api_patterns + method_patterns)
        score.total_apis_used = len(all_calls)

        for call in all_calls:
            # Check against known APIs
            is_known = (
                call in self.ALL_KNOWN
                or call.startswith("prisma.")
                or call.startswith("this.")
                or call.startswith("super.")
            )

            if is_known:
                score.correct_apis_used += 1
            else:
                # Check if it looks like a hallucinated API (PascalCase, not common)
                if call[0].isupper() and len(call) > 3:
                    # Heuristic: PascalCase identifiers that aren't in known APIs
                    score.hallucinated_apis.append(call)

        # Score: heavy penalty for each hallucinated API
        total = score.total_apis_used
        if total == 0:
            return 1.0

        hallucinated = len(score.hallucinated_apis)
        penalty_per_hallucination = 0.15  # Heavy penalty

        raw_score = max(0.0, 1.0 - hallucinated * penalty_per_hallucination)
        return raw_score

    # ── 2. Import Correctness ────────────────────────────────────────

    def _check_imports(
        self, code: str, expected: List[str], score: CodingAgentScore, language: str
    ) -> float:
        """Verify imports are correct and present."""
        import re

        checks = []
        present_imports: Set[str] = set()

        if language == "typescript":
            # Extract import statements
            import_lines = re.findall(
                r"import\s+(?:{[^}]+}|\*\s+as\s+\w+|\w+)\s+from\s+['\"]([^'\"]+)['\"]",
                code,
            )
            present_imports = set(import_lines)

            # Check expected imports
            for exp in expected:
                if exp in code or any(exp in imp for imp in import_lines):
                    checks.append(
                        ImportCheck(
                            name=exp,
                            from_path="",
                            category=ImportCategory.CORRECT,
                        )
                    )
                else:
                    checks.append(
                        ImportCheck(
                            name=exp,
                            from_path="",
                            category=ImportCategory.MISSING,
                            suggestion=f"Add import for {exp}",
                        )
                    )

            # Check for hallucinated imports (packages that don't exist)
            suspicious_patterns = [
                r"from\s+['\"](@\w+/[^'\"]+)['\"]",
                r"from\s+['\"]([a-z]+-[a-z]+-[a-z]+)['\"]",
            ]
            for pattern in suspicious_patterns:
                matches = re.findall(pattern, code)
                for m in matches:
                    checks.append(
                        ImportCheck(
                            name=m,
                            from_path=m,
                            category=ImportCategory.HALLUCINATED,
                            suggestion=f"Remove non-existent import: {m}",
                        )
                    )

        score.imports_checked = checks
        total_checks = len(checks)
        if total_checks == 0:
            return 1.0

        correct = sum(1 for c in checks if c.category == ImportCategory.CORRECT)
        return correct / total_checks

    # ── 3. Refactoring Quality ───────────────────────────────────────

    def _check_refactoring(self, original: str, generated: str, score: CodingAgentScore) -> float:
        """Check if the refactoring improved code quality."""
        import difflib

        orig_lines = original.splitlines()
        gen_lines = generated.splitlines()

        # Compute diff
        diff = list(difflib.unified_diff(orig_lines, gen_lines, lineterm=""))

        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

        score.refactoring = RefactoringMetrics(
            lines_added=added,
            lines_removed=removed,
        )

        # Score based on whether the change is minimal and improvement-oriented
        if added == 0 and removed == 0:
            return 0.0  # No changes made

        if score.refactoring.is_net_improvement:
            return 0.9
        elif removed > added:
            return 0.8  # Net reduction is good
        elif added > removed * 2:
            return 0.3  # Too much new code
        else:
            return 0.5

    # ── 4. Diff Accuracy ─────────────────────────────────────────────

    def _check_diff_accuracy(self, original: str, generated: str, score: CodingAgentScore) -> float:
        """Check diff is focused and minimal."""
        import difflib

        # Check for noise: whitespace-only changes, formatting only
        orig_normalized = "\n".join(l.rstrip() for l in original.splitlines())
        gen_normalized = "\n".join(l.rstrip() for l in generated.splitlines())

        if orig_normalized == gen_normalized:
            score.diff_noise_lines = abs(len(original.splitlines()) - len(generated.splitlines()))
            return 0.0  # Only whitespace changes

        diff = list(
            difflib.unified_diff(original.splitlines(), generated.splitlines(), lineterm="")
        )

        score.diff_total_lines = len(diff)
        noise = sum(1 for l in diff if l.startswith(("+", "-")) and l[1:].strip() == "")
        score.diff_noise_lines = noise

        if score.diff_total_lines == 0:
            return 1.0

        noise_ratio = noise / score.diff_total_lines
        return max(0.0, 1.0 - noise_ratio * 2)  # Heavy penalty for noise

    # ── 5. Type Safety ───────────────────────────────────────────────

    def _check_type_safety(self, code: str, score: CodingAgentScore) -> float:
        """Check TypeScript type safety."""
        import re

        # Count 'any' types
        any_in_types = len(re.findall(r":\s*any\b", code))
        any_in_generics = len(re.findall(r"<any>", code))
        any_in_casts = len(re.findall(r"as\s+any\b", code))
        implicit_any = len(
            re.findall(
                r"(?:function|const|let|var)\s+\w+\s*\([^)]*\)\s*(?::\s*\w+)?\s*{",
                code,
            )
        )

        score.any_types_found = any_in_types + any_in_generics + any_in_casts
        score.implicit_any_count = implicit_any

        # Perfect score if no 'any' types
        if score.any_types_found == 0 and score.implicit_any_count == 0:
            return 1.0

        # Penalize each 'any' type
        total_penalty = score.any_types_found * 0.1 + score.implicit_any_count * 0.05
        return max(0.0, 1.0 - total_penalty)

    # ── 6. Error Handling ────────────────────────────────────────────

    def _check_error_handling(self, code: str, score: CodingAgentScore) -> float:
        """Check for proper error handling patterns."""
        import re

        score.has_try_catch = bool(re.search(r"try\s*{", code))
        score.has_error_boundary = bool(
            re.search(r"componentDidCatch|getDerivedStateFromError|ErrorBoundary", code)
        )
        score.has_validation = bool(re.search(r"validate|isValid|check\w+|assert\w+|guard\b", code))

        score_val = 0.0
        if score.has_try_catch:
            score_val += 0.4
        if score.has_validation:
            score_val += 0.3
        if score.has_error_boundary:
            score_val += 0.3

        return min(1.0, score_val)

    # ── 7. Testability ───────────────────────────────────────────────

    def _check_testability(self, code: str, score: CodingAgentScore) -> float:
        """Check if code is structured for easy testing."""
        import re

        score.has_dependency_injection = bool(re.search(r"constructor\s*\(.*private\s+\w+", code))
        score.has_interfaces = bool(re.search(r"(?:interface|type)\s+\w+\s*{", code))

        # Check for pure functions
        functions = re.findall(
            r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
            code,
        )
        score.total_functions = len(functions)

        # Heuristic: functions without 'this.' or side effects are pure
        pure_count = 0
        for func in functions:
            func_body = self._extract_function_body(code, func)
            if func_body and "this." not in func_body:
                pure_count += 1
        score.functions_are_pure = pure_count

        score_val = 0.0
        if score.has_dependency_injection:
            score_val += 0.4
        if score.has_interfaces:
            score_val += 0.3
        if score.total_functions > 0:
            score_val += 0.3 * (score.functions_are_pure / score.total_functions)

        return min(1.0, score_val)

    @staticmethod
    def _extract_function_body(code: str, func_name: str) -> Optional[str]:
        """Extract body of a named function."""
        import re

        pattern = rf"(?:export\s+)?(?:async\s+)?function\s+{func_name}\s*\([^)]*\)\s*{{([^}}]*(?:{{[^}}]*}}[^}}]*)*)}}"
        match = re.search(pattern, code, re.DOTALL)
        return match.group(1) if match else None


# ── Convenience ────────────────────────────────────────────────────

# ── Alias for discoverability ─────────────────────────────────────

CodingAgentScorer = CodingAgentEvaluator  # alias expected by CLI/basher


def evaluate_coding_agent(
    generated_code: str,
    original_code: Optional[str] = None,
    expected_imports: Optional[List[str]] = None,
    language: str = "typescript",
) -> CodingAgentScore:
    """Convenience function to evaluate coding agent output."""
    evaluator = CodingAgentEvaluator()
    return evaluator.evaluate(generated_code, original_code, expected_imports, language)


if __name__ == "__main__":
    # Quick test
    test_code = """
import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class UserService {
  constructor(private prisma: PrismaService) {}

  async getUser(id: string): Promise<any> {
    try {
      const user = await this.prisma.user.findUnique({ where: { id } });
      if (!user) throw new NotFoundException('User not found');
      return user;
    } catch (error) {
      console.error(error);
      throw error;
    }
  }
}
"""
    result = evaluate_coding_agent(test_code, language="typescript")
    print(f"Overall coding score: {result.overall_coding_score:.2%}")
    print(f"API hallucination: {result.api_hallucination_score:.2%}")
    print(f"Import correctness: {result.import_correctness_score:.2%}")
    print(f"Error handling: {result.error_handling_score:.2%}")
    print(f"Type safety: {result.type_safety_score:.2%}")
    print(f"Testability: {result.testability_score:.2%}")
    if result.hallucinated_apis:
        print(f"Hallucinated APIs: {result.hallucinated_apis}")
