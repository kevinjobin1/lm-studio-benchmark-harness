"""
IFEval benchmark for instruction following evaluation.
"""

import re
from typing import Dict, List, Any
from core import Benchmark, BenchmarkResult


class IFEvalBenchmark(Benchmark):
    """IFEval benchmark for evaluating instruction following capabilities."""
    
    # Sample IFEval-style instruction following tasks
    TASKS = [
        {
            "instruction": "Write a sentence about cats. Do not use the letter 'e'.",
            "constraints": ["no_letter_e"],
            "check": lambda x: 'e' not in x.lower()
        },
        {
            "instruction": "Write exactly 5 words about programming.",
            "constraints": ["exact_word_count_5"],
            "check": lambda x: len(x.split()) == 5
        },
        {
            "instruction": "Write a sentence that starts with 'Today' and ends with 'tomorrow.'",
            "constraints": ["starts_with_Today", "ends_with_tomorrow"],
            "check": lambda x: x.strip().startswith('Today') and x.strip().lower().endswith('tomorrow.')
        },
        {
            "instruction": "Write a paragraph with exactly 3 sentences. Each sentence should be about dogs.",
            "constraints": ["exactly_3_sentences", "about_dogs"],
            "check": lambda x: len([s for s in x.split('.') if s.strip()]) == 3 and bool(re.search(r'\bdogs?\b', x.lower()))
        },
        {
            "instruction": "Write a response that includes the word 'artificial' at least twice.",
            "constraints": ["word_artificial_twice"],
            "check": lambda x: x.lower().count('artificial') >= 2
        },
        {
            "instruction": "Write a sentence where every word starts with the same letter.",
            "constraints": ["alliteration"],
            "check": lambda x: len(set(w[0].lower() for w in x.split() if w)) == 1 if x.split() else False
        },
        {
            "instruction": "Write a response that is exactly 50 characters long (including spaces).",
            "constraints": ["exactly_50_chars"],
            "check": lambda x: len(x) == 50
        },
        {
            "instruction": "Write a sentence that contains a number between 10 and 20.",
            "constraints": ["number_10_to_20"],
            "check": lambda x: any(10 <= int(n) <= 20 for n in re.findall(r'\d+', x))
        },
        {
            "instruction": "Write a response that does not contain any punctuation marks.",
            "constraints": ["no_punctuation"],
            "check": lambda x: not any(c in x for c in '.,!?;:()[]{}"\'')
        },
        {
            "instruction": "Write a sentence where the words are in alphabetical order.",
            "constraints": ["alphabetical_order"],
            "check": lambda x: x.split() == sorted(x.split(), key=lambda w: w.lower())
        }
    ]
    
    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run IFEval benchmark."""
        import random
        
        tasks = random.choices(self.TASKS, k=min(samples, len(self.TASKS)))
        passed = 0
        results = []
        
        for i, task in enumerate(tasks):
            messages = [
                {"role": "system", "content": "You are a precise instruction-following assistant. Follow the user's instruction EXACTLY. Respond with ONLY what is requested — no explanations, no markdown, no extra text whatsoever."},
                {"role": "user", "content": task["instruction"]}
            ]
            
            try:
                response, _ = self.client.chat_completion(
                    messages=messages,
                    temperature=0.0,
                    max_tokens=200
                )
                
                if self.verbose:
                    print(f"\n[VERBOSE if_eval #{i+1}] Instruction: {task['instruction'][:80]}")
                    print(f"[VERBOSE if_eval #{i+1}] Response ({len(response)} chars): {repr(response)} [{', '.join(task['constraints'])}]")
                
                # Check if constraints are satisfied
                is_passed = task["check"](response)
                
                if self.verbose:
                    print(f"[VERBOSE if_eval #{i+1}] Constraints: {'PASSED' if is_passed else 'FAILED'}")
                
                if is_passed:
                    passed += 1
                
                results.append(BenchmarkResult(
                    benchmark_name="if_eval",
                    metric_name="instruction_following",
                    score=1.0 if is_passed else 0.0,
                    metadata={
                        "instruction": task["instruction"],
                        "constraints": task["constraints"],
                        "response_length": len(response)
                    }
                ))
                
                if (i + 1) % 5 == 0:
                    print(f"  Progress: {i+1}/{len(tasks)} | Pass rate: {passed/(i+1):.2%}")
                    
            except Exception as e:
                print(f"  Error on task {i+1}: {e}")
                results.append(BenchmarkResult(
                    benchmark_name="if_eval",
                    metric_name="instruction_following",
                    score=0.0,
                    metadata={"error": str(e)}
                ))
        
        pass_rate = passed / len(tasks) if tasks else 0
        results.append(BenchmarkResult(
            benchmark_name="if_eval",
            metric_name="overall_pass_rate",
            score=pass_rate,
            metadata={"total_tasks": len(tasks), "passed": passed}
        ))
        
        print(f"\n  IFEval Pass Rate: {pass_rate:.2%} ({passed}/{len(tasks)})")
        
        return results
