"""
MMLU-Pro benchmark for general reasoning evaluation.
Uses a subset of MMLU-Pro questions.
"""

from typing import Dict, List, Any, Optional
from core import Benchmark, BenchmarkResult
import random
import re


class MMLUProBenchmark(Benchmark):
    """MMLU-Pro benchmark for evaluating general reasoning capabilities."""

    # Sample MMLU-Pro questions (subset for demonstration)
    QUESTIONS = [
        {
            "subject": "math",
            "question": "What is the derivative of f(x) = x^3 + 2x^2 - 5x + 1?",
            "choices": ["3x^2 + 4x - 5", "3x^2 + 4x + 5", "x^2 + 4x - 5", "3x^2 - 4x - 5"],
            "answer": 0,
        },
        {
            "subject": "physics",
            "question": "What is the speed of light in a vacuum?",
            "choices": ["3 × 10^8 m/s", "3 × 10^6 m/s", "3 × 10^10 m/s", "3 × 10^4 m/s"],
            "answer": 0,
        },
        {
            "subject": "chemistry",
            "question": "What is the atomic number of Carbon?",
            "choices": ["6", "12", "14", "8"],
            "answer": 0,
        },
        {
            "subject": "biology",
            "question": "What is the powerhouse of the cell?",
            "choices": ["Nucleus", "Mitochondria", "Ribosome", "Golgi apparatus"],
            "answer": 1,
        },
        {
            "subject": "computer_science",
            "question": "What is the time complexity of binary search?",
            "choices": ["O(n)", "O(log n)", "O(n^2)", "O(1)"],
            "answer": 1,
        },
        {
            "subject": "math",
            "question": "What is the integral of 2x dx?",
            "choices": ["x^2 + C", "2x^2 + C", "x + C", "2 + C"],
            "answer": 0,
        },
        {
            "subject": "physics",
            "question": "What is Newton's second law of motion?",
            "choices": ["F = ma", "E = mc^2", "F = G(m1m2)/r^2", "PV = nRT"],
            "answer": 0,
        },
        {
            "subject": "chemistry",
            "question": "What is the pH of a neutral solution?",
            "choices": ["0", "7", "14", "1"],
            "answer": 1,
        },
        {
            "subject": "biology",
            "question": "What is DNA primarily composed of?",
            "choices": ["Proteins", "Nucleotides", "Carbohydrates", "Lipids"],
            "answer": 1,
        },
        {
            "subject": "computer_science",
            "question": "What data structure uses LIFO?",
            "choices": ["Queue", "Stack", "Array", "Linked List"],
            "answer": 1,
        },
    ]

    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        self.subjects = config.get(
            "subjects", ["math", "physics", "chemistry", "biology", "computer_science"]
        )

    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run MMLU-Pro benchmark."""
        # Filter questions by configured subjects
        filtered_questions = [q for q in self.QUESTIONS if q["subject"] in self.subjects]

        # Sample questions (with replacement if needed)
        if len(filtered_questions) < samples:
            questions = random.choices(filtered_questions, k=samples)
        else:
            questions = random.sample(filtered_questions, samples)

        correct = 0
        results = []

        for i, q in enumerate(questions):
            # Format the question with choices
            choices_text = "\n".join(
                [f"{chr(65 + j)}. {choice}" for j, choice in enumerate(q["choices"])]
            )
            prompt = f"""Question: {q["question"]}

{choices_text}

