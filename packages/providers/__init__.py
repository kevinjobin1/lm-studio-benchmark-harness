"""Provider adapters and framework integrations for ModelLens."""

from .base import ProviderAdapter, Model, RunRequest, RunResult, ProviderMetrics, APICallMetrics

# Lazy-load OllamaClient — fails gracefully if deps are missing
try:
    from .ollama import OllamaClient
except (ImportError, ModuleNotFoundError):
    OllamaClient = None  # type: ignore

# Shared task mappings (no dependencies needed)
LM_EVAL_TASK_MAPPING = {
    "mmlu_pro": "mmlu",
    "gsm8k": "gsm8k",
    "aime": "aime",
    "humaneval": "humaneval",
    "if_eval": "ifeval",
}

OPENBENCH_TASK_MAPPING = {
    "mmlu_pro": "mmlu_pro",
    "gsm8k": "gsm8k",
    "aime": "aime_2024",
    "humaneval": "humaneval",
}


def run_lm_eval_benchmarks(base_url, api_key, model_name, benchmark_names, limit=None):
    """Run LM Eval benchmarks (lazy import to avoid requiring lm_eval at startup)."""
    from .lm_eval_integration import run_lm_eval_benchmarks as _run
    return _run(base_url, api_key, model_name, benchmark_names, limit)


def run_openbench_benchmarks(base_url, model_name, benchmark_names, limit=None, install_if_missing=False):
    """Run OpenBench benchmarks (lazy import to avoid requiring openbench at startup)."""
    from .openbench_integration import run_openbench_benchmarks as _run
    return _run(base_url, model_name, benchmark_names, limit, install_if_missing)


__all__ = [
    "ProviderAdapter",
    "APICallMetrics",
    "Model",
    "RunRequest",
    "RunResult",
    "ProviderMetrics",
    "OllamaClient",
    "run_lm_eval_benchmarks",
    "LM_EVAL_TASK_MAPPING",
    "run_openbench_benchmarks",
    "OPENBENCH_TASK_MAPPING",
]
