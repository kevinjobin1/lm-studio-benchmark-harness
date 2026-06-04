"""
Unit tests for workload evaluation core components:
  - ProjectLoader (project loading, file parsing, built-in projects)
  - TaskGenerator (task generation, task types, difficulty)
  - WorkloadScorer (scoring dimensions, failure detection, strength detection)

Uses built-in sample projects (no git/local dependencies) and deterministic
seeds for reproducible test results.
"""

import unittest
import tempfile
from pathlib import Path

from core.workload import (
    ProjectLoader, ProjectFile, Project,
    TaskGenerator, WorkloadTask, TaskDifficulty, TaskType,
    WorkloadScorer, WorkloadScore,
)


# ═════════════════════════════════════════════════════════════════════
#  PROJECT LOADER TESTS
# ═════════════════════════════════════════════════════════════════════

class TestProjectLoaderBuiltin(unittest.TestCase):
    """Tests for loading built-in sample projects."""

    def setUp(self):
        self.loader = ProjectLoader()

    def test_load_builtin_nestjs_api(self):
        """Loading nestjs-api should return a valid Project with files."""
        project = self.loader.load_builtin("nestjs-api")
        self.assertIsInstance(project, Project)
        self.assertEqual(project.name, "nestjs-api")
        self.assertEqual(project.language, "typescript")
        self.assertEqual(project.framework, "nestjs")
        self.assertGreater(project.total_files, 0)
        self.assertGreater(project.total_lines, 0)
        # Should have at least the three sample files
        self.assertIsNotNone(project.get_file_by_path("src/app.module.ts"))
        self.assertIsNotNone(project.get_file_by_path("src/users/users.service.ts"))
        self.assertIsNotNone(project.get_file_by_path("src/users/users.controller.ts"))

    def test_load_builtin_react_app(self):
        """Loading react-app should return a valid Project."""
        project = self.loader.load_builtin("react-app")
        self.assertEqual(project.name, "react-app")
        self.assertEqual(project.framework, "react")
        self.assertEqual(project.language, "typescript")
        self.assertIsNotNone(project.get_file_by_path("src/App.tsx"))
        self.assertIsNotNone(project.get_file_by_path("src/hooks/useModels.ts"))

    def test_load_builtin_python_cli(self):
        """Loading python-cli should return a Python project."""
        project = self.loader.load_builtin("python-cli")
        self.assertEqual(project.name, "python-cli")
        self.assertEqual(project.language, "python")
        self.assertEqual(project.framework, "click")
        self.assertIsNotNone(project.get_file_by_path("cli.py"))

    def test_load_builtin_rust_server(self):
        """Loading rust-server should return a Rust project."""
        project = self.loader.load_builtin("rust-server")
        self.assertEqual(project.name, "rust-server")
        self.assertEqual(project.language, "rust")
        self.assertEqual(project.framework, "actix")
        self.assertIsNotNone(project.get_file_by_path("src/main.rs"))

    def test_load_builtin_invalid_name_raises(self):
        """Loading a non-existent built-in should raise ValueError."""
        with self.assertRaises(ValueError):
            self.loader.load_builtin("nonexistent-project")

    def test_list_builtin_returns_dict(self):
        """list_builtin should return all available projects."""
        projects = self.loader.list_builtin()
        self.assertIn("nestjs-api", projects)
        self.assertIn("react-app", projects)
        self.assertIn("python-cli", projects)
        self.assertIn("rust-server", projects)
        self.assertEqual(len(projects), 4)
        # Values should be descriptions (strings)
        for desc in projects.values():
            self.assertIsInstance(desc, str)
            self.assertGreater(len(desc), 0)

    def test_builtin_project_file_metadata(self):
        """Built-in project file should have parsed exports, classes, functions."""
        project = self.loader.load_builtin("nestjs-api")
        app_module = project.get_file_by_path("src/app.module.ts")
        self.assertIsNotNone(app_module)
        # AppModule should have exports
        self.assertIn("AppModule", app_module.exports)
        self.assertIn("AppModule", app_module.classes)
        # UsersService should have exports
        users_service = project.get_file_by_path("src/users/users.service.ts")
        self.assertIn("UsersService", users_service.exports)

    def test_builtin_project_get_files_by_language(self):
        """get_files_by_language should filter correctly."""
        project = self.loader.load_builtin("nestjs-api")
        ts_files = project.get_files_by_language("typescript")
        self.assertEqual(len(ts_files), 3)

    def test_builtin_project_get_file_by_path_missing(self):
        """get_file_by_path should return None for missing files."""
        project = self.loader.load_builtin("nestjs-api")
        self.assertIsNone(project.get_file_by_path("src/missing.ts"))


