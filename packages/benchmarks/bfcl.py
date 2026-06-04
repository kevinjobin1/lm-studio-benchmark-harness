"""
BFCL (Berkeley Function Call Leaderboard) benchmark for tool use evaluation.
Simplified version for demonstration.
"""

import json
import re
from typing import Dict, List, Any, Optional
from core import Benchmark, BenchmarkResult


class BFCLBenchmark(Benchmark):
    """BFCL benchmark for evaluating tool use capabilities."""

    # Sample tool use scenarios
    SCENARIOS = [
        {
            "category": "simple",
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get the current weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name"},
                            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                        },
                        "required": ["location"],
                    },
                }
            ],
            "query": "What's the weather in Tokyo in celsius?",
            "expected_calls": [
                {"name": "get_weather", "arguments": {"location": "Tokyo", "unit": "celsius"}}
            ],
        },
        {
            "category": "simple",
            "tools": [
                {
                    "name": "calculate",
                    "description": "Perform a mathematical calculation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "Math expression to evaluate",
                            }
                        },
                        "required": ["expression"],
                    },
                }
            ],
            "query": "Calculate 25 * 4",
            "expected_calls": [{"name": "calculate", "arguments": {"expression": "25 * 4"}}],
        },
        {
            "category": "multi_turn",
            "tools": [
                {
                    "name": "search",
                    "description": "Search for information",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "Search query"}},
                        "required": ["query"],
                    },
                },
                {
                    "name": "get_details",
                    "description": "Get detailed information about an item",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "Item identifier"}
                        },
                        "required": ["item_id"],
                    },
                },
            ],
            "query": "Search for information about Python programming language",
            "expected_calls": [
                {"name": "search", "arguments": {"query": "Python programming language"}}
            ],
        },
        {
            "category": "parallel",
            "tools": [
                {
                    "name": "get_stock_price",
                    "description": "Get current stock price",
                    "parameters": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string", "description": "Stock symbol"}},
                        "required": ["symbol"],
                    },
                },
                {
                    "name": "get_company_info",
                    "description": "Get company information",
                    "parameters": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string", "description": "Stock symbol"}},
                        "required": ["symbol"],
                    },
                },
            ],
            "query": "Get both the stock price and company info for AAPL",
            "expected_calls": [
                {"name": "get_stock_price", "arguments": {"symbol": "AAPL"}},
                {"name": "get_company_info", "arguments": {"symbol": "AAPL"}},
            ],
        },
        {
            "category": "simple",
            "tools": [
                {
                    "name": "send_email",
                    "description": "Send an email",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email"},
                            "subject": {"type": "string", "description": "Email subject"},
                            "body": {"type": "string", "description": "Email body"},
                        },
                        "required": ["to", "subject", "body"],
                    },
                }
            ],
            "query": "Send an email to john@example.com with subject 'Meeting' and body 'Let's meet tomorrow'",
            "expected_calls": [
                {
                    "name": "send_email",
                    "arguments": {
                        "to": "john@example.com",
                        "subject": "Meeting",
                        "body": "Let's meet tomorrow",
                    },
                }
            ],
        },
    ]

    def __init__(self, client, config: Dict[str, Any]):
        super().__init__(client, config)
        self.categories = config.get("categories", ["simple", "multi_turn", "parallel"])

    def run(self, samples: int = 100) -> List[BenchmarkResult]:
        """Run BFCL benchmark."""
        import random

        filtered_scenarios = [s for s in self.SCENARIOS if s["category"] in self.categories]
        scenarios = random.choices(filtered_scenarios, k=min(samples, len(filtered_scenarios)))

        correct = 0
        results = []

        for i, scenario in enumerate(scenarios):
            # Format tools description
            tools_desc = json.dumps(scenario["tools"], indent=2)

            prompt = f"""Tools available:

{tools_desc}

User query: {scenario["query"]}

Respond with ONLY a valid JSON object (no markdown, no explanation):
{{"tool_calls": [{{"name": "tool_name", "arguments": {{"param": "value"}}}}]}}"""

            messages = [
                {
                    "role": "system",
                    "content": "You are a function-calling API. You MUST respond with ONLY a raw JSON object — no markdown fences, no explanations, no surrounding text. Output must be valid, parseable JSON starting with '{' and ending with '}'.",
                },
                {"role": "user", "content": prompt},
            ]

            try:
                response, _ = self.client.chat_completion(
                    messages=messages, temperature=0.0, max_tokens=500
                )

                if self.verbose:
                    print(f"\n[VERBOSE bfcl #{i + 1}] Query: {scenario['query'][:80]}")
                    print(
                        f"[VERBOSE bfcl #{i + 1}] Response ({len(response)} chars): {repr(response[:200])}"
                    )

                # Parse response - handle markdown wrapping
                is_correct = self._evaluate_tool_calls(response, scenario["expected_calls"])

                if self.verbose:
                    print(
                        f"[VERBOSE bfcl #{i + 1}] Tool calls: {'MATCHED' if is_correct else 'MISMATCHED'}"
                    )

                if is_correct:
                    correct += 1

                results.append(
                    BenchmarkResult(
                        benchmark_name="bfcl",
                        metric_name="tool_use_accuracy",
                        score=1.0 if is_correct else 0.0,
                        metadata={
                            "category": scenario["category"],
                            "query": scenario["query"],
                            "expected": scenario["expected_calls"],
                        },
                    )
                )

                if (i + 1) % 5 == 0:
                    print(
                        f"  Progress: {i + 1}/{len(scenarios)} | Accuracy: {correct / (i + 1):.2%}"
                    )

            except Exception as e:
                print(f"  Error on scenario {i + 1}: {e}")
                results.append(
                    BenchmarkResult(
                        benchmark_name="bfcl",
                        metric_name="tool_use_accuracy",
                        score=0.0,
                        metadata={"error": str(e)},
                    )
                )

        accuracy = correct / len(scenarios) if scenarios else 0
        results.append(
            BenchmarkResult(
                benchmark_name="bfcl",
                metric_name="overall_accuracy",
                score=accuracy,
                metadata={"total_scenarios": len(scenarios), "correct": correct},
            )
        )

        print(f"\n  BFCL Accuracy: {accuracy:.2%} ({correct}/{len(scenarios)})")

        return results

    def _evaluate_tool_calls(self, response: str, expected: List[Dict]) -> bool:
        """Evaluate if the tool calls match expected, handling markdown wrapping."""
        # Extract JSON from response (strip markdown, find JSON object)
        json_text = self._extract_json(response)
        if json_text is None:
            return False

        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            return False

        if "tool_calls" not in parsed:
            return False

        calls = parsed["tool_calls"]

        # Check number of calls
        if len(calls) != len(expected):
            return False

        # Check each call
        for call, exp in zip(calls, expected):
            if call["name"] != exp["name"]:
                return False
            if call.get("arguments") != exp["arguments"]:
                # Allow partial matches for arguments
                for key, value in exp["arguments"].items():
                    if call.get("arguments", {}).get(key) != value:
                        return False

        return True

    def _extract_json(self, response: str) -> Optional[str]:
        """Extract JSON from a model response, handling markdown wrapping."""
        text = response.strip()

        # Strategy 1: Remove markdown code fences (```json ... ```)
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if json_match:
            return json_match.group(1).strip()

        # Strategy 2: Find outermost JSON object (first { to last })
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]

        # Strategy 3: Raw text as fallback
        return text
