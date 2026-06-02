"""
Workload Scorer — evaluates model outputs for workload tasks.

Scoring dimensions:
- correctness: Does the code correctly address the task?
- completeness: Are all required elements present?
- code_quality: Is the code well-structured and maintainable?
- style_match: Does the code follow the project's existing patterns?
- efficiency: Is the solution efficient and appropriate?
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any

from .task_generator import WorkloadTask, TaskType


@dataclass
class WorkloadScore:
    """Scoring result for a single workload task."""
    overall: float
    correctness: float
    completeness: float
    code_quality: float
    style_match: float
    efficiency: float
    failures: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)


class WorkloadScorer:
    """Scores model responses on workload evaluation tasks.
    
    Uses a combination of:
    1. Heuristic checks (code blocks, imports, exports)
    2. Pattern matching (language idioms, framework patterns)
    3. Structural analysis (function count, docstrings, types)
    """
    
    def __init__(self):
        pass
    
    def score(self, task: WorkloadTask, response: str) -> WorkloadScore:
        """Score a model's response for a workload task.
        
        Args:
            task: The workload task
            response: The model's response text
            
        Returns:
            WorkloadScore with component scores
        """
        # Extract code blocks from response
        code_blocks = self._extract_code_blocks(response)
        has_code = len(code_blocks) > 0
        
        # Score each dimension
        correctness = self._score_correctness(task, response, code_blocks)
        completeness = self._score_completeness(task, response, code_blocks)
        code_quality = self._score_code_quality(response, code_blocks)
        style_match = self._score_style_match(task, response, code_blocks)
        efficiency = self._score_efficiency(response, code_blocks)
        
        # Collect failures and strengths
        failures = self._collect_failures(task, response, code_blocks)
        strengths = self._collect_strengths(task, response, code_blocks)
        
        # Weighted overall score
        weights = {
            "correctness": 0.30,
            "completeness": 0.25,
            "code_quality": 0.20,
            "style_match": 0.15,
            "efficiency": 0.10,
        }
        
        overall = (
            correctness * weights["correctness"]
            + completeness * weights["completeness"]
            + code_quality * weights["code_quality"]
            + style_match * weights["style_match"]
            + efficiency * weights["efficiency"]
        )
        
        return WorkloadScore(
            overall=round(overall, 3),
            correctness=round(correctness, 3),
            completeness=round(completeness, 3),
            code_quality=round(code_quality, 3),
            style_match=round(style_match, 3),
            efficiency=round(efficiency, 3),
            failures=failures,
            strengths=strengths,
        )
    
    # ── Dimension scorers ────────────────────────────────────────
    
    def _score_correctness(self, task: WorkloadTask, response: str, code_blocks: List[str]) -> float:
        """Score how correctly the response addresses the task."""
        score = 0.3  # Base for attempting the task
        
        # Has code blocks (essential for code tasks)
        if code_blocks:
            score += 0.2
        
        # References the target file/function
        target_refs = self._count_refs(response, [
            task.target_file.split("/")[-1],
            *[e for e in task.expected_elements],
        ])
        if target_refs >= 3:
            score += 0.2
        elif target_refs >= 1:
            score += 0.1
        
        # Has working code (contains function/class/export definitions)
        for block in code_blocks:
            if self._has_valid_code_structure(block, task.language):
                score += 0.15
                break
        
        # Suitable length (not too short, not too verbose)
        if 100 < len(response) < 5000:
            score += 0.15
        
        return min(score, 1.0)
    
    def _score_completeness(self, task: WorkloadTask, response: str, code_blocks: List[str]) -> float:
        """Score how complete the response is."""
        score = 0.2  # Base
        
        # Expected elements present
        if task.expected_elements:
            found = sum(1 for e in task.expected_elements if e.lower() in response.lower())
            score += 0.2 * (found / len(task.expected_elements))
        
        # Has multiple code blocks (test + implementation, etc.)
        if len(code_blocks) >= 2:
            score += 0.2
        elif len(code_blocks) >= 1:
            score += 0.1
        
        # Has explanation/commentary
        if self._has_explanation(response, code_blocks):
            score += 0.2
        
        # Has imports/requires
        for block in code_blocks:
            if self._has_imports(block, task.language):
                score += 0.2
                break
        
        return min(score, 1.0)
    
    def _score_code_quality(self, response: str, code_blocks: List[str]) -> float:
        """Score code quality - structure, types, error handling."""
        score = 0.2  # Base
        
        if not code_blocks:
            return 0.1
        
        for block in code_blocks:
            # Has function/class exports
            if re.search(r'\b(export|pub|def |fn |class )', block):
                score += 0.15
            
            # Has type annotations / type hints
            if re.search(r'(:\s*\w+|->\s*\w+|:\s*[A-Z])', block):
                score += 0.15
            
            # Has error handling
            if re.search(r'\b(try|catch|except|Result|Option|throws?|error)', block):
                score += 0.15
            
            # Has comments / docstrings
            if re.search(r'(///|// |"""|\'\'\'|# |\* )', block):
                score += 0.1
            
            # Not too long (reasonable function size)
            if len(block.split("\n")) <= 60:
                score += 0.05
            
            break  # Score based on first code block
        
        # Overall response structure
        if self._has_clear_structure(response):
            score += 0.1
        
        # No obvious issues
        if not re.search(r'(FIXME|TODO|HACK|XXX|BUG)', response):
            score += 0.1
        
        return min(score, 1.0)
    
    def _score_style_match(self, task: WorkloadTask, response: str, code_blocks: List[str]) -> float:
        """Score how well the response matches the project's code style."""
        score = 0.3  # Base
        
        if not code_blocks or not task.context_files:
            return score
        
        # Get style cues from context files
        context_code = "\n".join(task.context_files.values())
        
        for block in code_blocks:
            # Uses same import style (e.g., ES imports vs CommonJS)
            if re.search(r'import\s+.*from', context_code) and re.search(r'import\s+.*from', block):
                score += 0.2
            elif re.search(r'require\(', context_code) and re.search(r'require\(', block):
                score += 0.2
            
            # Uses same function style (arrow vs function keyword)
            context_arrows = context_code.count("=>")
            response_arrows = block.count("=>")
            context_functions = len(re.findall(r'\bfunction\b', context_code))
            response_functions = len(re.findall(r'\bfunction\b', block))
            
            if (context_arrows > context_functions and response_arrows > 0) or \
               (context_functions > context_arrows and response_functions > 0):
                score += 0.2
            
            # Uses same naming convention (camelCase vs snake_case)
            context_camel = len(re.findall(r'[a-z]+[A-Z]\w+', context_code))
            response_camel = len(re.findall(r'[a-z]+[A-Z]\w+', block))
            if (context_camel > 5 and response_camel > 0) or (context_camel == 0 and response_camel == 0):
                score += 0.15
            
            break
        
        return min(score, 1.0)
    
    def _score_efficiency(self, response: str, code_blocks: List[str]) -> float:
        """Score efficiency of the solution."""
        score = 0.3  # Base
        
        if not code_blocks:
            return score
        
        for block in code_blocks:
            # Not excessively long (efficient solutions are concise)
            lines = block.split("\n")
            if 5 <= len(lines) <= 40:
                score += 0.2
            elif 1 <= len(lines) <= 4:
                score += 0.1  # Too short might be incomplete
            
            # Uses appropriate data structures
            if re.search(r'\b(Map|Set|Promise\.all|async|await|reduce|filter)\b', block):
                score += 0.15
            
            # No nested loops deeper than 3 levels
            nesting = self._max_nesting(block)
            if nesting <= 2:
                score += 0.15
            elif nesting <= 3:
                score += 0.1
            
            # Has early returns / guard clauses
            if re.search(r'\b(return\s|guard|if .* return|if .* continue)\b', block):
                score += 0.1
            
            break
        
        return min(score, 1.0)
    
    # ── Failure/Strength collection ──────────────────────────────
    
    def _collect_failures(self, task: WorkloadTask, response: str, code_blocks: List[str]) -> List[str]:
        """Collect failure patterns from the response."""
        failures = []
        
        if not response.strip():
            failures.append("empty_response")
            return failures
        
        if not code_blocks:
            failures.append("no_code_blocks")
        
        for block in code_blocks:
            if re.search(r'\bimport\s+.*\bfrom\s+[\'"]@', block):
                # Check for hallucinated imports (scoped packages with 2+ path segments)
                imports = re.findall(r'from\s+[\'"]([^\'"]+)[\'"]', block)
                for imp in imports:
                    if "@" in imp and imp.count("/") >= 2:
                        failures.append("hallucinated_import")
                        break
            
            if re.search(r'\bany\b', block) and task.language == "typescript":
                failures.append("any_type_used")
            
            if re.search(r'(console\.log|print|println)\b', block):
                if "debug" not in response.lower() and "log" not in response.lower():
                    failures.append("leftover_debug_log")
            
            break
        
        return failures
    
    def _collect_strengths(self, task: WorkloadTask, response: str, code_blocks: List[str]) -> List[str]:
        """Collect notable strengths from the response."""
        strengths = []
        
        if not code_blocks:
            return strengths
        
        for block in code_blocks:
            if re.search(r'\b(interface|type)\s+\w+\s*{', block):
                strengths.append("typed_interfaces")
            
            if re.search(r'\b(try|catch|except)\b', block):
                strengths.append("error_handling")
            
            if re.search(r'(JSDoc|@param|@returns|"""|\'\'\'|///)', block):
                strengths.append("documented")
            
            if re.search(r'\b(async|await|Promise)\b', block):
                strengths.append("async_aware")
            
            if re.search(r'\b(Injectable|@Component|@Module)\b', block):
                strengths.append("framework_patterns")
            
            break
        
        return strengths
    
    # ── Utility methods ──────────────────────────────────────────
    
    @staticmethod
    def _extract_code_blocks(response: str) -> List[str]:
        """Extract code blocks from markdown response."""
        blocks = []
        pattern = r'```(?:\w+)?\n(.*?)```'
        for match in re.finditer(pattern, response, re.DOTALL):
            code = match.group(1).strip()
            if code:
                blocks.append(code)
        return blocks
    
    @staticmethod
    def _has_valid_code_structure(code: str, language: str) -> bool:
        """Check if code has valid structure for the language."""
        checks = {
            "typescript": [r'\b(export|function|class|const|import|interface)\b'],
            "python": [r'\b(def |class |import |from )\b'],
            "rust": [r'\b(fn |pub |struct |impl |use )\b'],
            "javascript": [r'\b(function|class|const|import|export)\b'],
        }
        
        patterns = checks.get(language, [r'\b(function|def|fn|class)\b'])
        return any(re.search(p, code) for p in patterns)
    
    @staticmethod
    def _has_explanation(response: str, code_blocks: List[str]) -> bool:
        """Check if response includes explanation beyond code."""
        text = response
        for block in code_blocks:
            text = text.replace(block, "")
        
        # Check for explanatory text
        words = len(text.split())
        return words > 30
    
    @staticmethod
    def _has_imports(code: str, language: str) -> bool:
        """Check if code has import statements."""
        if language == "typescript":
            return bool(re.search(r'import\s+.*from', code))
        elif language == "python":
            return bool(re.search(r'^(import |from )', code, re.MULTILINE))
        elif language == "rust":
            return bool(re.search(r'^(use |extern crate)', code, re.MULTILINE))
        return False
    
    @staticmethod
    def _has_clear_structure(response: str) -> bool:
        """Check if response has clear section structure."""
        markers = ["# ", "## ", "### ", "**", "---", "1. ", "- "]
        return any(m in response for m in markers)
    
    @staticmethod
    def _max_nesting(code: str) -> int:
        """Approximate maximum nesting depth in code."""
        max_depth = 0
        current = 0
        in_string = False
        
        for char in code:
            if char in ('"', "'", '`'):
                in_string = not in_string
            if not in_string:
                if char in ('{', '(', '['):
                    current += 1
                    max_depth = max(max_depth, current)
                elif char in ('}', ')', ']'):
                    current = max(0, current - 1)
        
        return max_depth
    
    @staticmethod
    def _count_refs(text: str, terms: List[str]) -> int:
        """Count references to terms in text."""
        text_lower = text.lower()
        count = 0
        for term in terms:
            if term.lower() in text_lower:
                count += 1
        return count
