"""
Core benchmark framework for LM Studio API evaluation.
"""

import time
import psutil
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from openai import OpenAI
import yaml

from providers.base import APICallMetrics@dataclass
class BenchmarkResult:
    """Stores results from a single benchmark run."""
    benchmark_name: str
    metric_name: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class LMStudioClient:
    """Wrapper for LM Studio OpenAI-compatible API."""

    def __init__(self, base_url: str, api_key: str = "lm-studio",
                 model_name: str = "local-model", timeout: int = 120,
                 max_retries: int = 3):
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries
        )
        self.model_name = model_name

    def chat_completion(self, messages: List[Dict], temperature: float = 0.0,
                       max_tokens: int = 4096, top_p: float = 1.0,
                       stream: bool = False) -> tuple[str, APICallMetrics]:
        """
        Make a chat completion request and track metrics.
        Returns (response_text, metrics).
        """
        start_time = time.time()
        first_token_time = None
        accumulated_tokens = 0
        
        if stream:
            # Streaming mode for accurate TTFT measurement
            response_text = ""
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    if first_token_time is None:
                        first_token_time = time.time()
                    response_text += chunk.choices[0].delta.content
                    accumulated_tokens += 1
            
            total_time = time.time() - start_time
            ttft = first_token_time - start_time if first_token_time else total_time
            
            # Estimate token counts
            prompt_tokens = sum(len(str(m["content"])) for m in messages) // 4  # Rough estimate
            completion_tokens = accumulated_tokens
            
        else:
            # Non-streaming mode
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=False
            )
            
            response_text = response.choices[0].message.content
            total_time = time.time() - start_time
            ttft = total_time  # Can't measure TTFT without streaming
            
            prompt_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else 0
            completion_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
        
        total_tokens = prompt_tokens + completion_tokens
        tokens_per_second = completion_tokens / total_time if total_time > 0 else 0
        
        metrics = APICallMetrics(
            ttft=ttft,
            total_time=total_time,
            tokens_per_second=tokens_per_second,
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )
        
        return response_text, metrics


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
            except:
                pass  # GPU monitoring not available
            
            time.sleep(self.interval)


class Benchmark:
    """Base class for all benchmarks."""
    
    def __init__(self, client: LMStudioClient, config: Dict[str, Any]):
        self.client = client
        self.config = config
        self.results: List[BenchmarkResult] = []
        
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run the benchmark with specified number of samples."""
        raise NotImplementedError("Subclasses must implement run()")
        
    def get_results(self) -> List[BenchmarkResult]:
        """Return all results from this benchmark."""
        return self.results


class BenchmarkSuite:
    """Manages running multiple benchmarks and aggregating results."""
    
    def __init__(self, client: LMStudioClient, config: Dict[str, Any]):
        self.client = client
        self.config = config
        self.benchmarks: Dict[str, Benchmark] = {}
        self.all_results: List[BenchmarkResult] = []
        
    def register_benchmark(self, name: str, benchmark: Benchmark):
        """Register a benchmark with the suite."""
        self.benchmarks[name] = benchmark
        
    def run_benchmark(self, name: str, samples: Optional[int] = None) -> List[BenchmarkResult]:
        """Run a specific benchmark."""
        if name not in self.benchmarks:
            raise ValueError(f"Benchmark {name} not registered")
            
        benchmark = self.benchmarks[name]
        sample_count = samples or self.config.get("benchmarks", {}).get("samples_per_benchmark", 100)
        
        print(f"\n{'='*60}")
        print(f"Running benchmark: {name}")
        print(f"Samples: {sample_count}")
        print(f"{'='*60}\n")
        
        results = benchmark.run(samples=sample_count)
        self.all_results.extend(results)
        
        return results
        
    def run_all(self, samples: Optional[int] = None, 
                benchmark_names: Optional[List[str]] = None) -> List[BenchmarkResult]:
        """Run all registered benchmarks or specified subset."""
        targets = benchmark_names or list(self.benchmarks.keys())
        
        for name in targets:
            try:
                self.run_benchmark(name, samples)
            except Exception as e:
                print(f"Error running benchmark {name}: {e}")
                continue
                
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
