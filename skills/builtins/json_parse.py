#!/usr/bin/env python3
"""
Built-in Skill: json_parse

Parses a JSON string and returns the parsed object.
Deterministic: same string → same parsed object.
"""

import json

from ..types import Skill, SkillManifest, SkillInput, SkillContext, SkillOutput


class JsonParseSkill(Skill):
    """Parse a JSON string into a Python object."""

    def _create_manifest(self) -> SkillManifest:
        return SkillManifest(
            name="json_parse",
            version="1.0.0",
            description="Parse a JSON string and return the parsed object. Useful for extracting structured data from model output.",
            input_schema={
                "type": "object",
                "required": ["json_string"],
                "properties": {
                    "json_string": {
                        "type": "string",
                        "description": "The JSON string to parse",
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
            tags=["data", "parsing", "core"],
        )

    async def run(self, input_data: SkillInput, ctx: SkillContext) -> SkillOutput:
        json_str = input_data.get("json_string", "")

        try:
            parsed = json.loads(json_str)

            return SkillOutput(
                success=True,
                data=parsed,
                metadata={
                    "type": type(parsed).__name__,
                },
            )

        except json.JSONDecodeError as e:
            return SkillOutput(
                success=False,
                error=f"Invalid JSON: {e}",
            )
        except Exception as e:
            return SkillOutput(success=False, error=str(e))
