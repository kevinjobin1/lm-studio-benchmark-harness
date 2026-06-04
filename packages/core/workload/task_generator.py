"""
Task Generator — generates realistic coding tasks from project files.

Task types:
- implement_feature: Add a new feature to an existing file
- fix_bug: Fix an injected bug in a file
- refactor: Refactor a section of code
- write_test: Write tests for a function/class
- add_validation: Add input validation / error handling
- optimize: Optimize a slow function
- document: Add documentation / type annotations
"""

import random
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

from .project_loader import Project, ProjectFile


class TaskType(Enum):
    IMPLEMENT_FEATURE = "implement_feature"
    FIX_BUG = "fix_bug"
    REFACTOR = "refactor"
    WRITE_TEST = "write_test"
    ADD_VALIDATION = "add_validation"
    OPTIMIZE = "optimize"
    DOCUMENT = "document"


class TaskDifficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class WorkloadTask:
    """A single workload evaluation task."""

    task_id: str
    task_type: TaskType
    difficulty: TaskDifficulty
    title: str
    description: str
    prompt: str  # The prompt sent to the model
    context_files: Dict[str, str]  # File path → content for context
    target_file: str  # The file the model should modify
    language: str
    framework: str
    project_name: str
    expected_elements: List[str] = field(default_factory=list)  # Things to check in output
    reference_solution: Optional[str] = None  # Optional reference implementation


class TaskGenerator:
    """Generates realistic coding tasks from project files.

    Each task is designed to test practical developer skills:
    understanding existing code, making targeted changes, and
    maintaining code quality.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self._task_counter = 0

    def generate_tasks(
        self,
        project: Project,
        count: int = 10,
        types: Optional[List[TaskType]] = None,
        difficulty: Optional[TaskDifficulty] = None,
    ) -> List[WorkloadTask]:
        """Generate a batch of tasks from a project.

        Args:
            project: The loaded project
            count: Number of tasks to generate
            types: Task types to include (default: all)
            difficulty: Difficulty filter (default: mixed)

        Returns:
            List of WorkloadTask
        """
        available_types = types or list(TaskType)
        tasks = []

        # Collect candidate files per type
        candidates = self._collect_candidates(project)

        attempts = 0
        while len(tasks) < count and attempts < count * 5:
            attempts += 1
            task_type = self.rng.choice(available_types)
            generator = self._get_generator(task_type)

            if not generator:
                continue

            task = generator(project, candidates)
            if task:
                if difficulty and task.difficulty != difficulty:
                    continue
                tasks.append(task)

        return tasks

    def generate_task(
        self,
        project: Project,
        task_type: Optional[TaskType] = None,
        difficulty: Optional[TaskDifficulty] = None,
    ) -> Optional[WorkloadTask]:
        """Generate a single task."""
        tasks = self.generate_tasks(
            project,
            count=1,
            types=[task_type] if task_type else None,
            difficulty=difficulty,
        )
        return tasks[0] if tasks else None

    # ── Candidate collection ──────────────────────────────────────

    def _collect_candidates(self, project: Project) -> Dict[str, List[ProjectFile]]:
        """Collect candidate files for each task type."""
        candidates: Dict[str, List[ProjectFile]] = {
            "source": [],  # Source files with functions/classes
            "test": [],  # Test files
            "config": [],  # Config files
        }

        for f in project.files:
            if "/test/" in f.path or "/tests/" in f.path or f.path.startswith("test_"):
                candidates["test"].append(f)
            elif f.path.endswith((".json", ".yaml", ".yml", ".toml", ".env")):
                candidates["config"].append(f)
            elif f.functions or f.classes:
                candidates["source"].append(f)
            else:
                candidates["source"].append(f)

        return candidates

    def _get_generator(self, task_type: TaskType) -> Optional[Callable]:
        """Get the generator function for a task type."""
        generators = {
            TaskType.IMPLEMENT_FEATURE: self._generate_feature_task,
            TaskType.FIX_BUG: self._generate_bugfix_task,
            TaskType.REFACTOR: self._generate_refactor_task,
            TaskType.WRITE_TEST: self._generate_test_task,
            TaskType.ADD_VALIDATION: self._generate_validation_task,
            TaskType.OPTIMIZE: self._generate_optimize_task,
            TaskType.DOCUMENT: self._generate_document_task,
        }
        return generators.get(task_type)

    # ── Individual task generators ────────────────────────────────

    def _generate_feature_task(self, project: Project, candidates: Dict) -> Optional[WorkloadTask]:
        """Generate an implement-feature task."""
        sources = candidates["source"]
        if not sources:
            return None

        file = self.rng.choice(sources)
        self._task_counter += 1

        # Pick a function or class to extend
        target_name = None
        if file.classes:
            target_name = self.rng.choice(file.classes)
        elif file.functions:
            fn = self.rng.choice(file.functions)
            target_name = fn["name"]

        if not target_name:
            # Generic feature: add validation to a file
            return self._generate_validation_task(project, candidates)

        # Build context: include related files
        context = self._get_context(project, file)

        prompt = f"""Add a new feature to the `{target_name}` {("class" if target_name in file.classes else "function")} in `{file.path}`.

