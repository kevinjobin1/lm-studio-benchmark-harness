"""
Speed and latency benchmark for tokens/sec and TTFT measurement.
"""

from typing import Dict, List, Any
from core import Benchmark, BenchmarkResult, MemoryMonitor


class SpeedLatencyBenchmark(Benchmark):
    """Benchmark for measuring speed (tokens/sec) and latency (TTFT)."""
    
    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        self.prompt_lengths = config.get("prompt_lengths", [100, 500, 1000, 2000])
        
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run speed and latency benchmark across different prompt lengths."""
        results = []
        
        for prompt_length in self.prompt_lengths:
            print(f"\n  Testing prompt length: {prompt_length} chars")
            
            # Generate prompt of specified length
            prompt = self._generate_prompt(prompt_length)
            
            ttft_values = []
            tps_values = []
            
            for i in range(min(samples, 10)):  # Limit iterations per length
                messages = [{"role": "user", "content": prompt}]
                
                try:
                    response, metrics = self.client.chat_completion(
                        messages=messages,
                        temperature=0.7,
                        max_tokens=500,
                        stream=True  # Use streaming for accurate TTFT
                    )
                    
                    ttft_values.append(metrics.ttft)
                    tps_values.append(metrics.tokens_per_second)
                    
                except Exception as e:
                    print(f"    Error on iteration {i+1}: {e}")
                    continue
            
            if ttft_values:
                avg_ttft = sum(ttft_values) / len(ttft_values)
                avg_tps = sum(tps_values) / len(tps_values)
                
                results.append(BenchmarkResult(
                    benchmark_name="speed_latency",
                    metric_name="ttft",
                    score=avg_ttft,
                    metadata={
                        "prompt_length": prompt_length,
                        "unit": "seconds"
                    }
                ))
                
                results.append(BenchmarkResult(
                    benchmark_name="speed_latency",
                    metric_name="tokens_per_second",
                    score=avg_tps,
                    metadata={
                        "prompt_length": prompt_length,
                        "unit": "tokens/second"
                    }
                ))
                
                print(f"    Avg TTFT: {avg_ttft:.3f}s")
                print(f"    Avg Tokens/sec: {avg_tps:.1f}")
        
        # Calculate overall averages
        ttft_results = [r for r in results if r.metric_name == "ttft"]
        tps_results = [r for r in results if r.metric_name == "tokens_per_second"]
        
        if ttft_results:
            overall_ttft = sum(r.score for r in ttft_results) / len(ttft_results)
            results.append(BenchmarkResult(
                benchmark_name="speed_latency",
                metric_name="overall_ttft",
                score=overall_ttft,
                metadata={"unit": "seconds"}
            ))
        
        if tps_results:
            overall_tps = sum(r.score for r in tps_results) / len(tps_results)
            results.append(BenchmarkResult(
                benchmark_name="speed_latency",
                metric_name="overall_tokens_per_second",
                score=overall_tps,
                metadata={"unit": "tokens/second"}
            ))
        
        print(f"\n  Overall TTFT: {overall_ttft:.3f}s")
        print(f"  Overall Tokens/sec: {overall_tps:.1f}")
        
        return results
    
    def _generate_prompt(self, length: int) -> str:
        """Generate a prompt of specified length."""
        filler_words = [
            "The", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog",
            "In", "a", "world", "of", "endless", "possibilities", "we", "find",
            "ourselves", "at", "the", "crossroads", "of", "destiny", "and", "choice",
            "Technology", "advances", "at", "an", "unprecedented", "pace", "transforming",
            "every", "aspect", "of", "our", "daily", "lives", "from", "communication",
            "to", "commerce", "healthcare", "to", "entertainment", "The", "future",
            "holds", "both", "challenges", "and", "opportunities", "for", "those",
            "willing", "to", "adapt", "innovate", "and", "persevere", "through",
            "adversity", "and", "uncertainty", "We", "must", "embrace", "change",
            "while", "preserving", "the", "values", "that", "define", "our", "humanity"
        ]
        
        prompt = " ".join(filler_words)
        
        # Repeat to reach target length
        while len(prompt) < length:
            prompt += " " + " ".join(filler_words)
        
        return prompt[:length]
