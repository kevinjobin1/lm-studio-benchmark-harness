"""
Workload Runner — runs models against workload tasks and collects results.
Emits typed events via the EventBus for observability.
"""

import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from .task_generator import WorkloadTask, TaskType
from .workload_scorer import WorkloadScorer, WorkloadScore

from events import (
    EventBus,
    default_bus,
    TokenGeneratedEvent,
    CompletionEvent,
    RunLifecycleEvent,
    MetricEvent,
    ErrorEvent,
)


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

    Emits events via EventBus for observability:
    - RunLifecycleEvent at batch start/completion
    - TokenGeneratedEvent for each token (when streaming=True)
    - CompletionEvent after each task response
    - MetricEvent for score components
    - ErrorEvent on failures
    """

    def __init__(
        self,
        api_base: str = "http://localhost:1234/v1",
        api_key: str = "lm-studio",
        model: str = "local-model",
        scorer: Optional[WorkloadScorer] = None,
        event_bus: Optional[EventBus] = None,
        stream: bool = False,
    ):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.scorer = scorer or WorkloadScorer()
        self.event_bus = event_bus or default_bus
        self.stream = stream
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
        source = f"workload.{task.project_name}"
        run_id = f"workload_{task.project_name}_{task.task_id[:8]}"

        if verbose:
            print(f"  Running: {task.title}")

        # Emit run lifecycle: task started
        self.event_bus.emit_sync(RunLifecycleEvent(
            status="started",
            model=self.model,
            workload=task.project_name,
            run_id=run_id,
            source=source,
        ))

        # Build messages with context
        messages = self._build_messages(task)

        # Measure response
        start_time = time.time()
        try:
            if self.stream:
                # ── Streaming path: emit TokenGeneratedEvent per chunk ──
                response_text = ""
                first_token_time = None
                token_index = 0

                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2000,
                    stream=True,
                )

                for chunk in stream:
                    now = time.time()
                    if first_token_time is None:
                        first_token_time = now

                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        token_text = delta.content
                        response_text += token_text

                        # Emit token event
                        timing_ms = (now - start_time) * 1000
                        self.event_bus.emit_sync(TokenGeneratedEvent(
                            model=self.model,
                            token=token_text,
                            index=token_index,
                            timing_ms=timing_ms,
                            provider=self.api_base,
                            run_id=run_id,
                            source=source,
                        ))
                        token_index += 1

                total_time = time.time() - start_time
                tokens_used = token_index

                ttft_ms = (first_token_time - start_time) * 1000 if first_token_time else total_time * 1000
            else:
                # ── Non-streaming path ──
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
                ttft_ms = total_time * 1000  # Approximate for non-streaming

            tokens_per_second = (tokens_used / total_time) if total_time > 0 else 0

            # Score the response
            score_result = self.scorer.score(task, response_text)

            # Emit completion event
            self.event_bus.emit_sync(CompletionEvent(
                model=self.model,
                response=response_text,
                tokens_used=tokens_used,
                latency_ms=total_time * 1000,
                ttft_ms=ttft_ms,
                tokens_per_second=tokens_per_second,
                provider=self.api_base,
                run_id=run_id,
                source=source,
                success=True,
            ))

            # Emit metric events for each score component
            self.event_bus.emit_sync(MetricEvent(
                name="workload.score",
                value=score_result.overall,
                tags={
                    "task_id": task.task_id,
                    "task_type": task.task_type.value,
                    "project": task.project_name,
                },
                model=self.model,
                run_id=run_id,
                source=source,
            ))
            for component_name in ("correctness", "completeness", "code_quality", "style_match", "efficiency"):
                value = getattr(score_result, component_name, 0.0)
                self.event_bus.emit_sync(MetricEvent(
                    name=f"workload.score.{component_name}",
                    value=value,
                    tags={
                        "task_id": task.task_id,
                        "task_type": task.task_type.value,
                        "project": task.project_name,
                    },
                    model=self.model,
                    run_id=run_id,
                    source=source,
                ))

            # Emit run lifecycle: completed
            self.event_bus.emit_sync(RunLifecycleEvent(
                status="completed",
                model=self.model,
                workload=task.project_name,
                run_id=run_id,
                source=source,
                duration_ms=total_time * 1000,
            ))

            if verbose:
                print(f"  ✓ Score: {score_result.overall:.3f} ({len(response_text.split(chr(10)))} lines, {total_time:.1f}s, {tokens_used} tok)")

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

        except Exception as e:
            total_time = time.time() - start_time

            # Emit error event
            self.event_bus.emit_sync(ErrorEvent(
                message=f"Workload task failed: {e}",
                exception=type(e).__name__,
                component="workload_runner",
                run_id=run_id,
                source=source,
                severity="error",
            ))

            # Emit completion event (failed)
            self.event_bus.emit_sync(CompletionEvent(
                model=self.model,
                response="",
                tokens_used=0,
                latency_ms=total_time * 1000,
                ttft_ms=0,
                tokens_per_second=0,
                provider=self.api_base,
                run_id=run_id,
                source=source,
                success=False,
                error=str(e),
            ))

            # Emit run lifecycle: failed
            self.event_bus.emit_sync(RunLifecycleEvent(
                status="failed",
                model=self.model,
                workload=task.project_name,
                run_id=run_id,
                source=source,
                duration_ms=total_time * 1000,
                error=str(e),
            ))

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
        if not tasks:
            return []

        source = f"workload.{tasks[0].project_name}"
        run_id = f"workload_batch_{tasks[0].project_name}_{int(time.time())}"

        # Emit batch lifecycle: started
        self.event_bus.emit_sync(RunLifecycleEvent(
            status="started",
            model=self.model,
            workload=tasks[0].project_name,
            run_id=run_id,
            source=source,
        ))

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
                        results.append(self._error_result(task, str(e)))
            results = self._sort_by_task_order(results, tasks)
        else:
            results = []
            for i, task in enumerate(tasks):
                if verbose:
                    print(f"  [{i+1}/{len(tasks)}] ", end="")
                result = self.run_task(task, verbose)
                results.append(result)

        # Calculate aggregate metrics
        valid_results = [r for r in results if r.score > 0]
        if valid_results:
            avg_score = sum(r.score for r in valid_results) / len(valid_results)
            avg_time = sum(r.response_time_ms for r in valid_results) / len(valid_results)
            total_tokens = sum(r.tokens_used for r in valid_results)

            self.event_bus.emit_sync(MetricEvent(
                name="workload.batch.avg_score",
                value=avg_score,
                tags={
                    "project": tasks[0].project_name,
                    "model": self.model,
                    "num_tasks": str(len(tasks)),
                },
                model=self.model,
                run_id=run_id,
                source=source,
            ))
            self.event_bus.emit_sync(MetricEvent(
                name="workload.batch.avg_latency_ms",
                value=avg_time,
                tags={
                    "project": tasks[0].project_name,
                    "model": self.model,
                },
                model=self.model,
                run_id=run_id,
                source=source,
            ))
            self.event_bus.emit_sync(MetricEvent(
                name="workload.batch.total_tokens",
                value=float(total_tokens),
                tags={
                    "project": tasks[0].project_name,
                    "model": self.model,
                },
                model=self.model,
                run_id=run_id,
                source=source,
            ))

        # Emit batch lifecycle: completed
        batch_duration = sum(r.response_time_ms for r in results)
        self.event_bus.emit_sync(RunLifecycleEvent(
            status="completed",
            model=self.model,
            workload=tasks[0].project_name,
            run_id=run_id,
            source=source,
            duration_ms=batch_duration,
        ))

        return results

    def _error_result(self, task: WorkloadTask, error_msg: str) -> WorkloadResult:
        """Create a failed WorkloadResult from an exception."""
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
            failures=[error_msg],
            strengths=[],
            project_name=task.project_name,
            target_file=task.target_file,
            language=task.language,
            framework=task.framework,
        )

    def _sort_by_task_order(
        self, results: List[WorkloadResult], tasks: List[WorkloadTask]
    ) -> List[WorkloadResult]:
        """Restore task order after parallel execution."""
        task_map = {r.task_id: r for r in results}
        return [task_map[t.task_id] for t in tasks if t.task_id in task_map]

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