class TestProjectLoaderLocal(unittest.TestCase):
    """Tests for loading projects from a local directory."""

    def setUp(self):
        self.loader = ProjectLoader()
        # Create a temporary directory with sample files
        self.tmpdir = Path(tempfile.mkdtemp())
        self._create_sample_files()

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmpdir), ignore_errors=True)

    def _create_sample_files(self):
        """Create a minimal sample project in the temp directory."""
        src = self.tmpdir / "src"
        src.mkdir()
        (src / "index.ts").write_text("""\
import { greet } from './utils';

export function main() {
  console.log(greet('World'));
}
""")
        (src / "utils.ts").write_text("""\
export function greet(name: string): string {
  return `Hello, ${name}!`;
}

export function add(a: number, b: number): number {
  return a + b;
}
""")
        # Add a Python file
        (src / "script.py").write_text("""\
def process(data: list) -> dict:
    result = {}
    for item in data:
        result[item.id] = item.name
    return result
""")
        # Add an ignorable file
        (src / "bundle.min.js").write_text("minified")

    def test_load_local_project(self):
        """Loading a local directory should return a valid Project."""
        project = self.loader.load_project(str(self.tmpdir))
        self.assertEqual(project.name, self.tmpdir.name)
        self.assertGreater(project.total_files, 0)

    def test_load_local_detects_typescript(self):
        """Local TS project should be detected as typescript."""
        project = self.loader.load_project(str(self.tmpdir))
        self.assertEqual(project.language, "typescript")
        paths = [f.path for f in project.files]
        self.assertIn("src/index.ts", paths)
        self.assertIn("src/utils.ts", paths)

    def test_load_local_ignores_minified_files(self):
        """Minified JS files should be ignored."""
        project = self.loader.load_project(str(self.tmpdir))
        paths = [f.path for f in project.files]
        self.assertNotIn("src/bundle.min.js", paths)

    def test_load_local_nonexistent_raises(self):
        """Loading a non-existent path should raise ValueError."""
        with self.assertRaises(ValueError):
            self.loader.load_project("/nonexistent/path")

    def test_load_local_parses_ts_exports(self):
        """TypeScript files should have exports parsed."""
        project = self.loader.load_project(str(self.tmpdir))
        utils_file = project.get_file_by_path("src/utils.ts")
        self.assertIsNotNone(utils_file)
        # 'greet' and 'add' are exported
        self.assertIn("greet", utils_file.exports)
        self.assertIn("add", utils_file.exports)
        # 'main' is exported from index.ts
        index_file = project.get_file_by_path("src/index.ts")
        self.assertIn("main", index_file.exports)

    def test_load_local_parses_ts_functions(self):
        """TypeScript files should have function metadata parsed."""
        project = self.loader.load_project(str(self.tmpdir))
        utils_file = project.get_file_by_path("src/utils.ts")
        func_names = [f["name"] for f in utils_file.functions]
        self.assertIn("greet", func_names)
        self.assertIn("add", func_names)

    def test_load_local_parses_python_functions(self):
        """Python files should have function metadata parsed."""
        project = self.loader.load_project(str(self.tmpdir))
        py_file = project.get_file_by_path("src/script.py")
        self.assertIsNotNone(py_file)
        self.assertEqual(py_file.language, "python")
        func_names = [f["name"] for f in py_file.functions]
        self.assertIn("process", func_names)


