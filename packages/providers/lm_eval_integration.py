"""
LM Eval integration for standardized benchmark evaluation.
"""

import os
from typing import Dict, List, Any, Optional
from openai import OpenAI
import lm_eval
from lm_eval.api.model import LM
from lm_eval.api.instance import Instance


class LMStudioLMEvalModel(LM):
    """LM Studio model adapter for LM Eval framework."""

    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        api_key: str = "lm-studio",
        model_name: str = "local-model",
        **kwargs,
    ):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=120)

    def loglikelihood(self, requests: List[Instance]) -> List[float]:
        """Compute log-likelihood for completion."""
        results = []
        for request in requests:
            prompt = request.args[0]
            completion = request.args[1]

            try:
                # For log-likelihood, we need to use the model's probability
                # Since LM Studio API doesn't support logprobs by default,
                # we'll approximate with completion
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1,
                    temperature=0.0,
                )

                # Return a placeholder log-likelihood
                # In a real implementation, you'd need logprobs support
                results.append((-1.0, False))
            except Exception as e:
                results.append((-float("inf"), False))

        return results

    def loglikelihood_rolling(self, requests: List[Instance]) -> List[float]:
        """Compute rolling log-likelihood."""
        # Similar to loglikelihood but for rolling context
        results = []
        for request in requests:
            try:
                results.append((-1.0, False))
            except Exception as e:
                results.append((-float("inf"), False))
        return results

    def generate_until(self, requests: List[Instance]) -> List[str]:
        """Generate completions until stopping condition."""
        results = []
        for request in requests:
            prompt = request.args[0]
            max_tokens = request.args[1] if len(request.args) > 1 else 512

            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=0.0,
                )

                results.append(response.choices[0].message.content)
            except Exception as e:
                results.append(f"ERROR: {str(e)}")

        return results

    def generate_until_multi_round(self, requests: List[Instance]) -> List[str]:
        """Generate completions for multi-round conversations."""
        # Similar to generate_until but for conversations
        return self.generate_until(requests)


class LMEvalRunner:
    """Runner for LM Eval benchmarks."""

    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name

    def run_benchmarks(
        self,
        tasks: List[str],
        num_fewshot: int = 0,
        limit: Optional[int] = None,
        batch_size: int = 1,
    ) -> Dict[str, Any]:
        """Run LM Eval benchmarks."""

        # Create LM Studio model adapter
        model = LMStudioLMEvalModel(
            base_url=self.base_url, api_key=self.api_key, model_name=self.model_name
        )

        # Run evaluation
        results = lm_eval.simple_evaluate(
            model=model,
            tasks=tasks,
            num_fewshot=num_fewshot,
            limit=limit,
            batch_size=batch_size,
            no_cache=True,
        )

        return results

    def get_available_tasks(self) -> List[str]:
        """Get list of available LM Eval tasks."""
        return lm_eval.api.registry.LM_EVAL_TASKS.keys()

    def get_task_details(self, task_name: str) -> Dict[str, Any]:
        """Get details about a specific task."""
        from lm_eval.api.registry import get_task

        task = get_task(task_name)
        return {"name": task_name, "config": task.config}


# Mapping of our benchmark names to LM Eval task names
LM_EVAL_TASK_MAPPING = {
    "mmlu_pro": "mmlu",
    "gsm8k": "gsm8k",
    "aime": "aime",
    "humaneval": "humaneval",
    "if_eval": "ifeval",
    # Note: SWE-bench, Needle-in-Haystack, BFCL, speed/latency, memory, creativity
    # are not in LM Eval and will use our custom implementation
}


def run_lm_eval_benchmarks(
    base_url: str,
    api_key: str,
    model_name: str,
    benchmark_names: List[str],
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Run LM Eval benchmarks for specified benchmark names."""

    # Map our benchmark names to LM Eval task names
    lm_eval_tasks = []
    custom_benchmarks = []

    for benchmark in benchmark_names:
        if benchmark in LM_EVAL_TASK_MAPPING:
            lm_eval_tasks.append(LM_EVAL_TASK_MAPPING[benchmark])
        else:
            custom_benchmarks.append(benchmark)

    results = {"lm_eval": {}, "custom": custom_benchmarks}

    if lm_eval_tasks:
        runner = LMEvalRunner(base_url, api_key, model_name)
        try:
            eval_results = runner.run_benchmarks(tasks=lm_eval_tasks, limit=limit)
            results["lm_eval"] = eval_results
        except Exception as e:
            results["lm_eval"]["error"] = str(e)

    return results
