"""
Math benchmarks: GSM8K and AIME subsets.
"""

import re
from typing import Dict, List, Any
from benchmark.core import Benchmark, BenchmarkResult


class GSM8KBenchmark(Benchmark):
    """GSM8K benchmark for grade school math problems."""
    
    # Sample GSM8K-style questions
    QUESTIONS = [
        {
            "question": "A baker has 60 loaves of bread. If he sells 25 loaves in the morning and 18 loaves in the afternoon, how many loaves does he have left?",
            "answer": 17
        },
        {
            "question": "A train travels 240 miles in 4 hours. What is the train's speed in miles per hour?",
            "answer": 60
        },
        {
            "question": "If a shirt costs $25 and is on sale for 20% off, what is the sale price?",
            "answer": 20
        },
        {
            "question": "A rectangle has a length of 12 cm and a width of 8 cm. What is its area?",
            "answer": 96
        },
        {
            "question": "John has 15 apples. He gives 5 to Mary and 3 to Tom. How many apples does John have left?",
            "answer": 7
        },
        {
            "question": "A car uses 8 gallons of gas to travel 200 miles. How many gallons are needed to travel 350 miles?",
            "answer": 14
        },
        {
            "question": "If 3 pencils cost $1.50, how much do 10 pencils cost?",
            "answer": 5
        },
        {
            "question": "A number is multiplied by 4, then 6 is added. The result is 34. What is the number?",
            "answer": 7
        },
        {
            "question": "A triangle has a base of 10 inches and a height of 6 inches. What is its area?",
            "answer": 30
        },
        {
            "question": "If you save $50 per month for 12 months, how much do you save in total?",
            "answer": 600
        }
    ]
    
    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run GSM8K benchmark."""
        import random
        
        questions = random.choices(self.QUESTIONS, k=min(samples, len(self.QUESTIONS)))
        correct = 0
        results = []
        
        for i, q in enumerate(questions):
            prompt = f"""Solve this math problem step by step. Give your final answer as a single number at the end.

Question: {q['question']}"""
            
            messages = [{"role": "user", "content": prompt}]
            
            try:
                response, _ = self.client.chat_completion(
                    messages=messages,
                    temperature=0.0,
                    max_tokens=500
                )
                
                # Extract numeric answer
                numbers = re.findall(r'-?\d+\.?\d*', response)
                if numbers:
                    predicted = float(numbers[-1])
                    is_correct = abs(predicted - q["answer"]) < 0.01
                    if is_correct:
                        correct += 1
                else:
                    is_correct = False
                
                results.append(BenchmarkResult(
                    benchmark_name="gsm8k",
                    metric_name="accuracy",
                    score=1.0 if is_correct else 0.0,
                    metadata={
                        "question": q["question"],
                        "predicted": numbers[-1] if numbers else None,
                        "correct_answer": q["answer"]
                    }
                ))
                
                if (i + 1) % 5 == 0:
                    print(f"  Progress: {i+1}/{len(questions)} | Accuracy: {correct/(i+1):.2%}")
                    
            except Exception as e:
                print(f"  Error on question {i+1}: {e}")
                results.append(BenchmarkResult(
                    benchmark_name="gsm8k",
                    metric_name="accuracy",
                    score=0.0,
                    metadata={"error": str(e)}
                ))
        
        overall_accuracy = correct / len(questions) if questions else 0
        results.append(BenchmarkResult(
            benchmark_name="gsm8k",
            metric_name="overall_accuracy",
            score=overall_accuracy,
            metadata={"total_questions": len(questions), "correct": correct}
        ))
        
        print(f"\n  GSM8K Accuracy: {overall_accuracy:.2%} ({correct}/{len(questions)})")
        
        return results


class AIMEBenchmark(Benchmark):
    """AIME benchmark for advanced math problems."""
    
    # Sample AIME-style questions
    QUESTIONS = [
        {
            "question": "Find the sum of all positive integers n such that n^2 + 19n + 92 is a perfect square.",
            "answer": 19
        },
        {
            "question": "How many positive integers less than 1000 are divisible by neither 3 nor 5?",
            "answer": 533
        },
        {
            "question": "Find the number of ways to arrange the letters of the word 'BANANA'.",
            "answer": 60
        },
        {
            "question": "If x + 1/x = 3, find x^3 + 1/x^3.",
            "answer": 18
        },
        {
            "question": "Find the area of a triangle with sides 13, 14, and 15.",
            "answer": 84
        }
    ]
    
    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run AIME benchmark."""
        import random
        
        questions = random.choices(self.QUESTIONS, k=min(samples, len(self.QUESTIONS)))
        correct = 0
        results = []
        
        for i, q in enumerate(questions):
            prompt = f"""Solve this advanced math problem. Show your work and give the final answer as a single integer.

Question: {q['question']}"""
            
            messages = [{"role": "user", "content": prompt}]
            
            try:
                response, _ = self.client.chat_completion(
                    messages=messages,
                    temperature=0.0,
                    max_tokens=800
                )
                
                # Extract numeric answer
                numbers = re.findall(r'-?\d+', response)
                if numbers:
                    predicted = int(numbers[-1])
                    is_correct = predicted == q["answer"]
                    if is_correct:
                        correct += 1
                else:
                    is_correct = False
                
                results.append(BenchmarkResult(
                    benchmark_name="aime",
                    metric_name="accuracy",
                    score=1.0 if is_correct else 0.0,
                    metadata={
                        "question": q["question"],
                        "predicted": numbers[-1] if numbers else None,
                        "correct_answer": q["answer"]
                    }
                ))
                
                print(f"  Progress: {i+1}/{len(questions)} | Accuracy: {correct/(i+1):.2%}")
                    
            except Exception as e:
                print(f"  Error on question {i+1}: {e}")
                results.append(BenchmarkResult(
                    benchmark_name="aime",
                    metric_name="accuracy",
                    score=0.0,
                    metadata={"error": str(e)}
                ))
        
        overall_accuracy = correct / len(questions) if questions else 0
        results.append(BenchmarkResult(
            benchmark_name="aime",
            metric_name="overall_accuracy",
            score=overall_accuracy,
            metadata={"total_questions": len(questions), "correct": correct}
        ))
        
        print(f"\n  AIME Accuracy: {overall_accuracy:.2%} ({correct}/{len(questions)})")
        
        return results
