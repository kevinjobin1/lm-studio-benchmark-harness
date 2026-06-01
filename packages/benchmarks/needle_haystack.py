"""
Needle-in-Haystack benchmark for long context evaluation.
"""

from typing import Dict, List, Any
from core import Benchmark, BenchmarkResult
import random


class NeedleInHaystackBenchmark(Benchmark):
    """Needle-in-Haystack benchmark for evaluating long context capabilities."""
    
    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        self.context_lengths = config.get("context_lengths", [4000, 8000, 16000, 32000])
        
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run Needle-in-Haystack benchmark across different context lengths."""
        results = []
        
        for context_length in self.context_lengths:
            print(f"\n  Testing context length: {context_length} tokens")
            
            # Generate context with a hidden "needle"
            context, needle, needle_position = self._generate_context(context_length)
            
            prompt = f"""Read the following text and answer the question at the end.

{context}

Question: What is the special code mentioned in the text? Respond with ONLY the code, no other text."""
            
            messages = [
                {"role": "system", "content": "You are a text retrieval system. Respond with ONLY the exact code or answer requested — no explanations, no punctuation, no surrounding text."},
                {"role": "user", "content": prompt}
            ]
            
            try:
                response, _ = self.client.chat_completion(
                    messages=messages,
                    temperature=0.0,
                    max_tokens=100
                )
                
                if self.verbose:
                    print(f"\n[VERBOSE needle #{context_length}] Needle: {needle}")
                    print(f"[VERBOSE needle #{context_length}] Response ({len(response)} chars): {repr(response)}")
                
                # Check if the needle was found
                is_found = needle.lower() in response.lower()
                
                results.append(BenchmarkResult(
                    benchmark_name="needle_in_haystack",
                    metric_name="retrieval_accuracy",
                    score=1.0 if is_found else 0.0,
                    metadata={
                        "context_length": context_length,
                        "needle_position": needle_position,
                        "needle": needle,
                        "response": response[:100]
                    }
                ))
                
                print(f"    Needle found: {is_found}")
                
            except Exception as e:
                print(f"    Error: {e}")
                results.append(BenchmarkResult(
                    benchmark_name="needle_in_haystack",
                    metric_name="retrieval_accuracy",
                    score=0.0,
                    metadata={"context_length": context_length, "error": str(e)}
                ))
        
        # Calculate overall accuracy
        accuracy = sum(r.score for r in results) / len(results) if results else 0
        results.append(BenchmarkResult(
            benchmark_name="needle_in_haystack",
            metric_name="overall_accuracy",
            score=accuracy,
            metadata={"total_tests": len(results)}
        ))
        
        print(f"\n  Overall Needle-in-Haystack Accuracy: {accuracy:.2%}")
        
        return results
    
    def _generate_context(self, target_tokens: int) -> tuple[str, str, float]:
        """Generate context with a hidden needle."""
        # The needle (special code to find)
        needle = f"SPECIAL-CODE-{random.randint(1000, 9999)}"
        
        # Generate filler text (Lorem ipsum style)
        filler_words = [
            "the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog",
            "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing",
            "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore",
            "et", "dolore", "magna", "aliqua", "enim", "ad", "minim", "veniam",
            "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi", "aliquip",
            "ex", "ea", "commodo", "consequat", "duis", "aute", "irure", "dolor",
            "reprehenderit", "voluptate", "velit", "esse", "cillum", "fugiat", "nulla",
            "pariatur", "excepteur", "sint", "occaecat", "cupidatat", "non", "proident"
        ]
        
        # Estimate tokens (roughly 4 chars per token)
        target_chars = target_tokens * 4
        
        # Generate filler text
        filler = " ".join(random.choices(filler_words, k=target_chars // 5))
        
        # Insert needle at random position (20-80% through the text)
        position = random.uniform(0.2, 0.8)
        insert_idx = int(len(filler) * position)
        
        context = filler[:insert_idx] + f" {needle} " + filler[insert_idx:]
        
        return context, needle, position