Project: {project.name} ({project.framework})
File: {file.path}

Current code context:
```{file.language}
{self._get_relevant_section(file, target_name)}
```

Task: Implement a new method or extend the existing functionality to support:
- Input validation and error handling
- Proper TypeScript types / Python type hints
- Integration with existing patterns in this file
- Tests or verification steps

Follow the existing code style and patterns in the project.
""".strip()

        return WorkloadTask(
            task_id=f"wl-feature-{self._task_counter:03d}",
            task_type=TaskType.IMPLEMENT_FEATURE,
            difficulty=TaskDifficulty.MEDIUM,
            title=f"Add feature to {target_name} in {file.path}",
            description=f"Extend {target_name} with additional functionality following existing patterns",
            prompt=prompt,
            context_files=context,
            target_file=file.path,
            language=file.language,
            framework=project.framework,
            project_name=project.name,
            expected_elements=["implementation", "error handling", "types"],
        )

    def _generate_bugfix_task(self, project: Project, candidates: Dict) -> Optional[WorkloadTask]:
        """Generate a fix-bug task."""
        sources = candidates["source"]
        if not sources:
            return None

        file = self.rng.choice(sources)
        self._task_counter += 1

        # Introduce a bug description (the model needs to understand the code and find/fix it)
        bugs = [
            "off-by-one error in array indexing",
            "missing null check before accessing property",
            "incorrect error handling — error is swallowed",
            "race condition — missing await on async call",
            "stale closure in callback — captures old state",
            "incorrect import path",
            "missing try/catch around fallible operation",
            "type mismatch between function signature and usage",
        ]
        bug = self.rng.choice(bugs)

        context = self._get_context(project, file)

        prompt = f"""Fix a bug in `{file.path}`.

Project: {project.name} ({project.framework})

Bug description: {bug}

File contents:
```{file.language}
{file.content}
```

Task:
1. Identify the bug in the code
2. Fix it with minimal changes
3. Explain what was wrong and how your fix addresses it
4. Ensure types and existing patterns are maintained
""".strip()

        return WorkloadTask(
            task_id=f"wl-bugfix-{self._task_counter:03d}",
            task_type=TaskType.FIX_BUG,
            difficulty=TaskDifficulty.EASY if "typo" in bug else TaskDifficulty.MEDIUM,
            title=f"Fix {bug.split(' — ')[0]} in {file.path}",
            description=f"Identify and fix a {bug}",
            prompt=prompt,
            context_files=context,
            target_file=file.path,
            language=file.language,
            framework=project.framework,
            project_name=project.name,
            expected_elements=["bug identification", "fix", "explanation"],
        )

    def _generate_refactor_task(self, project: Project, candidates: Dict) -> Optional[WorkloadTask]:
        """Generate a refactoring task."""
        sources = candidates["source"]
        if not sources:
            return None

        file = self.rng.choice(sources)
        self._task_counter += 1

        context = self._get_context(project, file)

        prompt = f"""Refactor the code in `{file.path}` to improve its structure and maintainability.

Project: {project.name} ({project.framework})

Current code:
```{file.language}
{file.content}
```

Refactoring goals (pick what makes sense for this code):
1. Extract repeated logic into helper functions
2. Reduce function complexity (split large functions)
3. Improve type safety (replace `any` with proper types)
4. Add proper error handling where missing
5. Improve naming and code organization

Keep the same public API / exports. Do NOT change external behavior.
""".strip()

        return WorkloadTask(
            task_id=f"wl-refactor-{self._task_counter:03d}",
            task_type=TaskType.REFACTOR,
            difficulty=TaskDifficulty.MEDIUM,
            title=f"Refactor {file.path}",
            description=f"Improve code structure, types, and maintainability",
            prompt=prompt,
            context_files=context,
            target_file=file.path,
            language=file.language,
            framework=project.framework,
            project_name=project.name,
            expected_elements=["extracted functions", "improved types", "error handling"],
        )

    def _generate_test_task(self, project: Project, candidates: Dict) -> Optional[WorkloadTask]:
        """Generate a write-test task."""
        sources = candidates["source"]
        if not sources:
            return candidates["test"]  # Can still test existing test files

        file = self.rng.choice(sources)
        self._task_counter += 1

        context = self._get_context(project, file)

        prompt = f"""Write comprehensive tests for the code in `{file.path}`.

Project: {project.name} ({project.framework})

Code to test:
```{file.language}
{file.content}
```

Requirements:
1. Cover the main functions/classes with unit tests
2. Include edge cases (empty inputs, null/undefined, errors)
3. Use the project's testing framework (Jest, Vitest, pytest, etc.)
4. Mock external dependencies (database, API calls)
5. Tests should be deterministic and isolated
""".strip()

        return WorkloadTask(
            task_id=f"wl-test-{self._task_counter:03d}",
            task_type=TaskType.WRITE_TEST,
            difficulty=TaskDifficulty.MEDIUM,
            title=f"Write tests for {file.path}",
            description=f"Create unit tests covering functions and edge cases",
            prompt=prompt,
            context_files=context,
            target_file=file.path,
            language=file.language,
            framework=project.framework,
            project_name=project.name,
            expected_elements=["test cases", "edge cases", "mocks"],
        )

    def _generate_validation_task(
        self, project: Project, candidates: Dict
    ) -> Optional[WorkloadTask]:
        """Generate an add-validation task."""
        sources = candidates["source"]
        if not sources:
            return None

        file = self.rng.choice(sources)
        self._task_counter += 1

        context = self._get_context(project, file)

        prompt = f"""Add input validation and error handling to the code in `{file.path}`.

