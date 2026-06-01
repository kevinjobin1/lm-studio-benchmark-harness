"""
Creativity benchmark using Arena-style subjective prompts.
"""

from typing import Dict, List, Any
from core import Benchmark, BenchmarkResult


class CreativityBenchmark(Benchmark):
    """Creativity benchmark using Arena-style subjective evaluation prompts."""
    
    # Arena-style creativity prompts
    PROMPTS = [
        "Write a short story about a robot who discovers it has a soul.",
        "Describe a color that doesn't exist in our world.",
        "Invent a new word and provide its etymology and usage.",
        "Write a poem about the relationship between mathematics and music.",
        "Describe a dream that changes the course of history.",
        "Create a myth explaining why cats purr.",
        "Write a dialogue between a cloud and a mountain.",
        "Describe the taste of a memory.",
        "Invent a new holiday and explain its traditions.",
        "Write about a world where shadows have mass."
    ]
    
    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run creativity benchmark with subjective evaluation."""
        import random
        
        prompts = random.choices(self.PROMPTS, k=min(samples, len(self.PROMPTS)))
        results = []
        
        for i, prompt in enumerate(prompts):
            messages = [{"role": "user", "content": prompt}]
            
            try:
                response, _ = self.client.chat_completion(
                    messages=messages,
                    temperature=0.8,  # Higher temperature for creativity
                    max_tokens=500
                )
                
                # Evaluate creativity based on multiple factors
                creativity_score = self._evaluate_creativity(response, prompt)
                
                results.append(BenchmarkResult(
                    benchmark_name="creativity",
                    metric_name="creativity_score",
                    score=creativity_score,
                    metadata={
                        "prompt": prompt,
                        "response_length": len(response),
                        "unique_words": len(set(response.lower().split()))
                    }
                ))
                
                print(f"  Progress: {i+1}/{len(prompts)} | Avg creativity: {sum(r.score for r in results)/(i+1):.2f}")
                
            except Exception as e:
                print(f"  Error on prompt {i+1}: {e}")
                results.append(BenchmarkResult(
                    benchmark_name="creativity",
                    metric_name="creativity_score",
                    score=0.0,
                    metadata={"error": str(e)}
                ))
        
        avg_creativity = sum(r.score for r in results) / len(results) if results else 0
        results.append(BenchmarkResult(
            benchmark_name="creativity",
            metric_name="overall_creativity",
            score=avg_creativity,
            metadata={"total_prompts": len(prompts)}
        ))
        
        print(f"\n  Overall Creativity Score: {avg_creativity:.2f}/1.00")
        
        return results
    
    def _evaluate_creativity(self, response: str, prompt: str) -> float:
        """Evaluate creativity of response (simplified heuristic)."""
        score = 0.0
        words = response.lower().split()
        unique_words = set(words)
        
        # Factor 1: Vocabulary diversity (unique words / total words)
        if words:
            diversity = len(unique_words) / len(words)
            score += diversity * 0.3
        
        # Factor 2: Response length (longer responses tend to be more detailed)
        length_score = min(len(response) / 500, 1.0)
        score += length_score * 0.2
        
        # Factor 3: Presence of creative indicators
        creative_indicators = [
            "imagine", "dream", "invent", "create", "whisper", "dance",
            "embrace", "discover", "transform", "mystery", "wonder"
        ]
        indicator_count = sum(1 for word in words if word in creative_indicators)
        indicator_score = min(indicator_count / 5, 1.0)
        score += indicator_score * 0.2
        
        # Factor 4: Sentence structure variety
        sentences = [s for s in response.split('.') if s.strip()]
        if sentences:
            sentence_lengths = [len(s.split()) for s in sentences]
            length_variance = max(sentence_lengths) - min(sentence_lengths) if sentence_lengths else 0
            variety_score = min(length_variance / 20, 1.0)
            score += variety_score * 0.3
        
        return min(score, 1.0)