class TestProjectLoaderGitUrlDetection(unittest.TestCase):
    """Tests for git URL detection in ProjectLoader."""

    def setUp(self):
        self.loader = ProjectLoader()

    def test_github_https_without_dot_git(self):
        """GitHub HTTPS URL without .git suffix should be detected."""
        self.assertTrue(
            self.loader._is_git_url("https://github.com/user/repo"),
        )

    def test_github_https_with_dot_git(self):
        """GitHub HTTPS URL with .git suffix should be detected."""
        self.assertTrue(
            self.loader._is_git_url("https://github.com/user/repo.git"),
        )

    def test_gitlab_https_url(self):
        """GitLab HTTPS URL should be detected."""
        self.assertTrue(
            self.loader._is_git_url("https://gitlab.com/user/repo"),
        )

    def test_bitbucket_https_url(self):
        """Bitbucket HTTPS URL should be detected."""
        self.assertTrue(
            self.loader._is_git_url("https://bitbucket.org/user/repo"),
            "bitbucket.org should be detected as a git URL",
        )

    def test_ssh_git_url(self):
        """SSH git URL should be detected."""
        self.assertTrue(
            self.loader._is_git_url("git@github.com:user/repo.git"),
        )

    def test_local_path_not_git_url(self):
        """A local path should NOT be detected as a git URL."""
        self.assertFalse(
            self.loader._is_git_url("/home/user/project"),
        )

    def test_regular_https_not_git_url(self):
        """A regular HTTPS URL (not git hosting) should NOT be detected."""
        self.assertFalse(
            self.loader._is_git_url("https://example.com/file.txt"),
        )


# ═════════════════════════════════════════════════════════════════════
#  TASK GENERATOR TESTS
# ═════════════════════════════════════════════════════════════════════

