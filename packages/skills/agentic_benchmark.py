#!/usr/bin/env python3
"""
Agentic Benchmark Runner

Runs agentic/tool-use evaluation mode against LM Studio models.
Evaluates tool selection, planning, and constraint adherence.

Hard constraints enforced:
- NO execution of model-generated code
- NO real filesystem access outside sandbox
- NO network calls in core skills
- NO dynamic skill creation during runtime
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from skills.types import (
    Action, AgenticResponse, AgenticScore, SkillContext,
    SkillInput, SkillOutput,
)
from skills.registry import SkillRegistry, create_registry
from skills.agentic_prompts import AgenticPromptGenerator, AgenticPrompt
from core.evaluators.agentic import AgenticEvaluator, AgenticEvaluationResult


@dataclass
class AgenticBenchmarkResult:
    """Result from a single agentic benchmark prompt."""
    prompt: AgenticPrompt
    raw_response: str
    parsed_response: Optional[AgenticResponse]
    evaluation: AgenticEvaluationResult
    metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    run_index: int = 0


@dataclass
class AgenticBenchmarkSummary:
    """Aggregate summary of agentic benchmark results."""
    model_name: str
    total_prompts: int
    total_runs: int  # prompts × runs_per_prompt
    overall_agentic_score: float = 0.0
    mean_validity: float = 0.0
    mean_planning: float = 0.0
    mean_skill_correctness: float = 0.0
    mean_constraint_adherence: float = 0.0
    hallucination_rate: float = 0.0
    results: List[AgenticBenchmarkResult] = field(default_factory=list)
    lockfile_errors: List[str] = field(default_factory=list)

    def compute(self):
        """Compute aggregate statistics from individual results."""
        if not self.results:
            return

        n = len(self.results)

        self.overall_agentic_score = sum(
            r.evaluation.score.overall_agentic_score for r in self.results
        ) / n

        self.mean_validity = sum(
            r.evaluation.score.validity_score for r in self.results
        ) / n

        self.mean_planning = sum(
            r.evaluation.score.planning_score for r in self.results
        ) / n

        self.mean_skill_correctness = sum(
            r.evaluation.score.skill_correctness_score for r in self.results
        ) / n

        self.mean_constraint_adherence = sum(
            r.evaluation.score.constraint_adherence_score for r in self.results
        ) / n

        total_hallucinated = sum(
            r.evaluation.score.skills_outside_allowlist for r in self.results
        )
        total_choices = sum(
            r.evaluation.score.total_tool_choices for r in self.results
        )
        self.hallucination_rate = total_hallucinated / total_choices if total_choices > 0 else 0.0

    def to_dict(self) -> Dict:
        return {
            "model_name": self.model_name,
            "total_prompts": self.total_prompts,
            "total_runs": self.total_runs,
            "overall_agentic_score": self.overall_agentic_score,
            "mean_validity": self.mean_validity,
            "mean_planning": self.mean_planning,
            "mean_skill_correctness": self.mean_skill_correctness,
            "mean_constraint_adherence": self.mean_constraint_adherence,
            "hallucination_rate": self.hallucination_rate,
            "lockfile_errors": self.lockfile_errors,
        }


class AgenticBenchmark:
    """Runner for agentic/tool-use evaluation mode.

    Usage:
        runner = AgenticBenchmark(registry, client)
        summary = await runner.run_agentic_benchmark(
            model_name="qwopus3.5-9b-coder",
            num_prompts=5,
            runs_per_prompt=3,
        )
    """

    def __init__(
        self,
        registry: SkillRegistry,
        client=None,  # LMStudioClient
        lockfile_path: str = "modellens.lock",
    ):
        self.registry = registry
        self.client = client
        self.prompt_generator = AgenticPromptGenerator()

        # Finalize registry and check lockfile
        lock_errors = registry.finalize()
        self.lock_errors = lock_errors

    async def run_agentic_benchmark(
        self,
        model_name: str,
        num_prompts: int = 5,
        runs_per_prompt: int = 3,
        difficulty: Optional[str] = None,
        verbose: bool = False,
    ) -> AgenticBenchmarkSummary:
        """Run the full agentic benchmark suite.

        Args:
            model_name: Name of the model being tested
            num_prompts: Number of distinct agentic prompts to generate
            runs_per_prompt: How many times to run each prompt (for variance)
            difficulty: Filter prompts by difficulty
            verbose: Print progress information

        Returns:
            Aggregated AgenticBenchmarkSummary
        """
        summary = AgenticBenchmarkSummary(
            model_name=model_name,
            total_prompts=num_prompts,
            total_runs=num_prompts * runs_per_prompt,
            lockfile_errors=self.lock_errors,
        )

        if self.lock_errors:
            print("LOCK ERRORS DETECTED:")
            for err in self.lock_errors:
                print(f"  {err}")
            print("Benchmark results may be invalid!")

        # Generate prompts
        prompts = self.prompt_generator.generate_batch(num_prompts, difficulty)
        summary.total_prompts = len(prompts)

        for prompt_idx, prompt in enumerate(prompts):
            if verbose:
                print(f"\nPrompt {prompt_idx + 1}/{len(prompts)}: {prompt.task}")

            for run_idx in range(runs_per_prompt):
                # Build the full prompt for the model
                full_prompt = self._build_model_prompt(prompt)

                # Call the model (or use mock if no client)
                raw_response = await self._call_model(full_prompt)

                # Parse and evaluate
                result = self._evaluate_response(raw_response, prompt)

                # Store result
                bench_result = AgenticBenchmarkResult(
                    prompt=prompt,
                    raw_response=raw_response,
                    parsed_response=AgenticResponse.from_json(raw_response),
                    evaluation=result,
                    run_index=run_idx,
                )
                summary.results.append(bench_result)

                if verbose:
                    s = result.score
                    print(
                        f"  Run {run_idx + 1}: overall={s.overall_agentic_score:.2%} "
                        f"validity={s.validity_score:.2%} planning={s.planning_score:.2%} "
                        f"correctness={s.skill_correctness_score:.2%} constraints={s.constraint_adherence_score:.2%}"
                    )

        summary.compute()
        return summary

    def _build_model_prompt(self, prompt: AgenticPrompt) -> str:
        """Build the full prompt string for the model."""
        template = self.prompt_generator.get_strict_prompt_template(prompt.available_skills)
        task_block = f"""Task: {prompt.task}

