#!/usr/bin/env python3
"""
Prompt Pack System - Community-Extensible Benchmark Packs

Provides loading, validation, and generation for prompt packs.
Each pack is a self-contained directory with:
  - pack.json (metadata)
  - prompts/*.json (parameterized prompt templates)

Packs enable:
  - Community contributions via PRs
  - Reproducible benchmarks with versioned prompts
  - A/B testing between different prompt sets
  - Category-specific evaluation
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# Root directory for prompt packs
PACKS_ROOT = Path(__file__).parent


class PackValidationError(Exception):
    """Raised when a pack fails validation."""

    pass


@dataclass
class PackPrompt:
    """A single prompt template from a pack with parameterization info."""

    id: str
    task: str
    template: str
    params: Dict[str, List[str]]
    constraints: List[str]
    expected_keywords: List[str]
    difficulty: str
    category_id: str
    code: Optional[str] = None
    issue: Optional[str] = None
    expected_fix: Optional[List[str]] = None

    def generate(self, param_overrides: Optional[Dict[str, str]] = None) -> str:
        """Generate a concrete prompt from the template by resolving parameters."""
        resolved = {}
        for param, options in self.params.items():
            if param_overrides and param in param_overrides:
                resolved[param] = param_overrides[param]
            else:
                resolved[param] = random.choice(options)

        prompt = self.template.format(**resolved)

        # Append constraints
        if self.constraints:
            prompt += "\n\nConstraints:\n"
            for i, constraint in enumerate(self.constraints, 1):
                prompt += f"{i}. {constraint}\n"

        if self.code:
            prompt += f"\n\n```typescript\n{self.code}\n```"

        if self.issue:
            prompt += f"\n\n**Issue**: {self.issue}"
            prompt += "\n\nExplain:\n1. What's causing the bug\n2. Why it happens\n3. How to fix it with code\n\nProvide a complete, working solution."

        return prompt


@dataclass
class PackCategory:
    """A category within a prompt pack."""

    id: str
    label: str
    difficulty: List[str]
    count: int
    prompts: List[PackPrompt] = field(default_factory=list)


@dataclass
class PromptPack:
    """A complete prompt pack with metadata and categories."""

    name: str
    version: str
    description: str
    tags: List[str]
    generator: str
    path: Path
    categories: List[PackCategory] = field(default_factory=list)
    total_prompts: int = 0

    def get_prompt(
        self, category_id: Optional[str] = None, difficulty: Optional[str] = None
    ) -> PackPrompt:
        """Get a random prompt, optionally filtered by category and difficulty."""
        candidates = []

        for category in self.categories:
            if category_id and category.id != category_id:
                continue
            for prompt in category.prompts:
                if difficulty and prompt.difficulty != difficulty:
                    continue
                candidates.append(prompt)

        if not candidates:
            raise ValueError(f"No prompts matching category={category_id}, difficulty={difficulty}")

        return random.choice(candidates)

    def get_prompts_by_category(self, category_id: str) -> List[PackPrompt]:
        """Get all prompts for a specific category."""
        for category in self.categories:
            if category.id == category_id:
                return category.prompts
        return []

    def get_all_prompts(self) -> List[PackPrompt]:
        """Get all prompts across all categories."""
        all_prompts = []
        for category in self.categories:
            all_prompts.extend(category.prompts)
        return all_prompts


class PackValidator:
    """Validate prompt packs against the schema."""

    @staticmethod
    def validate_pack_json(pack_json: Dict[str, Any]) -> List[str]:
        """Validate pack.json structure. Returns list of errors (empty = valid)."""
        errors = []

        required_fields = ["name", "version", "description", "tags", "generator", "categories"]
        for field in required_fields:
            if field not in pack_json:
                errors.append(f"Missing required field: {field}")

        if "categories" in pack_json:
            for i, cat in enumerate(pack_json["categories"]):
                for field in ["id", "label", "difficulty", "count"]:
                    if field not in cat:
                        errors.append(f"Category {i}: missing field '{field}'")

        if "tags" in pack_json and not isinstance(pack_json["tags"], list):
            errors.append("'tags' must be a list")

        return errors

    @staticmethod
    def validate_prompt_json(prompt_json: Dict[str, Any]) -> List[str]:
        """Validate prompts/*.json structure. Returns list of errors."""
        errors = []

        if "id" not in prompt_json:
            errors.append("Missing 'id' in prompt file")
        if "prompts" not in prompt_json:
            errors.append("Missing 'prompts' array in prompt file")
        elif isinstance(prompt_json["prompts"], list):
            for i, p in enumerate(prompt_json["prompts"]):
                for field in ["id", "task", "difficulty"]:
                    if field not in p:
                        errors.append(f"Prompt {i}: missing field '{field}'")
        else:
            errors.append("'prompts' must be an array")

        return errors

    @staticmethod
    def check_duplicates(prompts: List[PackPrompt]) -> List[str]:
        """Check for duplicate prompt IDs across a pack."""
        seen = set()
        duplicates = []
        for p in prompts:
            if p.id in seen:
                duplicates.append(f"Duplicate prompt ID: {p.id}")
            seen.add(p.id)
        return duplicates


class PackLoader:
    """Load and register prompt packs from the filesystem."""

    def __init__(self, packs_root: Optional[Path] = None):
        self.packs_root = packs_root or PACKS_ROOT
        self.packs: Dict[str, PromptPack] = {}
        self.validator = PackValidator()
        self._discover_packs()

    def _discover_packs(self):
        """Discover all valid prompt packs in the packs root."""
        if not self.packs_root.exists():
            return

        for pack_dir in self.packs_root.iterdir():
            if (
                pack_dir.is_dir()
                and not pack_dir.name.startswith(".")
                and not pack_dir.name.startswith("__")
            ):
                pack_json_path = pack_dir / "pack.json"
                if pack_json_path.exists():
                    try:
                        pack = self.load_pack(pack_dir)
                        self.packs[pack.name] = pack
                    except PackValidationError as e:
                        print(f"Warning: Skipping invalid pack '{pack_dir.name}': {e}")

    def load_pack(self, pack_dir: Path) -> PromptPack:
        """Load a single prompt pack from a directory."""
        pack_json_path = pack_dir / "pack.json"

        if not pack_json_path.exists():
            raise PackValidationError(f"No pack.json found in {pack_dir}")

        with open(pack_json_path) as f:
            pack_data = json.load(f)

        # Validate pack.json
        errors = self.validator.validate_pack_json(pack_data)
        if errors:
            raise PackValidationError(f"Invalid pack.json: {'; '.join(errors)}")

        # Create pack
        pack = PromptPack(
            name=pack_data["name"],
            version=pack_data["version"],
            description=pack_data["description"],
            tags=pack_data["tags"],
            generator=pack_data["generator"],
            path=pack_dir,
            total_prompts=pack_data.get("total_prompts", 0),
        )

        # Load categories from pack.json
        for cat_data in pack_data.get("categories", []):
            category = PackCategory(
                id=cat_data["id"],
                label=cat_data["label"],
                difficulty=cat_data["difficulty"],
                count=cat_data["count"],
            )
            pack.categories.append(category)

        # Load prompts from prompts/ directory
        prompts_dir = pack_dir / "prompts"
        if prompts_dir.exists():
            for prompt_file in sorted(prompts_dir.glob("*.json")):
                with open(prompt_file) as f:
                    prompt_data = json.load(f)

                # Validate prompt file
                errors = self.validator.validate_prompt_json(prompt_data)
                if errors:
                    print(f"Warning: Invalid prompt file {prompt_file}: {'; '.join(errors)}")
                    continue

                category_id = prompt_data["id"]
                cat_prompts = []

                for p_data in prompt_data["prompts"]:
                    prompt = PackPrompt(
                        id=p_data["id"],
                        task=p_data["task"],
                        template=p_data.get("template", ""),
                        params=p_data.get("params", {}),
                        constraints=p_data.get("constraints", []),
                        expected_keywords=p_data.get("expected_keywords", []),
                        difficulty=p_data.get("difficulty", "medium"),
                        category_id=category_id,
                        code=p_data.get("code"),
                        issue=p_data.get("issue"),
                        expected_fix=p_data.get("expected_fix"),
                    )
                    cat_prompts.append(prompt)

                # Add prompts to the matching category
                for category in pack.categories:
                    if category.id == category_id:
                        category.prompts = cat_prompts
                        break

        # Check for duplicate IDs
        all_prompts = pack.get_all_prompts()
        dupes = self.validator.check_duplicates(all_prompts)
        if dupes:
            raise PackValidationError(f"Duplicate prompt IDs: {'; '.join(dupes)}")

        return pack

    def get_pack(self, name: str) -> Optional[PromptPack]:
        """Get a pack by name."""
        return self.packs.get(name)

    def list_packs(self) -> List[str]:
        """List all loaded pack names."""
        return list(self.packs.keys())

    def get_pack_info(self) -> List[Dict[str, Any]]:
        """Get metadata for all loaded packs."""
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "tags": p.tags,
                "total_prompts": len(p.get_all_prompts()),
                "categories": [c.label for c in p.categories],
            }
            for p in self.packs.values()
        ]

    def generate_from_packs(
        self,
        pack_names: Optional[List[str]] = None,
        total_prompts: int = 20,
        seed: Optional[int] = None,
    ) -> List[str]:
        """Generate concrete prompts from specified packs.

        Args:
            pack_names: List of pack names to use. None = all packs.
            total_prompts: Total prompts to generate across all packs.
            seed: Random seed for reproducibility.
        """
        if seed is not None:
            random.seed(seed)

        target_packs = []
        if pack_names:
            for name in pack_names:
                pack = self.packs.get(name)
                if pack:
                    target_packs.append(pack)
                else:
                    print(f"Warning: Pack '{name}' not found")
        else:
            target_packs = list(self.packs.values())

        if not target_packs:
            print("No packs available")
            return []

        # Distribute prompts evenly across packs
        prompts_per_pack = max(1, total_prompts // len(target_packs))
        generated = []

        for pack in target_packs:
            for _ in range(prompts_per_pack):
                try:
                    prompt = pack.get_prompt()
                    generated.append(prompt.generate())
                except ValueError:
                    continue

        # Shuffle for variety
        random.shuffle(generated)
        return generated[:total_prompts]


# Convenience functions


def load_all_packs() -> PackLoader:
    """Load all prompt packs and return the loader."""
    loader = PackLoader()
    print(f"Loaded {len(loader.packs)} prompt packs: {', '.join(loader.list_packs())}")
    return loader


def list_available_packs() -> List[Dict[str, Any]]:
    """List all available prompt packs with metadata."""
    loader = PackLoader()
    return loader.get_pack_info()


if __name__ == "__main__":
    # Test pack loading
    loader = PackLoader()
    print(f"\n📦 Loaded {len(loader.packs)} prompt packs:\n")

    for info in loader.get_pack_info():
        print(f"  {info['name']} v{info['version']}")
        print(f"    {info['description']}")
        print(f"    Tags: {', '.join(info['tags'])}")
        print(f"    Prompts: {info['total_prompts']}")
        print(f"    Categories: {', '.join(info['categories'])}")
        print()

    # Test prompt generation
    print("\n📝 Generating sample prompts:\n")
    for i, prompt_text in enumerate(loader.generate_from_packs(total_prompts=3, seed=42), 1):
        print(f"--- Prompt {i} ---")
        print(prompt_text[:300] + "...\n")