Project: {project.name} ({project.framework})

Current code:
```{file.language}
{file.content}
```

Add:
1. Input validation for function parameters (type checks, range checks, required fields)
2. Proper error handling (try/catch where operations can fail)
3. Meaningful error messages
4. Return proper error responses instead of crashing
5. Log errors appropriately for debugging
""".strip()

        return WorkloadTask(
            task_id=f"wl-validation-{self._task_counter:03d}",
            task_type=TaskType.ADD_VALIDATION,
            difficulty=TaskDifficulty.EASY,
            title=f"Add validation to {file.path}",
            description=f"Add input validation and error handling",
            prompt=prompt,
            context_files=context,
            target_file=file.path,
            language=file.language,
            framework=project.framework,
            project_name=project.name,
            expected_elements=["validation", "error handling", "logging"],
        )

    def _generate_optimize_task(self, project: Project, candidates: Dict) -> Optional[WorkloadTask]:
        """Generate an optimization task."""
        sources = candidates["source"]
        if not sources:
            return None

        file = self.rng.choice(sources)
        self._task_counter += 1

        context = self._get_context(project, file)

        prompt = f"""Optimize the performance of the code in `{file.path}`.

Project: {project.name} ({project.framework})

Current code:
```{file.language}
{file.content}
```

Optimization goals:
1. Identify performance bottlenecks (nested loops, redundant operations, etc.)
2. Suggest and implement optimizations
3. Consider: algorithmic complexity, caching, batching, parallel execution
4. Don't sacrifice readability or type safety for micro-optimizations
5. Explain the performance impact of each change
""".strip()

        return WorkloadTask(
            task_id=f"wl-optimize-{self._task_counter:03d}",
            task_type=TaskType.OPTIMIZE,
            difficulty=TaskDifficulty.HARD,
            title=f"Optimize {file.path}",
            description=f"Identify and fix performance bottlenecks",
            prompt=prompt,
            context_files=context,
            target_file=file.path,
            language=file.language,
            framework=project.framework,
            project_name=project.name,
            expected_elements=["bottleneck analysis", "optimized code", "explanation"],
        )

    def _generate_document_task(self, project: Project, candidates: Dict) -> Optional[WorkloadTask]:
        """Generate a documentation task."""
        sources = candidates["source"]
        if not sources:
            return None

        file = self.rng.choice(sources)
        self._task_counter += 1

        context = self._get_context(project, file)

        prompt = f"""Add comprehensive documentation to the code in `{file.path}`.

Project: {project.name} ({project.framework})

Current code:
```{file.language}
{file.content}
```

Add:
1. JSDoc / docstrings for all exported functions and classes
2. Parameter descriptions with types
3. Return value descriptions
4. Usage examples for complex functions
5. Inline comments for non-obvious logic
6. A module/file-level description at the top

Follow the project's existing documentation style.
""".strip()

        return WorkloadTask(
            task_id=f"wl-doc-{self._task_counter:03d}",
            task_type=TaskType.DOCUMENT,
            difficulty=TaskDifficulty.EASY,
            title=f"Document {file.path}",
            description=f"Add JSDoc/docstrings and inline comments",
            prompt=prompt,
            context_files=context,
            target_file=file.path,
            language=file.language,
            framework=project.framework,
            project_name=project.name,
            expected_elements=["JSDoc/docstrings", "parameter docs", "examples"],
        )

    # ── Helpers ──────────────────────────────────────────────────

    def _get_context(
        self, project: Project, main_file: ProjectFile, max_context_files: int = 3
    ) -> Dict[str, str]:
        """Build context from related files."""
        context = {main_file.path: main_file.content}

        # Find related files (same directory, imported modules)
        related = []
        main_dir = "/".join(main_file.path.split("/")[:-1]) if "/" in main_file.path else ""

        for f in project.files:
            if f.path == main_file.path:
                continue
            # Same directory
            if main_dir and f.path.startswith(main_dir):
                related.append(f)

        # Pick some related files
        selected = self.rng.sample(related, min(max_context_files - 1, len(related)))
        for f in selected:
            context[f.path] = f.content

        return context

    @staticmethod
    def _get_relevant_section(file: ProjectFile, target_name: str) -> str:
        """Extract the relevant section of a file around a target."""
        lines = file.content.split("\n")
        target_line = -1

        for i, line in enumerate(lines):
            if target_name in line:
                target_line = i
                break

        if target_line < 0:
            return file.content

        # Return ~20 lines around the target
        start = max(0, target_line - 5)
        end = min(len(lines), target_line + 15)
        return "\n".join(lines[start:end])