Description: {prompt.description}

Input context: {prompt.input_context}

---

{template}
"""
        return task_block

    async def _call_model(self, prompt_text: str) -> str:
        """Call the LM Studio model. Falls back to mock if no client."""
        if self.client is None:
            # Mock response for testing
            return self._mock_response()

        try:
            messages = [{"role": "user", "content": prompt_text}]
            response_text, metrics = self.client.chat_completion(
                messages=messages,
                temperature=0.0,  # Deterministic
                max_tokens=500,
                stream=False,
            )
            return response_text
        except Exception as e:
            print(f"Model call failed: {e}")
            return ""

    def _mock_response(self) -> str:
        """Generate a mock response for testing without a real model."""
        return json.dumps({
            "actions": [
                {"skill": "read_file", "input": {"path": "src/index.ts"}},
                {"skill": "write_file", "input": {"path": "src/index.ts"}},
                {"skill": "diff", "input": {"a": "original", "b": "modified"}},
            ]
        })

    def _evaluate_response(
        self, raw_response: str, prompt: AgenticPrompt
    ) -> AgenticEvaluationResult:
        """Evaluate a model response against the prompt."""
        evaluator = AgenticEvaluator(
            available_skills=prompt.available_skills,
        )

        # Convert expected actions to Action objects
        expected_actions = [
            Action(skill=a["skill"], input=a.get("input", {}), order=i)
            for i, a in enumerate(prompt.expected_actions)
        ]

        return evaluator.evaluate(
            raw_response=raw_response,
            expected_actions=expected_actions,
            expected_params=prompt.expected_params,
        )


# ── Convenience Functions ─────────────────────────────────────────

def run_agentic_benchmark_sync(
    model_name: str,
    num_prompts: int = 5,
    runs_per_prompt: int = 3,
    lockfile_path: str = "modellens.lock",
    verbose: bool = True,
) -> AgenticBenchmarkSummary:
    """Synchronous wrapper for running agentic benchmarks."""
    import asyncio

    registry = create_registry(lockfile_path=lockfile_path)
    benchmark = AgenticBenchmark(registry=registry)

    return asyncio.run(
        benchmark.run_agentic_benchmark(
            model_name=model_name,
            num_prompts=num_prompts,
            runs_per_prompt=runs_per_prompt,
            verbose=verbose,
        )
    )


if __name__ == "__main__":
    # Quick test with mock responses (no real model needed)
    summary = run_agentic_benchmark_sync(
        model_name="test-model",
        num_prompts=2,
        runs_per_prompt=1,
        verbose=True,
    )

    print("\n" + "=" * 60)
    print("AGENTIC BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"Model: {summary.model_name}")
    print(f"Overall Agentic Score: {summary.overall_agentic_score:.2%}")
    print(f"  Validity:              {summary.mean_validity:.2%}")
    print(f"  Planning:              {summary.mean_planning:.2%}")
    print(f"  Skill Correctness:     {summary.mean_skill_correctness:.2%}")
    print(f"  Constraint Adherence:  {summary.mean_constraint_adherence:.2%}")
    print(f"  Hallucination Rate:    {summary.hallucination_rate:.2%}")
    if summary.lockfile_errors:
        print(f"\nLOCK ERRORS: {len(summary.lockfile_errors)}")
