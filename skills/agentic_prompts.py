#!/usr/bin/env python3
"""
Agentic Prompt Templates and Generator

Generates prompts for agentic/tool-use evaluation.
Models must return JSON with an "actions" array using only permitted skills.
"""

import random
from typing import Dict, List, Optional
from dataclasses import dataclass

# ── Agentic Prompt Dataclass ─────────────────────────────────────


@dataclass
class AgenticPrompt:
    """A prompt for agentic/tool-use evaluation."""
    task: str
    description: str
    available_skills: List[str]
    input_context: str
    expected_actions: List[Dict]  # Ground truth for evaluation
    expected_params: Optional[Dict[str, Dict]] = None
    difficulty: str = "medium"


class AgenticPromptGenerator:
    """Generate agentic tool-use prompts across multiple scenarios."""

    SCENARIOS = [
        {
            "task": "Refactor code using provided skills",
            "description": "Read a TypeScript file, make changes, and generate a diff.",
            "skills": ["read_file", "write_file", "diff"],
            "input": "src/index.ts",
            "expected": [
                {"skill": "read_file", "input": {"path": "src/index.ts"}},
                {"skill": "write_file", "input": {"path": "src/index.ts"}},
                {"skill": "diff", "input": {"a": "...", "b": "..."}},
            ],
            "difficulty": "medium",
        },
        {
            "task": "Parse and validate JSON data",
            "description": "Read a JSON config file, parse it, and write validated output.",
            "skills": ["read_file", "json_parse", "write_file"],
            "input": "config.json",
            "expected": [
                {"skill": "read_file", "input": {"path": "config.json"}},
                {"skill": "json_parse", "input": {"json_string": "..."}},
                {"skill": "write_file", "input": {"path": "config_validated.json"}},
            ],
            "difficulty": "easy",
        },
        {
            "task": "Compare two files and summarize changes",
            "description": "Read two versions of a file and compute their diff.",
            "skills": ["read_file", "diff"],
            "input": "original.ts vs modified.ts",
            "expected": [
                {"skill": "read_file", "input": {"path": "original.ts"}},
                {"skill": "read_file", "input": {"path": "modified.ts"}},
                {"skill": "diff", "input": {"a": "...", "b": "..."}},
            ],
            "difficulty": "easy",
        },
        {
            "task": "Read and transform API response",
            "description": "Read a JSON file containing an API response, parse it, and write a transformed version.",
            "skills": ["read_file", "json_parse", "write_file"],
            "input": "api_response.json",
            "expected": [
                {"skill": "read_file", "input": {"path": "api_response.json"}},
                {"skill": "json_parse", "input": {"json_string": "..."}},
                {"skill": "write_file", "input": {"path": "api_transformed.json"}},
            ],
            "difficulty": "medium",
        },
        {
            "task": "Debug a code file and apply fix",
            "description": "Read a buggy file, fix it, write the fix, and show the diff.",
            "skills": ["read_file", "write_file", "diff"],
            "input": "src/buggy.ts",
            "expected": [
                {"skill": "read_file", "input": {"path": "src/buggy.ts"}},
                {"skill": "write_file", "input": {"path": "src/buggy.ts"}},
                {"skill": "diff", "input": {"a": "...", "b": "..."}},
            ],
            "difficulty": "hard",
        },
        {
            "task": "Extract and validate nested JSON",
            "description": "Read a file containing embedded JSON, parse it, and validate the structure.",
            "skills": ["read_file", "json_parse"],
            "input": "nested_data.txt",
            "expected": [
                {"skill": "read_file", "input": {"path": "nested_data.txt"}},
                {"skill": "json_parse", "input": {"json_string": "..."}},
            ],
            "difficulty": "medium",
        },
    ]

    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
        self.seed = seed

    def generate_prompt(
        self,
        scenario_index: Optional[int] = None,
        difficulty: Optional[str] = None,
    ) -> AgenticPrompt:
        """Generate an agentic prompt.

        Args:
            scenario_index: Specific scenario index (None = random)
            difficulty: Filter by difficulty (None = any)
        """
        scenarios = self.SCENARIOS
        if difficulty:
            scenarios = [s for s in scenarios if s["difficulty"] == difficulty]
            if not scenarios:
                scenarios = self.SCENARIOS

        if scenario_index is not None and 0 <= scenario_index < len(scenarios):
            scenario = scenarios[scenario_index]
        else:
            scenario = random.choice(scenarios)

        return AgenticPrompt(
            task=scenario["task"],
            description=scenario["description"],
            available_skills=scenario["skills"],
            input_context=scenario["input"],
            expected_actions=[dict(a) for a in scenario["expected"]],
            difficulty=scenario.get("difficulty", "medium"),
        )

    def generate_batch(
        self,
        count: int = 5,
        difficulty_distribution: Optional[Dict[str, float]] = None,
    ) -> List[AgenticPrompt]:
        """Generate a batch of agentic prompts."""
        prompts = []
        for _ in range(count):
            difficulty = None
            if difficulty_distribution:
                rc = random.random()
                if rc < difficulty_distribution.get("easy", 0.33):
                    difficulty = "easy"
                elif rc < difficulty_distribution.get("easy", 0.33) + difficulty_distribution.get("medium", 0.34):
                    difficulty = "medium"
                else:
                    difficulty = "hard"
            prompts.append(self.generate_prompt(difficulty=difficulty))

        random.shuffle(prompts)
        return prompts

    def get_strict_prompt_template(self, available_skills: List[str]) -> str:
        """Get the strict agent prompt template.

        Models are instructed to:
        - Use ONLY the listed skills
        - Return ONLY valid JSON with "actions" array
        - NOT execute code
        - NOT explain or add commentary
        """
        skills_list = ", ".join(available_skills)
        skills_example = "\n".join(
            f'  {{"skill": "{s}", "input": {{ ... }}}}' for s in available_skills
        )

        return f"""You are allowed to use only the following skills:
{skills_list}

Return ONLY valid JSON with an "actions" array.

Do not execute code.
Do not explain.
Do not add commentary.

Example format:
{{
  "actions": [
{skills_example}
  ]
}}

Respond with ONLY the JSON. No markdown fences. No additional text."""


# ── Convenience Functions ─────────────────────────────────────────

def generate_agentic_prompts(count: int = 5) -> List[AgenticPrompt]:
    """Generate a batch of agentic tool-use prompts."""
    gen = AgenticPromptGenerator()
    return gen.generate_batch(count)


def get_agentic_template(skills: List[str]) -> str:
    """Get the strict agent prompt template for specified skills."""
    gen = AgenticPromptGenerator()
    return gen.get_strict_prompt_template(skills)


if __name__ == "__main__":
    gen = AgenticPromptGenerator(seed=42)

    print("=== Agentic Prompt Example ===")
    prompt = gen.generate_prompt()
    print(f"Task: {prompt.task}")
    print(f"Skills: {prompt.available_skills}")
    print(f"Input: {prompt.input_context}")
    print(f"Expected actions: {len(prompt.expected_actions)}")
    print(f"Difficulty: {prompt.difficulty}")
    print()

    print("=== Strict Prompt Template ===")
    print(get_agentic_template(["read_file", "diff", "json_parse"]))
    print()

    print("=== Batch Generation ===")
    batch = gen.generate_batch(3)
    for i, p in enumerate(batch):
        print(f"  {i + 1}. [{p.difficulty}] {p.task} ({', '.join(p.available_skills)})")
