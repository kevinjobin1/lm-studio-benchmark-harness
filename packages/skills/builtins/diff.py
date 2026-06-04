#!/usr/bin/env python3
"""
Built-in Skill: diff

Computes a unified diff between two strings.
Deterministic: same inputs → same diff output.
"""

import difflib
from typing import List

from ..types import Skill, SkillManifest, SkillInput, SkillContext, SkillOutput


class DiffSkill(Skill):
    """Compute a unified diff between two text strings."""

    def _create_manifest(self) -> SkillManifest:
        return SkillManifest(
            name="diff",
            version="1.0.0",
            description="Compute a unified diff between two strings (e.g., original code and modified code).",
            input_schema={
                "type": "object",
                "required": ["a", "b"],
                "properties": {
                    "a": {
                        "type": "string",
                        "description": "The original text (before changes)",
                    },
                    "b": {
                        "type": "string",
                        "description": "The modified text (after changes)",
                    },
                    "label_a": {
                        "type": "string",
                        "description": "Label for the original text (default: 'original')",
                        "default": "original",
                    },
                    "label_b": {
                        "type": "string",
                        "description": "Label for the modified text (default: 'modified')",
                        "default": "modified",
                    },
                },
            },
            output_schema={
                "type": "object",
                "required": ["success", "data"],
                "properties": {
                    "success": {"type": "boolean"},
                    "data": {"type": "object"},
                    "error": {"type": "string"},
                },
            },
            tags=["code", "diff", "core"],
        )

    async def run(self, input_data: SkillInput, ctx: SkillContext) -> SkillOutput:
        text_a = input_data.get("a", "")
        text_b = input_data.get("b", "")
        label_a = input_data.get("label_a", "original")
        label_b = input_data.get("label_b", "modified")

        try:
            lines_a = text_a.splitlines(keepends=True)
            lines_b = text_b.splitlines(keepends=True)

            diff = difflib.unified_diff(
                lines_a,
                lines_b,
                fromfile=label_a,
                tofile=label_b,
                lineterm="",
            )

            diff_text = "\n".join(diff)

            changes = {
                "added": 0,
                "removed": 0,
                "unchanged": 0,
            }

            for line in diff_text.split("\n"):
                if line.startswith("+") and not line.startswith("+++"):
                    changes["added"] += 1
                elif line.startswith("-") and not line.startswith("---"):
                    changes["removed"] += 1
                elif not line.startswith(("@", "---", "+++", "diff", "index", "new", "old")):
                    if line.strip():
                        changes["unchanged"] += 1

            has_changes = changes["added"] > 0 or changes["removed"] > 0

            return SkillOutput(
                success=True,
                data={
                    "diff": diff_text,
                    "has_changes": has_changes,
                    "stats": changes,
                },
                metadata={
                    "has_changes": has_changes,
                    "added_lines": changes["added"],
                    "removed_lines": changes["removed"],
                },
            )

        except Exception as e:
            return SkillOutput(success=False, error=str(e))
