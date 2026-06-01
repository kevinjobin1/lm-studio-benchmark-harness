"""
Core package - benchmark framework + agentic evaluators.
"""

from core.benchmark import (
    Benchmark,
    BenchmarkResult,
    BenchmarkSuite,
    LMStudioClient,
    MemoryMonitor,
)

from core.evaluators.agentic import (
    AgenticEvaluator,
    AgenticEvaluationResult,
    evaluate_agentic_response,
    get_hallucination_rate,
)

__all__ = [
    "Benchmark",
    "BenchmarkResult",
    "BenchmarkSuite",
    "LMStudioClient",
    "MemoryMonitor",
    "AgenticEvaluator",
    "AgenticEvaluationResult",
    "evaluate_agentic_response",
    "get_hallucination_rate",
]