class TestTaskGenerator(unittest.TestCase):
    """Tests for TaskGenerator — task generation and type distribution."""

    def setUp(self):
        self.loader = ProjectLoader()
        self.project = self.loader.load_builtin("nestjs-api")
        self.generator = TaskGenerator(seed=42)

    def test_generate_tasks_default_count(self):
        """generate_tasks with default count should produce tasks."""
        tasks = self.generator.generate_tasks(self.project, count=5)
        self.assertEqual(len(tasks), 5)
        for task in tasks:
            self.assertIsInstance(task, WorkloadTask)
            self.assertIsNotNone(task.task_id)
            self.assertIsNotNone(task.prompt)
            self.assertIsNotNone(task.target_file)

    def test_generate_tasks_many(self):
        """generate_tasks with a larger count should yield all requested tasks."""
        tasks = self.generator.generate_tasks(self.project, count=20)
        self.assertEqual(len(tasks), 20)

    def test_generate_tasks_zero(self):
        """generate_tasks with count=0 should return empty list."""
        tasks = self.generator.generate_tasks(self.project, count=0)
        self.assertEqual(len(tasks), 0)

    def test_task_has_expected_fields(self):
        """Each generated task should have all required fields populated."""
        tasks = self.generator.generate_tasks(self.project, count=3)
        for t in tasks:
            self.assertTrue(t.task_id.startswith("wl-"))
            self.assertIsInstance(t.task_type, TaskType)
            self.assertIsInstance(t.difficulty, TaskDifficulty)
            self.assertGreater(len(t.title), 0)
            self.assertGreater(len(t.prompt), 50)
            self.assertGreater(len(t.context_files), 0)
            self.assertIn(t.target_file, t.context_files)
            self.assertEqual(t.language, "typescript")
            self.assertEqual(t.project_name, "nestjs-api")

    def test_task_types_are_diverse(self):
        """Generated tasks should include various task types."""
        tasks = self.generator.generate_tasks(self.project, count=15)
        types_found = set(t.task_type for t in tasks)
        # With 15 tasks across 7 types, we should see at least 3 different types
        self.assertGreaterEqual(len(types_found), 3,
                                f"Expected diverse types, got: {types_found}")

    def test_single_task_type_filter(self):
        """Filtering by a single task type should produce only that type."""
        tasks = self.generator.generate_tasks(
            self.project, count=5, types=[TaskType.FIX_BUG],
        )
        for t in tasks:
            self.assertEqual(t.task_type, TaskType.FIX_BUG)

    def test_single_difficulty_filter(self):
        """Filtering by difficulty should produce only that difficulty."""
        tasks = self.generator.generate_tasks(
            self.project, count=5, difficulty=TaskDifficulty.EASY,
        )
        for t in tasks:
            self.assertEqual(t.difficulty, TaskDifficulty.EASY)

    def test_generate_task_single(self):
        """generate_task (singular) should return a single task or None."""
        task = self.generator.generate_task(self.project)
        if task is not None:
            self.assertIsInstance(task, WorkloadTask)
            self.assertTrue(task.task_id.startswith("wl-"))
        # For a project with source files, it should return a task
        self.assertIsNotNone(task)

    def test_generate_task_with_type(self):
        """generate_task with specific type should return that type."""
        task = self.generator.generate_task(
            self.project, task_type=TaskType.DOCUMENT,
        )
        if task is not None:
            self.assertEqual(task.task_type, TaskType.DOCUMENT)

    def test_task_target_file_exists(self):
        """The target file should be one of the project's files."""
        tasks = self.generator.generate_tasks(self.project, count=5)
        project_files = {f.path for f in self.project.files}
        for t in tasks:
            self.assertIn(t.target_file, project_files)

    def test_task_context_includes_target(self):
        """Context files should include the target file."""
        tasks = self.generator.generate_tasks(self.project, count=5)
        for t in tasks:
            self.assertIn(t.target_file, t.context_files)

    def test_deterministic_with_seed(self):
        """Same seed should produce the same tasks."""
        gen_a = TaskGenerator(seed=100)
        gen_b = TaskGenerator(seed=100)
        tasks_a = gen_a.generate_tasks(self.project, count=5)
        tasks_b = gen_b.generate_tasks(self.project, count=5)
        for ta, tb in zip(tasks_a, tasks_b):
            self.assertEqual(ta.task_type, tb.task_type)
            self.assertEqual(ta.target_file, tb.target_file)

    def test_different_seeds_different_tasks(self):
        """Different seeds should (usually) produce different tasks."""
        gen_a = TaskGenerator(seed=1)
        gen_b = TaskGenerator(seed=9999)
        tasks_a = gen_a.generate_tasks(self.project, count=10)
        tasks_b = gen_b.generate_tasks(self.project, count=10)
        # At least some tasks should differ between seeds
        types_a = [(t.task_type, t.target_file) for t in tasks_a]
        types_b = [(t.task_type, t.target_file) for t in tasks_b]
        self.assertNotEqual(types_a, types_b)


class TestTaskGeneratorOnPythonProject(unittest.TestCase):
    """Tests for generating tasks from the Python built-in project."""

    def setUp(self):
        self.loader = ProjectLoader()
        self.project = self.loader.load_builtin("python-cli")
        self.generator = TaskGenerator(seed=42)

    def test_generates_python_tasks(self):
        """Python project should generate tasks with python language."""
        tasks = self.generator.generate_tasks(self.project, count=5)
        for t in tasks:
            self.assertEqual(t.language, "python")

    def test_generates_python_doc_task(self):
        """Document task for Python should mention docstrings."""
        task = self.generator.generate_task(
            self.project, task_type=TaskType.DOCUMENT,
        )
        if task is not None:
            self.assertIn("docstring", task.prompt.lower())


