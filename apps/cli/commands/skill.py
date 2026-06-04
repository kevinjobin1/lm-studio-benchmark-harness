"""Skill commands for modellens CLI.

Executes built-in skills (read_file, write_file, json_parse, diff) and
community skills. Skills are deterministic, sandboxed tools for
agentic evaluation.

Usage:
    modellens skill list
    modellens skill info json_parse
    modellens skill run json_parse '{"json_string": "{\"key\": \"value\"}"}'
    modellens skill run read_file '{"path": "test.txt"}'
    modellens skill run --batch '[{"skill": "read_file", "input": {"path": "a.txt"}}, {"skill": "diff", "input": {"a": "x", "b": "y"}}]'
"""

import json
import sys
from pathlib import Path

import click

from .utils import _echo


@click.group()
def skill():
    """Execute and manage deterministic evaluation skills.

    \b
    Examples:
      modellens skill list
      modellens skill info json_parse
      modellens skill run json_parse '{"json_string": "{\"key\": \"value\"}"}'
    """
    pass


@skill.command(name="list")
def skill_list():
    """List all available skills."""
    try:
        from skills.runner import create_runner

        runner = create_runner()
    except Exception as e:
        _echo(f"✗ Failed to initialize skill registry: {e}", "red")
        sys.exit(1)

    skills = runner.list_skills()
    if not skills:
        _echo("No skills registered.", "yellow")
        return

    _echo("")
    _echo("📦 Available Skills", "bold blue")
    for name in skills:
        info = runner.get_skill_info(name)
        version = info.get("version", "?") if info else "?"
        desc = info.get("description", "") if info else ""
        _echo(f"   {name:<20} v{version:<8} {desc}", "dim")
    _echo("")


@skill.command(name="info")
@click.argument("skill_name")
def skill_info(skill_name):
    """Show detailed info about a skill (schema, description)."""
    try:
        from skills.runner import create_runner

        runner = create_runner()
    except Exception as e:
        _echo(f"✗ Failed to initialize skill registry: {e}", "red")
        sys.exit(1)

    info = runner.get_skill_info(skill_name)
    if not info:
        _echo(f"✗ Skill '{skill_name}' not found.", "red")
        sys.exit(1)

    _echo("")
    _echo(f"📖 Skill: {info['name']}  v{info['version']}", "bold blue")
    _echo(f"   {info['description']}", "dim")
    _echo("")
    _echo("   Input Schema:", "bold")
    click.echo(f"   {json.dumps(info.get('input_schema', {}), indent=4)}")
    _echo("")
    _echo("   Output Schema:", "bold")
    click.echo(f"   {json.dumps(info.get('output_schema', {}), indent=4)}")
    _echo("")


@skill.command(name="run")
@click.argument("skill_name", required=False, default=None)
@click.argument("input_json", required=False, default=None)
@click.option("--batch", default=None, help="JSON array of skill executions (overrides skill_name + input_json)")
@click.option("--json", "json_output", is_flag=True, help="Output result as JSON")
@click.option(
    "--sandbox", default="/tmp/lmbench_sandbox",
    help="Sandbox root directory (default: /tmp/lmbench_sandbox)",
)
@click.option("--model", default="", help="Model name for event metadata")
@click.option("--run-id", default="", help="Run ID for event correlation")
def skill_run(skill_name, input_json, batch, json_output, sandbox, model, run_id):
    """Execute a skill with the given JSON input.

    \b
    Examples:
      modellens skill run json_parse '{"json_string": "{\"key\": \"value\"}"}'
      modellens skill run read_file '{"path": "test.txt"}'
      modellens skill run --batch '[{"skill": "read_file", "input": {"path": "a.txt"}}]'
    """
    from skills.runner import create_runner
    from skills.types import SkillContext

    try:
        runner = create_runner()
    except Exception as e:
        _echo(f"✗ Failed to initialize skill registry: {e}", "red")
        sys.exit(1)

    # Ensure sandbox directory exists
    sandbox_path = Path(sandbox)
    sandbox_path.mkdir(parents=True, exist_ok=True)

    ctx = SkillContext(
        working_directory=str(sandbox_path),
        model_name=model or "",
        run_id=run_id or "",
        sandbox={"_sandbox_root": str(sandbox_path)},
    )

    if batch:
        # Batch mode
        try:
            items = json.loads(batch)
            if not isinstance(items, list):
                raise ValueError("--batch must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            _echo(f"✗ Invalid batch JSON: {e}", "red")
            sys.exit(1)

        results = runner.execute_batch_sync(skills=items, context=ctx, run_id=run_id, model=model)

        if json_output:
            click.echo(json.dumps([r.to_dict() for r in results], indent=2, default=str))
            return

        _echo("")
        _echo("📋 Batch Skill Execution Results", "bold blue")
        for r in results:
            icon = "✓" if r.success else "✗"
            _echo(f"   {icon} {r.skill_name:<20} {r.timing_ms:7.1f}ms", "green" if r.success else "red")
            if not r.success and r.error:
                _echo(f"       Error: {r.error}", "dim")
        _echo("")
    else:
        # Single skill execution
        if not skill_name:
            _echo("✗ Missing SKILL_NAME argument. Use --batch for batch mode.", "red")
            sys.exit(1)

        if not input_json:
            _echo("✗ Missing INPUT_JSON argument.", "red")
            sys.exit(1)

        try:
            inp = json.loads(input_json)
        except json.JSONDecodeError as e:
            _echo(f"✗ Invalid JSON input: {e}", "red")
            sys.exit(1)

        result = runner.execute_sync(
            skill_name=skill_name,
            input_data=inp,
            context=ctx,
            run_id=run_id,
            model=model,
        )

        if json_output:
            click.echo(json.dumps(result.to_dict(), indent=2, default=str))
            return

        icon = "✓" if result.success else "✗"
        _echo("")
        _echo(f"{icon}  Skill: {result.skill_name} v{result.skill_version}", "bold blue" if result.success else "bold red")
        _echo(f"   Timing: {result.timing_ms:.1f}ms", "dim")

        if result.validation_errors:
            _echo(f"   Validation Errors:", "red")
            for err in result.validation_errors:
                _echo(f"     - {err}", "dim")

        if result.error:
            _echo(f"   Error: {result.error}", "red")

        if result.output and result.output.data is not None:
            _echo(f"   Output:", "bold")
            output_str = json.dumps(result.output.data, indent=2, default=str, ensure_ascii=False)
            click.echo(f"   {output_str}")
        _echo("")
