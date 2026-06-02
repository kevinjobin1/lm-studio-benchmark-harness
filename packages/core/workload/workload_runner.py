"""
Workload Runner — runs models against workload tasks and collects results.
"""

import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from .task_generator import WorkloadTask, TaskType
from .workload_scorer import WorkloadScorer, WorkloadScore


@dataclass
class WorkloadResult:
    """Result from evaluating a model on a single workload task."""
    task_id: str
    model: str
    provider: str
    task_type: str
    difficulty: str
    title: str
    prompt: str
    
    # Model output
    response: str
    response_time_ms: float
    tokens_used: int
    
    # Scoring
    score: float
    score_components: Dict[str, float]
    failures: List[str]
    strengths: List[str]
    
    # Metadata
    project_name: str
    target_file: str
    language: str
    framework: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class WorkloadRunner:
    """Runs workload evaluation tasks against a model.
    
    Connects to a provider (LM Studio, Ollama), sends tasks,
    collects responses, and scores them.
    """
    
    def __init__(
        self,
        api_base: str = "http://localhost:1234/v1",
        api_key: str = "lm-studio",
        model: str = "local-model",
        scorer: Optional[WorkloadScorer] = None,
    ):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.scorer = scorer or WorkloadScorer()
        self._client = None
    
    @property
    def client(self):
        """Lazy-init OpenAI client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(base_url=self.api_base, api_key=self.api_key)
        return self._client
    
    def run_task(self, task: WorkloadTask, verbose: bool = False) -> WorkloadResult:
        """Run a single workload task against the model.
        
        Args:
            task: The workload task to evaluate
            verbose: Print progress information
            
        Returns:
            WorkloadResult with response and score
        """
        if verbose:
            print(f"  Running: {task.title}")
        
        # Build messages with context
        messages = self._build_messages(task)
        
        # Measure response
        start_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=2000,
            )
            response_text = response.choices[0].message.content or ""
            total_time = time.time() - start_time
            
            tokens_used = (
                (response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0)
                if hasattr(response, 'usage') and response.usage
                else len(response_text) // 4
            )
            
        except Exception as e:
            if verbose:
                print(f"  ✗ Error: {e}")
            return WorkloadResult(
                task_id=task.task_id,
                model=self.model,
                provider=self.api_base,
                task_type=task.task_type.value,
                difficulty=task.difficulty.value,
                title=task.title,
                prompt=task.prompt,
                response="",
                response_time_ms=0,
                tokens_used=0,
                score=0.0,
                score_components={"error": 0.0},
                failures=[str(e)],
                strengths=[],
                project_name=task.project_name,
                target_file=task.target_file,
                language=task.language,
                framework=task.framework,
            )
        
        # Score the response
        score_result = self.scorer.score(task, response_text)
        
        if verbose:
            print(f"  ✓ Score: {score_result.overall:.3f} ({response_text.count(chr(10)) + 1} lines, {total_time:.1f}s)")
        
        return WorkloadResult(
            task_id=task.task_id,
            model=self.model,
            provider=self.api_base,
            task_type=task.task_type.value,
            difficulty=task.difficulty.value,
            title=task.title,
            prompt=task.prompt,
            response=response_text,
            response_time_ms=total_time * 1000,
            tokens_used=tokens_used,
            score=score_result.overall,
            score_components={
                "correctness": score_result.correctness,
                "completeness": score_result.completeness,
                "code_quality": score_result.code_quality,
                "style_match": score_result.style_match,
                "efficiency": score_result.efficiency,
            },
            failures=score_result.failures,
            strengths=score_result.strengths,
            project_name=task.project_name,
            target_file=task.target_file,
            language=task.language,
            framework=task.framework,
        )
    
    def run_batch(
        self,
        tasks: List[WorkloadTask],
        verbose: bool = True,
        parallel: bool = False,
        max_workers: int = 3,
    ) -> List[WorkloadResult]:
        """Run multiple tasks against the model.
        
        Args:
            tasks: List of workload tasks
            verbose: Print progress
            parallel: Run tasks in parallel (experimental)
            max_workers: Max parallel workers
            
        Returns:
            List of WorkloadResult
        """
        if parallel:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self.run_task, task, verbose): task for task in tasks}
                for i, future in enumerate(as_completed(futures)):
                    task = futures[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        print(f"  ✗ [{i+1}/{len(tasks)}] {task.title}: {e}")
                        results.append(WorkloadResult(
                            task_id=task.task_id,
                            model=self.model,
                            provider=self.api_base,
                            task_type=task.task_type.value,
                            difficulty=task.difficulty.value,
                            title=task.title,
                            prompt=task.prompt,
                            response="",
                            response_time_ms=0,
                            tokens_used=0,
                            score=0.0,
                            score_components={"error": 0.0},
                            failures=[str(e)],
                            strengths=[],
                            project_name=task.project_name,
                            target_file=task.target_file,
                            language=task.language,
                            framework=task.framework,
                        ))
            return results
        
        results = []
        for i, task in enumerate(tasks):
            if verbose:
                print(f"  [{i+1}/{len(tasks)}] ", end="")
            result = self.run_task(task, verbose)
            results.append(result)
        
        return results
    
    def _build_messages(self, task: WorkloadTask) -> List[Dict[str, str]]:
        """Build chat messages from a task."""
        system = f"""You are an expert {task.language} developer working on a {task.framework} project.
Your task is to write production-quality code following the project's existing patterns.

Rules:
- Write complete, working code
- Follow the existing code style and patterns
- Use proper types and error handling
- Include imports and exports
- Keep changes minimal and focused
- Explain your changes briefly
"""
        
        # Build context string
        context_str = ""
        for file_path, content in task.context_files.items():
            context_str += f"\n### {file_path}\n```{task.language}\n{content}\n```\n"
        
        user = f"""Project: {task.project_name}
Framework: {task.framework}
Target file: {task.target_file}

Context files:
{context_str}

Task:
{task.prompt}
"""
        
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