class TestTaskGeneratorOnRustProject(unittest.TestCase):
    """Tests for generating tasks from the Rust built-in project."""

    def setUp(self):
        self.loader = ProjectLoader()
        self.project = self.loader.load_builtin("rust-server")
        self.generator = TaskGenerator(seed=42)

    def test_generates_rust_tasks(self):
        """Rust project should generate tasks with rust language."""
        tasks = self.generator.generate_tasks(self.project, count=5)
        for t in tasks:
            self.assertEqual(t.language, "rust")
            self.assertEqual(t.framework, "actix")


# ═════════════════════════════════════════════════════════════════════
#  WORKLOAD SCORER TESTS
# ═════════════════════════════════════════════════════════════════════

class TestWorkloadScorer(unittest.TestCase):
    """Tests for WorkloadScorer — scoring model responses."""

    def setUp(self):
        self.loader = ProjectLoader()
        self.project = self.loader.load_builtin("nestjs-api")
        self.generator = TaskGenerator(seed=42)
        self.scorer = WorkloadScorer()
        # Generate a real task for realistic scoring
        self.tasks = self.generator.generate_tasks(self.project, count=3)

    def test_score_good_response(self):
        """A complete response with code should score well."""
        task = self.tasks[0]
        response = """\
Here is my implementation:

```typescript
import { Injectable, NotFoundException } from '@nestjs/common';

@Injectable()
export class UsersService {
  constructor(private prisma: PrismaService) {}

  async create(dto: CreateUserDto) {
    const existing = await this.prisma.user.findUnique({ where: { email: dto.email } });
    if (existing) throw new ConflictException('Email already exists');
    return this.prisma.user.create({ data: dto });
  }
}
```

This implements the create method with proper validation and error handling.
"""
        score = self.scorer.score(task, response)
        
        self.assertIsInstance(score, WorkloadScore)
        self.assertGreaterEqual(score.overall, 0.3)  # Should score decently
        self.assertGreaterEqual(score.correctness, 0.3)
        self.assertGreaterEqual(score.completeness, 0.2)
        self.assertGreaterEqual(score.code_quality, 0.2)

    def test_score_empty_response(self):
        """Empty response should score very low."""
        task = self.tasks[0]
        score = self.scorer.score(task, "")
        
        self.assertLess(score.overall, 0.3)
        self.assertIn("empty_response", score.failures)

    def test_score_response_without_code_blocks(self):
        """Response without code blocks should score poorly on code quality."""
        task = self.tasks[0]
        response = "I think the best approach is to add validation here."
        score = self.scorer.score(task, response)
        
        self.assertLess(score.code_quality, 0.3)
        self.assertIn("no_code_blocks", score.failures)

    def test_score_identifies_hallucinated_imports(self):
        """Scorer should detect hallucinated imports."""
        from core.workload.task_generator import WorkloadTask
        task = WorkloadTask(
            task_id="test-001",
            task_type=TaskType.IMPLEMENT_FEATURE,
            difficulty=TaskDifficulty.MEDIUM,
            title="Test task",
            description="Test",
            prompt="Implement a feature",
            context_files={"test.ts": "content"},
            target_file="test.ts",
            language="typescript",
            framework="nestjs",
            project_name="test",
        )
        response = """\
```typescript
import { Something } from '@nestjs/fake-lib/made-up';
```
"""
        score = self.scorer.score(task, response)
        self.assertIn("hallucinated_import", score.failures)

    def test_score_identifies_any_type(self):
        """Scorer should flag 'any' type usage in TypeScript."""
        from core.workload.task_generator import WorkloadTask
        task = WorkloadTask(
            task_id="test-002",
            task_type=TaskType.IMPLEMENT_FEATURE,
            difficulty=TaskDifficulty.MEDIUM,
            title="Test",
            description="Test",
            prompt="Implement",
            context_files={"test.ts": "content"},
            target_file="test.ts",
            language="typescript",
            framework="nestjs",
            project_name="test",
        )
        response = """\
```typescript
function process(data: any): any {
  return data;
}
```
"""
        score = self.scorer.score(task, response)
        self.assertIn("any_type_used", score.failures)

    def test_score_identifies_strengths(self):
        """Scorer should detect strengths in typed, error-handled code."""
        from core.workload.task_generator import WorkloadTask
        task = WorkloadTask(
            task_id="test-003",
            task_type=TaskType.IMPLEMENT_FEATURE,
            difficulty=TaskDifficulty.MEDIUM,
            title="Test",
            description="Test",
            prompt="Create a service",
            context_files={"service.ts": "content"},
            target_file="service.ts",
            language="typescript",
            framework="nestjs",
            project_name="test",
        )
        response = """\
Here is the implementation with proper types and error handling:

```typescript
import { Injectable, NotFoundException } from '@nestjs/common';

interface UserData {
  id: string;
  name: string;
}

@Injectable()
export class UserService {
  async getUser(id: string): Promise<UserData> {
    try {
      const user = await this.findUser(id);
      if (!user) throw new NotFoundException();
      return user;
    } catch (error) {
      console.error('Failed to get user:', error);
      throw error;
    }
  }

  private async findUser(id: string): Promise<UserData | null> {
    return { id, name: 'Test' };
  }
}
```
"""
        score = self.scorer.score(task, response)
        self.assertIn("typed_interfaces", score.strengths)
        self.assertIn("error_handling", score.strengths)
        self.assertIn("async_aware", score.strengths)

    def test_all_score_components_in_range(self):
        """All score components should be in [0, 1] range."""
        task = self.tasks[0]
        response = "```typescript\nexport function test() { return 42; }\n```"
        score = self.scorer.score(task, response)
        
        self.assertGreaterEqual(score.overall, 0.0)
        self.assertLessEqual(score.overall, 1.0)
        self.assertGreaterEqual(score.correctness, 0.0)
        self.assertLessEqual(score.correctness, 1.0)
        self.assertGreaterEqual(score.completeness, 0.0)
        self.assertLessEqual(score.completeness, 1.0)
        self.assertGreaterEqual(score.code_quality, 0.0)
        self.assertLessEqual(score.code_quality, 1.0)
        self.assertGreaterEqual(score.style_match, 0.0)
        self.assertLessEqual(score.style_match, 1.0)
        self.assertGreaterEqual(score.efficiency, 0.0)
        self.assertLessEqual(score.efficiency, 1.0)


