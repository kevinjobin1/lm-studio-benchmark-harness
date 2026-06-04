"""
Core benchmark framework for local AI model evaluation.
"""

import time
import psutil
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import yaml

from packages.logging import get_logger
from providers.base import APICallMetrics, ProviderAdapter

try:
    from events import (
        EventBus, default_bus,
        RunLifecycleEvent, CompletionEvent, MetricEvent, ErrorEvent,
    )
    _EVENTS_AVAILABLE = True
except ImportError:
    EventBus = None  # type: ignore
    default_bus = None  # type: ignore
    RunLifecycleEvent = None  # type: ignore
    CompletionEvent = None  # type: ignore
    MetricEvent = None  # type: ignore
    ErrorEvent = None  # type: ignore
    _EVENTS_AVAILABLE = False

logger = get_logger(__name__)


@dataclass
class BenchmarkResult:
    """Stores results from a single benchmark run."""
    benchmark_name: str
    metric_name: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ── Legacy alias for backward compatibility ────────────────────────
# LMStudioClient was a stand-alone OpenAI wrapper that duplicated
# OpenAICompatibleProvider from packages/providers/. It is kept as
# an alias to avoid breaking existing code. New code should import
# from packages.providers directly.

from providers.openai_compatible import OpenAICompatibleProvider as _OpenAICompat


class LMStudioClient:
    """[DEPRECATED] Legacy alias for OpenAICompatibleProvider.

    Use ``from providers import OpenAICompatibleProvider`` instead.
    Kept for backward compatibility with existing benchmark scripts.
    """

    def __init__(self, base_url: str, api_key: str = "lm-studio",
                 model_name: str = "local-model", timeout: int = 120,
                 max_retries: int = 3):
        logger.warning(
            "LMStudioClient is deprecated. Use OpenAICompatibleProvider from providers."
        )
        self._provider = _OpenAICompat(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.model_name = model_name

    def chat_completion(self, messages: List[Dict], temperature: float = 0.0,
                       max_tokens: int = 4096, top_p: float = 1.0,
                       stream: bool = False) -> tuple[str, APICallMetrics]:
        """Delegate to OpenAICompatibleProvider.chat_completion."""
        return self._provider.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=stream,
        )


class MemoryMonitor:
    """Monitors RAM and VRAM usage during benchmark execution."""
    
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.monitoring = False
        self.ram_usage = []
        self.vram_usage = []
        self.thread = None
        
    def start(self):
        """Start monitoring memory usage."""
        self.monitoring = True
        self.ram_usage = []
        self.vram_usage = []
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self):
        """Stop monitoring and return statistics."""
        self.monitoring = False
        if self.thread:
            self.thread.join()
            
        if not self.ram_usage:
            return {"ram_mb": 0, "ram_peak_mb": 0, "vram_mb": 0, "vram_peak_mb": 0}
        
        return {
            "ram_mb": sum(self.ram_usage) / len(self.ram_usage),
            "ram_peak_mb": max(self.ram_usage),
            "vram_mb": sum(self.vram_usage) / len(self.vram_usage) if self.vram_usage else 0,
            "vram_peak_mb": max(self.vram_usage) if self.vram_usage else 0
        }
        
    def _monitor_loop(self):
        """Internal monitoring loop."""
        while self.monitoring:
            # RAM usage
            process = psutil.Process()
            ram_mb = process.memory_info().rss / 1024 / 1024
            self.ram_usage.append(ram_mb)
            
            # VRAM usage (try to get GPU info if available)
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                vram_mb = info.used / 1024 / 1024
                self.vram_usage.append(vram_mb)
            except (ImportError, ModuleNotFoundError):
                pass  # GPU monitoring not available
            except Exception:
                pass  # pynvml initialization failed
            
            time.sleep(self.interval)


class Benchmark:
    """Base class for all benchmarks."""
    
    def __init__(self, client, config: Dict[str, Any],
                 event_bus: Optional[object] = None,
                 run_id: str = ""):
        self.client = client
        self.config = config
        self.results: List[BenchmarkResult] = []
        self.event_bus = event_bus if event_bus is not None else default_bus
        self._run_id = run_id
        self._events_available = _EVENTS_AVAILABLE and self.event_bus is not None
        
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run the benchmark with specified number of samples."""
        raise NotImplementedError("Subclasses must implement run()")
        
    def get_results(self) -> List[BenchmarkResult]:
        """Return all results from this benchmark."""
        return self.results
    
    def _emit_metric(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Emit a MetricEvent on the event bus (if available)."""
        if not self._events_available:
            return
        self.event_bus.emit_sync(MetricEvent(
            name=name,
            value=value,
            tags=tags or {},
            model=getattr(self.client, 'model_name', ''),
            run_id=self._run_id,
            source=f"benchmark.{self.__class__.__name__}",
        ))


