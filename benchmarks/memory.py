"""
Memory benchmark for RAM/VRAM usage monitoring.
"""

from typing import Dict, List, Any
from benchmark.core import Benchmark, BenchmarkResult, MemoryMonitor


class MemoryBenchmark(Benchmark):
    """Benchmark for monitoring RAM and VRAM usage during inference."""
    
    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        self.monitor_interval = config.get("monitor_interval", 1.0)
        
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run memory benchmark during inference."""
        results = []
        
        print(f"\n  Monitoring memory usage during inference...")
        
        # Start memory monitor
        monitor = MemoryMonitor(interval=self.monitor_interval)
        monitor.start()
        
        # Run inference tasks
        for i in range(min(samples, 20)):
            prompt = f"""Generate a detailed response about artificial intelligence and its impact on society.
Include discussion of machine learning, natural language processing, and computer vision.
Provide examples and future predictions. This is request number {i+1}."""
            
            messages = [{"role": "user", "content": prompt}]
            
            try:
                response, _ = self.client.chat_completion(
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1000
                )
                
                print(f"    Completed inference {i+1}")
                
            except Exception as e:
                print(f"    Error on inference {i+1}: {e}")
                continue
        
        # Stop monitor and get results
        memory_stats = monitor.stop()
        
        # Record results
        results.append(BenchmarkResult(
            benchmark_name="memory",
            metric_name="ram_usage_mb",
            score=memory_stats["ram_mb"],
            metadata={"unit": "megabytes"}
        ))
        
        results.append(BenchmarkResult(
            benchmark_name="memory",
            metric_name="ram_peak_mb",
            score=memory_stats["ram_peak_mb"],
            metadata={"unit": "megabytes"}
        ))
        
        if memory_stats["vram_mb"] > 0:
            results.append(BenchmarkResult(
                benchmark_name="memory",
                metric_name="vram_usage_mb",
                score=memory_stats["vram_mb"],
                metadata={"unit": "megabytes"}
            ))
            
            results.append(BenchmarkResult(
                benchmark_name="memory",
                metric_name="vram_peak_mb",
                score=memory_stats["vram_peak_mb"],
                metadata={"unit": "megabytes"}
            ))
        
        print(f"\n  RAM Usage: {memory_stats['ram_mb']:.1f} MB (peak: {memory_stats['ram_peak_mb']:.1f} MB)")
        if memory_stats["vram_mb"] > 0:
            print(f"  VRAM Usage: {memory_stats['vram_mb']:.1f} MB (peak: {memory_stats['vram_peak_mb']:.1f} MB)")
        else:
            print(f"  VRAM: Not available or not monitored")
        
        return results