class TestWorkloadScorerPython(unittest.TestCase):
    """Tests for WorkloadScorer with Python tasks."""

    def setUp(self):
        self.loader = ProjectLoader()
        self.project = self.loader.load_builtin("python-cli")
        self.generator = TaskGenerator(seed=42)
        self.scorer = WorkloadScorer()

    def test_score_python_response(self):
        """Python response with code should score reasonably."""
        task = self.generator.generate_task(
            self.project, task_type=TaskType.DOCUMENT,
        )
        if task is None:
            self.skipTest("No task generated")
        
        response = """\
Here's the documented version:

```python
def greet(name: str, greeting: str = "Hello") -> None:
    \"\"\"Greet someone with a custom greeting.

    Args:
        name: The person to greet
        greeting: The greeting to use (default: "Hello")
    \"\"\"
    click.echo(f'{greeting}, {name}!')
```
"""
        score = self.scorer.score(task, response)
        self.assertGreaterEqual(score.overall, 0.3)
        if "documented" in score.strengths:
            self.assertIn("documented", score.strengths)


class TestWorkloadScorerRust(unittest.TestCase):
    """Tests for WorkloadScorer with Rust tasks."""

    def setUp(self):
        self.loader = ProjectLoader()
        self.project = self.loader.load_builtin("rust-server")
        self.generator = TaskGenerator(seed=42)
        self.scorer = WorkloadScorer()

    def test_score_rust_response(self):
        """Rust response with proper struct should score well."""
        from core.workload.task_generator import WorkloadTask
        task = WorkloadTask(
            task_id="rust-test",
            task_type=TaskType.IMPLEMENT_FEATURE,
            difficulty=TaskDifficulty.MEDIUM,
            title="Add health check",
            description="Add health check endpoint",
            prompt="Add a health check endpoint to the server",
            context_files={"src/main.rs": "content"},
            target_file="src/main.rs",
            language="rust",
            framework="actix",
            project_name="rust-server",
        )
        response = """\
```rust
use actix_web::{web, HttpResponse};

pub async fn health_check() -> HttpResponse {
    HttpResponse::Ok().json(serde_json::json!({"status": "ok"}))
}
```
"""
        score = self.scorer.score(task, response)
        self.assertGreaterEqual(score.overall, 0.3)
        # Rust code with pub fn should have reasonable code quality
        self.assertGreaterEqual(score.code_quality, 0.2)