class BenchmarkSuite:
    """Manages running multiple benchmarks and aggregating results."""
    
    def __init__(self, client: ProviderAdapter, config: Dict[str, Any],
                 event_bus: Optional[object] = None,
                 event_source: str = ""):
        self.client = client
        self.config = config
        self.benchmarks: Dict[str, Benchmark] = {}
        self.all_results: List[BenchmarkResult] = []
        self.event_bus = event_bus if event_bus is not None else default_bus
        self._event_source = event_source or "benchmark_suite"
        self._events_available = _EVENTS_AVAILABLE and self.event_bus is not None
        
    def register_benchmark(self, name: str, benchmark: Benchmark):
        """Register a benchmark with the suite."""
        self.benchmarks[name] = benchmark
        
    def run_benchmark(self, name: str, samples: Optional[int] = None) -> List[BenchmarkResult]:
        """Run a specific benchmark."""
        if name not in self.benchmarks:
            raise ValueError(f"Benchmark {name} not registered")
            
        benchmark = self.benchmarks[name]
        sample_count = samples or self.config.get("benchmarks", {}).get("samples_per_benchmark", 100)
        run_id = f"{self._event_source}.{name}.{int(time.time())}"

        logger.info("Running benchmark: %s (samples: %d)", name, sample_count)

        # ── Emit lifecycle: benchmark started ───────────────────
        if self._events_available:
            self.event_bus.emit_sync(RunLifecycleEvent(
                status="started",
                model=getattr(self.client, 'model_name', ''),
                workload=f"general/{name}",
                run_id=run_id,
                source=self._event_source,
            ))

        start_ms = time.time() * 1000
        results = benchmark.run(samples=sample_count)
        duration_ms = time.time() * 1000 - start_ms
        self.all_results.extend(results)

        # ── Emit MetricEvents for each result ───────────────────
        if self._events_available:
            for r in results:
                model = getattr(self.client, 'model_name', '')
                self.event_bus.emit_sync(MetricEvent(
                    name=f"general.{r.benchmark_name}.{r.metric_name}",
                    value=r.score,
                    tags=r.metadata if isinstance(r.metadata, dict) else {},
                    model=model,
                    run_id=run_id,
                    source=self._event_source,
                ))

            # ── Emit lifecycle: benchmark completed ─────────────
            self.event_bus.emit_sync(RunLifecycleEvent(
                status="completed",
                model=getattr(self.client, 'model_name', ''),
                workload=f"general/{name}",
                run_id=run_id,
                source=self._event_source,
                duration_ms=duration_ms,
            ))

        return results
        
    def run_all(self, samples: Optional[int] = None, 
                benchmark_names: Optional[List[str]] = None) -> List[BenchmarkResult]:
        """Run all registered benchmarks or specified subset."""
        targets = benchmark_names or list(self.benchmarks.keys())
        model = getattr(self.client, 'model_name', '')
        run_id = f"{self._event_source}.all.{int(time.time())}"

        # ── Emit lifecycle: suite started ───────────────────────
        if self._events_available:
            self.event_bus.emit_sync(RunLifecycleEvent(
                status="started",
                model=model,
                workload="general/all",
                run_id=run_id,
                source=self._event_source,
            ))

        start_ms = time.time() * 1000
        
        for name in targets:
            try:
                self.run_benchmark(name, samples)
            except Exception as e:
                logger.error("Error running benchmark %s: %s", name, e, exc_info=True)
                if self._events_available:
                    self.event_bus.emit_sync(ErrorEvent(
                        message=f"Benchmark {name} failed: {e}",
                        exception=type(e).__name__,
                        component=name,
                        run_id=run_id,
                        source=self._event_source,
                        severity="error",
                    ))
                continue

        duration_ms = time.time() * 1000 - start_ms

        # ── Emit lifecycle: suite completed ─────────────────────
        if self._events_available:
            status = "completed" if self.all_results else "failed"
            self.event_bus.emit_sync(RunLifecycleEvent(
                status=status,
                model=model,
                workload="general/all",
                run_id=run_id,
                source=self._event_source,
                duration_ms=duration_ms,
                error="No results produced" if not self.all_results else None,
            ))
                
        return self.all_results
        
    def get_summary(self) -> Dict[str, Any]:
        """Generate a summary of all benchmark results."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "model": self.client.model_name,
            "benchmarks": {}
        }
        
        # Group results by benchmark
        by_benchmark: Dict[str, List[BenchmarkResult]] = {}
        for result in self.all_results:
            if result.benchmark_name not in by_benchmark:
                by_benchmark[result.benchmark_name] = []
            by_benchmark[result.benchmark_name].append(result)
        
        # Calculate statistics for each benchmark
        for benchmark_name, results in by_benchmark.items():
            benchmark_summary = {
                "metrics": {}
            }
            
            # Group by metric name
            by_metric: Dict[str, List[float]] = {}
            for result in results:
                if result.metric_name not in by_metric:
                    by_metric[result.metric_name] = []
                by_metric[result.metric_name].append(result.score)
            
            # Calculate stats for each metric
            for metric_name, scores in by_metric.items():
                benchmark_summary["metrics"][metric_name] = {
                    "mean": sum(scores) / len(scores),
                    "min": min(scores),
                    "max": max(scores),
                    "count": len(scores)
                }
            
            summary["benchmarks"][benchmark_name] = benchmark_summary
        
        return summary