Respond with ONLY the letter of the correct answer (A, B, C, or D) and nothing else."""

            messages = [
                {
                    "role": "system",
                    "content": "You are a precise multiple-choice answerer. You MUST respond with exactly one character: the letter of the correct answer (A, B, C, or D). Never include explanations, punctuation, or any other text.",
                },
                {"role": "user", "content": prompt},
            ]

            try:
                response, _ = self.client.chat_completion(
                    messages=messages, temperature=0.0, max_tokens=10
                )

                if self.verbose:
                    print(f"\n[VERBOSE mmlu_pro #{i + 1}] Q: {q['question'][:80]}")
                    print(
                        f"[VERBOSE mmlu_pro #{i + 1}] Response ({len(response)} chars): {repr(response)}"
                    )

                # Robustly extract answer letter from response
                predicted_idx = self._extract_answer_letter(response)

                if self.verbose:
                    expected_letter = chr(q["answer"] + ord("A"))
                    if predicted_idx is not None:
                        actual_letter = chr(predicted_idx + ord("A"))
                        status = "CORRECT" if predicted_idx == q["answer"] else "INCORRECT"
                        print(
                            f"[VERBOSE mmlu_pro #{i + 1}] Parser: extracted '{actual_letter}' (idx {predicted_idx})"
                        )
                        print(
                            f"[VERBOSE mmlu_pro #{i + 1}] Expected: '{expected_letter}' (idx {q['answer']}) → {status}"
                        )
                    else:
                        print(
                            f"[VERBOSE mmlu_pro #{i + 1}] Parser: ALL STRATEGIES FAILED — could not extract answer letter"
                        )
                        print(
                            f"[VERBOSE mmlu_pro #{i + 1}] Expected: '{expected_letter}' (idx {q['answer']}) → INCORRECT (0.0)"
                        )

                is_correct = predicted_idx == q["answer"] if predicted_idx is not None else False
                if is_correct:
                    correct += 1

                results.append(
                    BenchmarkResult(
                        benchmark_name="mmlu_pro",
                        metric_name="accuracy",
                        score=1.0 if is_correct else 0.0,
                        metadata={
                            "subject": q["subject"],
                            "question": q["question"],
                            "predicted": chr(predicted_idx + ord("A"))
                            if predicted_idx is not None
                            else None,
                            "correct_idx": q["answer"],
                        },
                    )
                )

                if (i + 1) % 10 == 0:
                    print(
                        f"  Progress: {i + 1}/{samples} | Accuracy so far: {correct / (i + 1):.2%}"
                    )

            except Exception as e:
                print(f"  Error on question {i + 1}: {e}")
                results.append(
                    BenchmarkResult(
                        benchmark_name="mmlu_pro",
                        metric_name="accuracy",
                        score=0.0,
                        metadata={"error": str(e)},
                    )
                )

        # Add overall accuracy result
        overall_accuracy = correct / len(questions) if questions else 0
        results.append(
            BenchmarkResult(
                benchmark_name="mmlu_pro",
                metric_name="overall_accuracy",
                score=overall_accuracy,
                metadata={"total_questions": len(questions), "correct": correct},
            )
        )

        print(f"\n  MMLU-Pro Accuracy: {overall_accuracy:.2%} ({correct}/{len(questions)})")

        return results

    def _extract_answer_letter(self, response: str) -> Optional[int]:
        """Robustly extract the answer letter (A/B/C/D) from a response."""
        text = response.strip().upper()

        # Strategy 1: Look for explicit answer markers like "answer: A" or "answer is A"
        answer_patterns = [
            r"ANSWER\s*(?:IS\s*)?:?\s*([A-D])",
            r"CORRECT\s*(?:ANSWER\s*)?(?:IS\s*)?:?\s*([A-D])",
            r"CHOICE\s*:?\s*([A-D])",
            r"OPTION\s*:?\s*([A-D])",
        ]
        for pattern in answer_patterns:
            match = re.search(pattern, text)
            if match:
                return ord(match.group(1)) - ord("A")

        # Strategy 2: Look for isolated A/B/C/D in parentheses e.g., "(A)" or "A)"
        match = re.search(r"\(?([A-D])\)", text)
        if match:
            return ord(match.group(1)) - ord("A")

        # Strategy 3: Look for letter followed by period and answer text e.g., "A. 3x^2 + 4x - 5"
        match = re.search(r"(?:^|\s)([A-D])\.\s", text)
        if match:
            return ord(match.group(1)) - ord("A")

        # Strategy 4: Look for any isolated A, B, C, or D as a word
        match = re.search(r"\b([A-D])\b", text)
        if match:
            return ord(match.group(1)) - ord("A")

        # Strategy 5: First character fallback
        if text and text[0] in "ABCD":
            return ord(text[0]) - ord("A")

        return None
