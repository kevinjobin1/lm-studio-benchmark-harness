"""
SWE-bench Lite benchmark for coding agent evaluation.
Simplified version for demonstration.
"""

from typing import Dict, List, Any
from core import Benchmark, BenchmarkResult


class SWEBenchLiteBenchmark(Benchmark):
    """SWE-bench Lite benchmark for evaluating coding agent capabilities."""
    
    # Simplified SWE-bench Lite tasks (for demonstration)
    TASKS = [
        {
            "task_id": "swe-bench-lite-1",
            "repo": "django/django",
            "problem_statement": "Fix a bug where the ORM doesn't properly handle null values in foreign key relationships.",
            "base_commit": "abc123",
            "hints": ["Check the foreign key field definition", "Look at the null handling in queries"]
        },
        {
            "task_id": "swe-bench-lite-2",
            "repo": "matplotlib/matplotlib",
            "problem_statement": "Add support for custom color palettes in scatter plots.",
            "base_commit": "def456",
            "hints": ["Extend the scatter plot function", "Add a palette parameter"]
        },
        {
            "task_id": "swe-bench-lite-3",
            "repo": "numpy/numpy",
            "problem_statement": "Optimize the matrix multiplication function for large sparse matrices.",
            "base_commit": "ghi789",
            "hints": ["Use sparse matrix operations", "Consider block-based computation"]
        },
        {
            "task_id": "swe-bench-lite-4",
            "repo": "pallets/flask",
            "problem_statement": "Fix a memory leak in the session handling code.",
            "base_commit": "jkl012",
            "hints": ["Check session cleanup", "Look at garbage collection"]
        },
        {
            "task_id": "swe-bench-lite-5",
            "repo": "scikit-learn/scikit-learn",
            "problem_statement": "Add early stopping support to the gradient boosting classifier.",
            "base_commit": "mno345",
            "hints": ["Add validation split parameter", "Implement early stopping logic"]
        }
    ]
    
    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        self.max_tasks = config.get("max_tasks", 20)
        
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run SWE-bench Lite benchmark (simplified evaluation)."""
        import random
        
        tasks = random.choices(self.TASKS, k=min(samples, min(self.max_tasks, len(self.TASKS))))
        results = []
        
        for i, task in enumerate(tasks):
            # For a full implementation, this would:
            # 1. Clone the repository
            # 2. Checkout the base commit
            # 3. Have the agent make changes
            # 4. Run tests to verify
            
            # Simplified: evaluate the agent's understanding and approach
            prompt = f"""Repository: {task['repo']}
Problem: {task['problem_statement']}
Hints: {', '.join(task['hints'])}

Provide a detailed technical plan covering:
1. Problem understanding
2. Files to examine
3. Specific changes needed
4. Verification approach

Be specific and include file paths, function names, and code patterns."""
            
            messages = [
                {"role": "system", "content": "You are an expert software engineer. Provide detailed, technical, and specific plans. Always mention files to examine, specific changes to make, and how to verify correctness."},
                {"role": "user", "content": prompt}
            ]
            
            try:
                response, _ = self.client.chat_completion(
                    messages=messages,
                    temperature=0.0,
                    max_tokens=1000
                )
                
                if self.verbose:
                    print(f"\n[VERBOSE swe_bench #{i+1}] Task: {task['task_id']} ({task['repo']})")
                    print(f"[VERBOSE swe_bench #{i+1}] Response ({len(response)} chars): {repr(response[:200])}")
                
                # Simplified scoring based on response quality
                quality_score = self._evaluate_response_quality(response, task)
                
                if self.verbose:
                    print(f"[VERBOSE swe_bench #{i+1}] Quality score: {quality_score:.2f}")
                
                results.append(BenchmarkResult(
                    benchmark_name="swe_bench_lite",
                    metric_name="task_quality",
                    score=quality_score,
                    metadata={
                        "task_id": task["task_id"],
                        "repo": task["repo"],
                        "response_length": len(response)
                    }
                ))
                
                print(f"  Progress: {i+1}/{len(tasks)} | Avg quality: {sum(r.score for r in results)/(i+1):.2f}")
                    
            except Exception as e:
                print(f"  Error on task {i+1}: {e}")
                results.append(BenchmarkResult(
                    benchmark_name="swe_bench_lite",
                    metric_name="task_quality",
                    score=0.0,
                    metadata={"error": str(e)}
                ))
        
        avg_quality = sum(r.score for r in results) / len(results) if results else 0
        results.append(BenchmarkResult(
            benchmark_name="swe_bench_lite",
            metric_name="overall_quality",
            score=avg_quality,
            metadata={"total_tasks": len(tasks)}
        ))
        
        print(f"\n  SWE-bench Lite Quality Score: {avg_quality:.2f}/1.00")
        
        return results
    
    def _evaluate_response_quality(self, response: str, task: Dict) -> float:
        """Evaluate the quality of the agent's response (simplified)."""
        score = 0.0
        
        # Check for key elements
        if "understand" in response.lower() or "problem" in response.lower():
            score += 0.25
        if "file" in response.lower() or "examine" in response.lower():
            score += 0.25
        if "change" in response.lower() or "fix" in response.lower():
            score += 0.25
        if "test" in response.lower() or "verify" in response.lower():
            score += 0.25
        
        # Ensure score is in [0, 1]
        return min(score, 1.0)
