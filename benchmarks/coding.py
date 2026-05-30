"""
HumanEval benchmark for coding capability evaluation.
"""

import ast
from typing import Dict, List, Any
from benchmark.core import Benchmark, BenchmarkResult


class HumanEvalBenchmark(Benchmark):
    """HumanEval benchmark for evaluating coding capabilities."""
    
    # Sample HumanEval-style problems
    PROBLEMS = [
        {
            "task_id": "HumanEval/0",
            "prompt": "def has_close_elements(numbers: List[float], threshold: float) -> bool:\n    \"\"\"Check if in given list of numbers, are any two numbers closer to each other than\n    given threshold.\n    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)\n    False\n    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)\n    True\n    \"\"\"\n",
            "canonical_solution": "    for idx, elem in enumerate(numbers):\n        for idx2, elem2 in enumerate(numbers):\n            if idx != idx2:\n                distance = abs(elem - elem2)\n                if distance < threshold:\n                    return True\n    return False\n",
            "test": "def check():\n    assert has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True\n    assert has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05) == False\n    assert has_close_elements([1.0, 2.0, 5.9, 4.0, 5.0], 0.3) == True\n    assert has_close_elements([], 0.3) == False\n"
        },
        {
            "task_id": "HumanEval/1",
            "prompt": "def separate_paren_groups(paren_string: str) -> List[str]:\n    \"\"\"Input to this function is a string containing multiple groups of nested parentheses. \n    Your goal is to separate those groupings into separate strings and return the list of those.\n    Separate groups are balanced (each open brace is properly closed) and not nested within each other.\n    Ignore any spaces in the input string.\n    >>> separate_paren_groups('( ) (( )) (( )( ))')\n    ['()', '(())', '(()())']\n    \"\"\"\n",
            "canonical_solution": "    result = []\n    current_string = []\n    current_depth = 0\n\n    for c in paren_string:\n        if c == '(':\n            current_string.append(c)\n            current_depth += 1\n        elif c == ')':\n            current_string.append(c)\n            current_depth -= 1\n\n            if current_depth == 0:\n                result.append(''.join(current_string))\n                current_string = []\n\n    return result\n",
            "test": "def check():\n    assert separate_paren_groups('( ) (( )) (( )( ))') == ['()', '(())', '(()())']\n    assert separate_paren_groups('()()()') == ['()', '()', '()']\n    assert separate_paren_groups('((()))') == ['((()))']\n"
        },
        {
            "task_id": "HumanEval/2",
            "prompt": "def truncate_number(number: float) -> float:\n    \"\"\"Given a positive floating point number, return its decimal part as a float.\n    >>> truncate_number(1.25)\n    0.25\n    >>> truncate_number(5.0)\n    0.0\n    \"\"\"\n",
            "canonical_solution": "    return number % 1.0\n",
            "test": "def check():\n    assert abs(truncate_number(1.25) - 0.25) < 0.001\n    assert abs(truncate_number(5.0) - 0.0) < 0.001\n    assert abs(truncate_number(3.14159) - 0.14159) < 0.001\n"
        },
        {
            "task_id": "HumanEval/3",
            "prompt": "def below_zero(operations: List[int]) -> bool:\n    \"\"\"You're given a list of deposit and withdrawal operations on a bank account. \n    Return true if and only if the account balance ever falls below zero at any point.\n    >>> below_zero([1, 2, 3])\n    False\n    >>> below_zero([1, -1, 2, -2, 3])\n    True\n    \"\"\"\n",
            "canonical_solution": "    balance = 0\n    for op in operations:\n        balance += op\n        if balance < 0:\n            return True\n    return False\n",
            "test": "def check():\n    assert below_zero([1, 2, 3]) == False\n    assert below_zero([1, -1, 2, -2, 3]) == True\n    assert below_zero([-1, -2, -3]) == True\n    assert below_zero([10, -5, 5, -10, 10]) == True\n"
        },
        {
            "task_id": "HumanEval/4",
            "prompt": "def mean_absolute_deviation(numbers: List[float]) -> float:\n    \"\"\"For a given list of numbers, return the mean absolute deviation.\n    The mean absolute deviation is the mean of the absolute differences between each value and the mean.\n    >>> mean_absolute_deviation([1.0, 2.0, 3.0, 4.0])\n    1.0\n    \"\"\"\n",
            "canonical_solution": "    mean_val = sum(numbers) / len(numbers)\n    return sum(abs(x - mean_val) for x in numbers) / len(numbers)\n",
            "test": "def check():\n    assert abs(mean_absolute_deviation([1.0, 2.0, 3.0, 4.0]) - 1.0) < 0.001\n    assert abs(mean_absolute_deviation([5.0, 5.0, 5.0]) - 0.0) < 0.001\n    assert abs(mean_absolute_deviation([1.0, 1.0, 10.0]) - 3.0) < 0.01\n"
        }
    ]
    
    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        
    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run HumanEval benchmark."""
        import random
        
        problems = random.choices(self.PROBLEMS, k=min(samples, len(self.PROBLEMS)))
        passed = 0
        results = []
        
        for i, problem in enumerate(problems):
            prompt = f"""Complete the following Python function. Return only the completed function code, no explanations.

{problem['prompt']}"""
            
            messages = [{"role": "user", "content": prompt}]
            
            try:
                response, _ = self.client.chat_completion(
                    messages=messages,
                    temperature=0.0,
                    max_tokens=300
                )
                
                # Extract function code
                code = response.strip()
                
                # Try to execute and test
                is_correct = self._test_solution(code, problem["test"])
                
                if is_correct:
                    passed += 1
                
                results.append(BenchmarkResult(
                    benchmark_name="humaneval",
                    metric_name="pass@1",
                    score=1.0 if is_correct else 0.0,
                    metadata={
                        "task_id": problem["task_id"],
                        "code_length": len(code)
                    }
                ))
                
                print(f"  Progress: {i+1}/{len(problems)} | Pass rate: {passed/(i+1):.2%}")
                    
            except Exception as e:
                print(f"  Error on problem {i+1}: {e}")
                results.append(BenchmarkResult(
                    benchmark_name="humaneval",
                    metric_name="pass@1",
                    score=0.0,
                    metadata={"error": str(e)}
                ))
        
        pass_rate = passed / len(problems) if problems else 0
        results.append(BenchmarkResult(
            benchmark_name="humaneval",
            metric_name="overall_pass_rate",
            score=pass_rate,
            metadata={"total_problems": len(problems), "passed": passed}
        ))
        
        print(f"\n  HumanEval Pass@1: {pass_rate:.2%} ({passed}/{len(problems)})")
        
        return results
    
    def _test_solution(self, code: str, test_code: str) -> bool:
        """Test if the solution passes the test cases."""
        try:
            # Combine solution and test
            full_code = code + "\n" + test_code + "\ncheck()"
            
            # Execute in a restricted environment
            namespace = {}
            exec(full_code, namespace)
            
            return True
        except:
            return False
