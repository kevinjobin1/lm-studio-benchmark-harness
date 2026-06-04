#!/usr/bin/env python3
"""
Built-in Skill: read_file

Reads file contents within the sandbox.
Deterministic: same file → same content.
"""

import os
from pathlib import Path

from ..types import Skill, SkillManifest, SkillInput, SkillContext, SkillOutput


class ReadFileSkill(Skill):
    """Read a file within the sandbox and return its contents."""

    def _create_manifest(self) -> SkillManifest:
        return SkillManifest(
            name="read_file",
            version="1.0.0",
            description="Read a file within the sandbox and return its contents as a string.",
            input_schema={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file within the sandbox",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (default: utf-8)",
                        "default": "utf-8",
                    },
                },
            },
            output_schema={
                "type": "object",
                "required": ["success", "data"],
                "properties": {
                    "success": {"type": "boolean"},
                    "data": {"type": "string"},
                    "error": {"type": "string"},
                },
            },
            tags=["filesystem", "read", "core"],
        )

    async def run(self, input_data: SkillInput, ctx: SkillContext) -> SkillOutput:
        file_path = input_data.get("path", "")
        encoding = input_data.get("encoding", "utf-8")

        # Resolve within sandbox
        full_path = ctx.get_sandbox_path(file_path)

        try:
            if not os.path.exists(full_path):
                return SkillOutput(
                    success=False,
                    error=f"File not found: {file_path}",
                )

            with open(full_path, "r", encoding=encoding) as f:
                content = f.read()

            return SkillOutput(
                success=True,
                data=content,
                metadata={
                    "path": file_path,
                    "size_bytes": len(content.encode(encoding)),
                    "encoding": encoding,
                },
            )

        except PermissionError:
            return SkillOutput(success=False, error=f"Permission denied: {file_path}")
        except UnicodeDecodeError:
            return SkillOutput(success=False, error=f"Invalid encoding for {file_path}")
        except Exception as e:
            return SkillOutput(success=False, error=str(e))