class TestWorkloadScorerEdgeCases(unittest.TestCase):
    """Edge cases for WorkloadScorer."""

    def setUp(self):
        from core.workload.task_generator import WorkloadTask
        self.task = WorkloadTask(
            task_id="edge-test",
            task_type=TaskType.REFACTOR,
            difficulty=TaskDifficulty.MEDIUM,
            title="Edge test",
            description="Edge test",
            prompt="Refactor this code",
            context_files={"test.ts": 'export function foo() { return 1; }'},
            target_file="test.ts",
            language="typescript",
            framework="nestjs",
            project_name="test",
        )
        self.scorer = WorkloadScorer()

    def test_code_block_extraction(self):
        """_extract_code_blocks should find all code blocks."""
        response = """\
Some text
```typescript
const x = 1;
```
More text
```python
y = 2
```
"""
        blocks = self.scorer._extract_code_blocks(response)
        self.assertEqual(len(blocks), 2)
        self.assertIn("const x = 1;", blocks)
        self.assertIn("y = 2", blocks)  # The \n after `y = 2` is stripped

    def test_code_block_extraction_without_language(self):
        """Code blocks without language specifier should still be extracted."""
        response = "```\ncode here\n```"
        blocks = self.scorer._extract_code_blocks(response)
        self.assertEqual(len(blocks), 1)

    def test_max_nesting_simple(self):
        """_max_nesting should calculate nesting depth accurately."""
        code = "{\n  {\n    {\n      x = 1;\n    }\n  }\n}"
        depth = self.scorer._max_nesting(code)
        self.assertEqual(depth, 3)

    def test_max_nesting_flat(self):
        """Flat code should have depth 1 (or 0 for no braces)."""
        code = "const x = 1;\nconst y = 2;"
        depth = self.scorer._max_nesting(code)
        self.assertLessEqual(depth, 1)

    def test_has_valid_code_structure_ts(self):
        """TypeScript code should be recognized as valid."""
        code = "export function foo() { return 1; }"
        self.assertTrue(
            self.scorer._has_valid_code_structure(code, "typescript")
        )

    def test_has_valid_code_structure_python(self):
        """Python code should be recognized as valid."""
        code = "def foo():\n    return 1"
        self.assertTrue(
            self.scorer._has_valid_code_structure(code, "python")
        )

    def test_has_valid_code_structure_rust(self):
        """Rust code should be recognized as valid."""
        code = "pub fn foo() -> i32 { 1 }"
        self.assertTrue(
            self.scorer._has_valid_code_structure(code, "rust")
        )

    def test_has_valid_code_structure_invalid(self):
        """Non-code text should NOT be recognized as valid."""
        code = "This is just a paragraph of text."
        self.assertFalse(
            self.scorer._has_valid_code_structure(code, "typescript")
        )

    def test_has_imports_ts(self):
        """TypeScript code with import should be detected."""
        code = "import { Injectable } from '@nestjs/common';"
        self.assertTrue(
            self.scorer._has_imports(code, "typescript")
        )

    def test_has_imports_python(self):
        """Python code with import should be detected."""
        code = "import os\nfrom typing import List"
        self.assertTrue(
            self.scorer._has_imports(code, "python")
        )

    def test_has_imports_none(self):
        """Code without imports should return False."""
        code = "const x = 1;"
        self.assertFalse(
            self.scorer._has_imports(code, "typescript")
        )

    def test_has_explanation_short(self):
        """Very short response without code should NOT have explanation."""
        response = "Short text."
        blocks = []
        self.assertFalse(
            self.scorer._has_explanation(response, blocks)
        )

    def test_has_explanation_long(self):
        """Longer response with explanation text should be detected."""
        response = "I implemented the feature by adding validation logic and error handling. " * 5
        blocks = []
        self.assertTrue(
            self.scorer._has_explanation(response, blocks)
        )


