#!/usr/bin/env python3
"""
Built-in Skill: write_file

Writes content to a file within the sandbox.
Deterministic: same input → same file state.
"""

import os
from pathlib import Path

from ..types import Skill, SkillManifest, SkillInput, SkillContext, SkillOutput


class WriteFileSkill(Skill):
    """Write content to a file within the sandbox."""

    def _create_manifest(self) -> SkillManifest:
        return SkillManifest(
            name="write_file",
            version="1.0.0",
            description="Write content to a file within the sandbox. Creates parent directories if needed.",
            input_schema={
                "type": "object",
                "required": ["path", "content"],
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to write within the sandbox",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
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
                    "data": {"type": "object"},
                    "error": {"type": "string"},
                },
            },
            tags=["filesystem", "write", "core"],
        )

    async def run(self, input_data: SkillInput, ctx: SkillContext) -> SkillOutput:
        file_path = input_data.get("path", "")
        content = input_data.get("content", "")
        encoding = input_data.get("encoding", "utf-8")

        if not file_path:
            return SkillOutput(success=False, error="Path is required")

        # Resolve within sandbox
        full_path = ctx.get_sandbox_path(file_path)

        try:
            # Create parent directories
            parent = os.path.dirname(full_path)
            os.makedirs(parent, exist_ok=True)

            with open(full_path, "w", encoding=encoding) as f:
                f.write(content)

            file_size = os.path.getsize(full_path)

            return SkillOutput(
                success=True,
                data={
                    "path": file_path,
                    "size_bytes": file_size,
                },
                metadata={
                    "path": file_path,
                    "size_bytes": file_size,
                    "encoding": encoding,
                },
            )

        except PermissionError:
            return SkillOutput(success=False, error=f"Permission denied: {file_path}")
        except OSError as e:
            return SkillOutput(success=False, error=f"IO error: {e}")
        except Exception as e:
            return SkillOutput(success=False, error=str(e))
