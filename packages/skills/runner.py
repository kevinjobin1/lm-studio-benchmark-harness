"""
Skill Runner — standalone runtime executor for skills.

Wires together:
1. Skill registry lookup
2. Input validation against schema
3. Sandboxed execution via ``Skill.run()``
4. ToolCallEvent emission to the EventBus
5. Structured result with timing

Usage:
    from skills.runner import SkillRunner, execute_skill_sync

    runner = SkillRunner(registry)
    result = await runner.execute("read_file", {"path": "test.txt"})
"""

from __future__ import annotations

import time
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .types import SkillInput, SkillContext, SkillOutput
from .registry import SkillRegistry


@dataclass
class SkillExecutionResult:
    """Structured result from a single skill execution."""

    success: bool
    skill_name: str
    skill_version: str
    input_data: Dict[str, Any]
    output: Optional[SkillOutput] = None
    error: Optional[str] = None
    timing_ms: float = 0.0
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "skill_name": self.skill_name,
            "skill_version": self.skill_version,
            "input_data": self.input_data,
            "output": self.output.to_dict() if self.output else None,
            "error": self.error,
            "timing_ms": self.timing_ms,
            "validation_errors": self.validation_errors,
        }


class SkillRunner:
    """Standalone runtime executor for skills.

    Args:
        registry: Initialized SkillRegistry with loaded skills.
        event_bus: Optional EventBus instance — if provided, ToolCallEvent
            events are emitted on each skill execution.
        event_source: Source string for emitted events (e.g. "skill.cli").
    """

    def __init__(
        self,
        registry: SkillRegistry,
        event_bus: Any = None,
        event_source: str = "skill.runner",
    ):
        self.registry = registry
        self.event_bus = event_bus
        self.event_source = event_source

    # ── Core execution ─────────────────────────────────────────────

    async def execute(
        self,
        skill_name: str,
        input_data: Dict[str, Any],
        context: Optional[SkillContext] = None,
        run_id: str = "",
        model: str = "",
    ) -> SkillExecutionResult:
        """Execute a skill by name with the given input.

        Steps:
        1. Look up the skill in the registry
        2. Validate input against the skill's schema
        3. Execute the skill (async)
        4. Emit a ToolCallEvent (if event_bus configured)
        5. Return a structured result with timing

        Args:
            skill_name: Name of the skill to execute.
            input_data: Raw input dict for the skill.
            context: Optional SkillContext (defaults to empty).
            run_id: Optional run_id for event correlation.
            model: Optional model name for event metadata.

        Returns:
            SkillExecutionResult with output or error.
        """
        start_time = time.time()

        # 1. Look up the skill
        try:
            skill = self.registry.get(skill_name)
        except KeyError as e:
            elapsed = (time.time() - start_time) * 1000
            return SkillExecutionResult(
                success=False,
                skill_name=skill_name,
                skill_version="",
                input_data=input_data,
                error=str(e),
                timing_ms=elapsed,
            )

        # 2. Validate input
        validation_errors = skill.validate_input(input_data)
        if validation_errors:
            elapsed = (time.time() - start_time) * 1000
            result = SkillExecutionResult(
                success=False,
                skill_name=skill_name,
                skill_version=skill.manifest.version,
                input_data=input_data,
                error="Input validation failed",
                timing_ms=elapsed,
                validation_errors=validation_errors,
            )
            self._emit_tool_event(result, run_id, model)
            return result

        # 3. Execute the skill
        ctx = context or SkillContext()
        skill_input = SkillInput(raw=input_data, _validated=True)

        try:
            output = await skill.run(skill_input, ctx)
            elapsed = (time.time() - start_time) * 1000

            result = SkillExecutionResult(
                success=output.success,
                skill_name=skill_name,
                skill_version=skill.manifest.version,
                input_data=input_data,
                output=output,
                timing_ms=elapsed,
                validation_errors=[],
            )

            if not output.success:
                result.error = output.error

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            result = SkillExecutionResult(
                success=False,
                skill_name=skill_name,
                skill_version=skill.manifest.version,
                input_data=input_data,
                error=f"Skill execution error: {e}",
                timing_ms=elapsed,
                validation_errors=[],
            )

        # 4. Emit event
        self._emit_tool_event(result, run_id, model)

        return result

    def execute_sync(
        self,
        skill_name: str,
        input_data: Dict[str, Any],
        context: Optional[SkillContext] = None,
        run_id: str = "",
        model: str = "",
    ) -> SkillExecutionResult:
        """Synchronous version of ``execute()``.

        Runs the async skill execution in a new event loop.
        """
        return asyncio.run(
            self.execute(
                skill_name=skill_name,
                input_data=input_data,
                context=context,
                run_id=run_id,
                model=model,
            )
        )

    # ── Event emission ─────────────────────────────────────────────

    def _emit_tool_event(
        self,
        result: SkillExecutionResult,
        run_id: str,
        model: str,
    ) -> None:
        """Emit a ToolCallEvent to the EventBus (if configured)."""
        if self.event_bus is None:
            return

        try:
            from events import ToolCallEvent

            event = ToolCallEvent(
                tool_name=result.skill_name,
                input_args=result.input_data,
                model=model,
                run_id=run_id,
                source=self.event_source,
                timestamp_ms=time.time() * 1000,
            )
            self.event_bus.emit_sync(event)
        except Exception:
            pass  # Don't let event emission fail execution

    # ── Batch execution ────────────────────────────────────────────

    async def execute_batch(
        self,
        skills: List[Dict[str, Any]],
        context: Optional[SkillContext] = None,
        run_id: str = "",
        model: str = "",
    ) -> List[SkillExecutionResult]:
        """Execute multiple skills sequentially.

        Each item in the list should have:
            - ``skill``: Skill name (str)
            - ``input``: Input data dict (optional, defaults to {})

        Args:
            skills: List of skill execution descriptors.
            context: Shared SkillContext across all executions.
            run_id: Run ID for event correlation.
            model: Model name for event metadata.

        Returns:
            List of SkillExecutionResult in execution order.
        """
        results: List[SkillExecutionResult] = []
        for item in skills:
            name = item.get("skill", "")
            inp = item.get("input", {})
            result = await self.execute(
                skill_name=name,
                input_data=inp,
                context=context,
                run_id=run_id,
                model=model,
            )
            results.append(result)
        return results

    def execute_batch_sync(
        self,
        skills: List[Dict[str, Any]],
        context: Optional[SkillContext] = None,
        run_id: str = "",
        model: str = "",
    ) -> List[SkillExecutionResult]:
        """Synchronous version of ``execute_batch()``."""
        return asyncio.run(
            self.execute_batch(
                skills=skills,
                context=context,
                run_id=run_id,
                model=model,
            )
        )

    # ── Introspection ──────────────────────────────────────────────

    def list_skills(self) -> List[str]:
        """List all available skill names from the registry."""
        return self.registry.list_names()

    def get_skill_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get skill metadata (manifest info) by name."""
        try:
            skill = self.registry.get(name)
            return skill.to_dict()
        except KeyError:
            return None


# ── Convenience functions ─────────────────────────────────────────


def create_runner(
    lockfile_path: str = "modellens.lock",
    event_bus: Any = None,
) -> SkillRunner:
    """Factory function: create a SkillRegistry and SkillRunner.

    Args:
        lockfile_path: Path to the modellens.lock file.
        event_bus: Optional EventBus for ToolCallEvent emission.

    Returns:
        Initialized SkillRunner with built-in skills loaded.
    """
    try:
        from .registry import create_registry

        registry = create_registry(lockfile_path=lockfile_path, load_builtins=True)
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize skill registry: {exc}") from exc

    return SkillRunner(registry=registry, event_bus=event_bus, event_source="skill.runner")


__all__ = [
    "SkillRunner",
    "SkillExecutionResult",
    "create_runner",
]
