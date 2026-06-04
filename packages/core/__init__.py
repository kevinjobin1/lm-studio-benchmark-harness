"""
Core package - benchmark framework + agentic evaluators + trace capture.
"""

from core.benchmark import (
    Benchmark,
    BenchmarkResult,
    BenchmarkSuite,
    MemoryMonitor,
)

# LMStudioClient is deprecated — kept for backward compatibility.
# New code should use `from providers import OpenAICompatibleProvider`.
from core.benchmark import LMStudioClient  # noqa: F401

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

from core.cache import (
    ContentAddressableCache,
    open_cache,
    cache_result,
    load_cached,
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
    # Cache
    "ContentAddressableCache",
    "open_cache",
    "cache_result",
    "load_cached",
]
