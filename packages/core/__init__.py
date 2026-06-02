"""
Core package - benchmark framework + agentic evaluators + trace capture.
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

from core.trace_schema import (
    TokenEvent,
    TraceEvent,
    TraceMetrics,
    TraceArtifacts,
    Trace,
)

from core.trace_capture import (
    TraceCapture,
    wrap_stream,
)

__all__ = [
    # Benchmark
    "Benchmark",
    "BenchmarkResult",
    "BenchmarkSuite",
    "LMStudioClient",
    "MemoryMonitor",
    # Agentic
    "AgenticEvaluator",
    "AgenticEvaluationResult",
    "evaluate_agentic_response",
    "get_hallucination_rate",
    # Trace V2
    "TokenEvent",
    "TraceEvent",
    "TraceMetrics",
    "TraceArtifacts",
    "Trace",
    "TraceCapture",
    "wrap_stream",
]