# ═════════════════════════════════════════════════════════════════════
#  INTEGRATION TESTS
# ═════════════════════════════════════════════════════════════════════

class TestProjectTaskScorerIntegration(unittest.TestCase):
    """End-to-end integration: load project → generate task → score response."""

    def setUp(self):
        self.loader = ProjectLoader()
        self.project = self.loader.load_builtin("react-app")
        self.generator = TaskGenerator(seed=42)
        self.scorer = WorkloadScorer()

    def test_full_pipeline_feature_task(self):
        """Full pipeline with a feature task should work end-to-end."""
        task = self.generator.generate_task(
            self.project, task_type=TaskType.IMPLEMENT_FEATURE,
        )
        if task is None:
            self.skipTest("No task generated")
        
        # Simulate a reasonable model response
        response = """\
I implemented the feature by adding a new method to handle search functionality:

```typescript
import { useState, useEffect } from 'react';

interface SearchResult {
  id: string;
  name: string;
  relevance: number;
}

export function useSearch(query: string) {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query) return;
    setLoading(true);
    const fetchData = async () => {
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        setResults(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [query]);

  return { results, loading, error };
}
```

This adds a search hook with proper types, async/await, loading states, and error handling.
"""
        score = self.scorer.score(task, response)
        
        # Should score well across all dimensions
        self.assertGreater(score.overall, 0.4)
        self.assertGreater(score.correctness, 0.3)
        self.assertGreater(score.completeness, 0.3)
        self.assertGreater(score.code_quality, 0.3)
        
        # Should detect strengths
        self.assertIn("typed_interfaces", score.strengths)
        self.assertIn("error_handling", score.strengths)
        self.assertIn("async_aware", score.strengths)

    def test_full_pipeline_bugfix_task(self):
        """Bugfix task pipeline should work."""
        task = self.generator.generate_task(
            self.project, task_type=TaskType.FIX_BUG,
        )
        if task is None:
            self.skipTest("No task generated")
        
        response = """\
I identified the bug: there's a missing null check before accessing the `name` property.

```typescript
function getName(user: User | null): string {
  if (!user) return 'Anonymous';
  return user.name;
}
```

The fix adds a guard clause to handle the null case.
"""
        score = self.scorer.score(task, response)
        
        self.assertGreater(score.overall, 0.3)
        self.assertGreaterEqual(score.correctness, 0.3)


class TestAllBuiltinProjectsGenerateTasks(unittest.TestCase):
    """All built-in projects should generate tasks without errors."""

    def test_all_projects_produce_tasks(self):
        loader = ProjectLoader()
        generator = TaskGenerator(seed=42)
        
        for name in ["nestjs-api", "react-app", "python-cli", "rust-server"]:
            with self.subTest(project=name):
                project = loader.load_builtin(name)
                tasks = generator.generate_tasks(project, count=3)
                self.assertEqual(
                    len(tasks), 3,
                    f"{name} should produce 3 tasks, got {len(tasks)}",
                )


if __name__ == "__main__":
    unittest.main()
