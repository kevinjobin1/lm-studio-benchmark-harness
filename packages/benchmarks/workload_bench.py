"""
Workload Evaluation Benchmark — evaluates models on real-world project tasks.

Integrates with the core workload evaluation framework to register
it as a standard benchmark within the Model Lens system.
"""

from typing import Dict, List, Any, Optional
from core.benchmark import Benchmark, BenchmarkResult


class WorkloadBenchmark(Benchmark):
    """Workload evaluation benchmark — tests models on real project tasks.
    
    This benchmark:
    1. Loads a real project (built-in samples, local repos, or git URLs)
    2. Generates coding tasks from the project files
    3. Runs the model against each task
    4. Scores responses on correctness, completeness, code quality, style, and efficiency
    """
    
    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        self.project_source = config.get("project_source", "builtin")
        self.project_name = config.get("project_name", "nestjs-api")
        self.task_count = config.get("task_count", 10)
        self.verbose = config.get("verbose", False)
    
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run the workload evaluation benchmark."""
        from core.workload import (
            ProjectLoader, TaskGenerator, WorkloadRunner, WorkloadScorer,
        )
        
        # 1. Load project
        loader = ProjectLoader()
        if self.project_source == "builtin":
            project = loader.load_builtin(self.project_name)
        else:
            project = loader.load_project(self.project_source)
        
        if self.verbose:
            print(f"  Loaded project: {project.name} ({project.language}/{project.framework})")
            print(f"  Files: {project.total_files}, Lines: {project.total_lines}")
        
        # 2. Generate tasks
        generator = TaskGenerator()
        tasks = generator.generate_tasks(project, count=min(samples, self.task_count))
        
        if self.verbose:
            print(f"  Generated {len(tasks)} tasks")
            for t in tasks:
                print(f"    [{t.task_type.value}] {t.title}")
        
        # 3. Run evaluation
        scorer = WorkloadScorer()
        runner = WorkloadRunner(
            api_base=self.client.client.base_url if hasattr(self.client, 'client') else "http://localhost:1234/v1",
            model=self.client.model_name if hasattr(self.client, 'model_name') else "local-model",
            scorer=scorer,
        )
        
        results = runner.run_batch(tasks, verbose=self.verbose)
        
        # 4. Convert to benchmark results
        benchmark_results = []
        for r in results:
            benchmark_results.append(BenchmarkResult(
                benchmark_name=f"workload_{self.project_name}",
                metric_name=r.task_type,
                score=r.score,
                metadata={
                    "task_id": r.task_id,
                    "title": r.title,
                    "model": r.model,
                    "difficulty": r.difficulty,
                    "language": r.language,
                    "framework": r.framework,
                    "project": r.project_name,
                    "target_file": r.target_file,
                    "response_time_ms": r.response_time_ms,
                    "tokens_used": r.tokens_used,
                    "score_components": r.score_components,
                    "failures": r.failures,
                    "strengths": r.strengths,
                    "response_preview": r.response[:200] if r.response else "",
                }
            ))
        
        # Add overall score
        if results:
            overall = sum(r.score for r in results) / len(results)
            benchmark_results.append(BenchmarkResult(
                benchmark_name=f"workload_{self.project_name}",
                metric_name="overall",
                score=overall,
                metadata={
                    "total_tasks": len(results),
                    "project": project.name,
                    "language": project.language,
                    "framework": project.framework,
                }
            ))
            
            if self.verbose:
                print(f"\n  Overall workload score: {overall:.3f}")
        
        return benchmark_results


# ── Factory ───────────────────────────────────────────────────────

def create_workload_benchmark(client, config: Dict[str, Any]) -> WorkloadBenchmark:
    """Factory function to create a workload benchmark instance."""
    return WorkloadBenchmark(client, config)


# ── Built-in project names ───────────────────────────────────────

BUILTIN_PROJECTS = {
    "nestjs-api": "NestJS REST API with Prisma, Auth, and Kafka",
    "react-app": "React dashboard with state management and components",
    "python-cli": "Python CLI tool with Click and async I/O",
    "rust-server": "Rust HTTP server with Actix-web",
}
