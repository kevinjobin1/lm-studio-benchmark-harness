"""Workload evaluation commands for modellens CLI.

Evaluates models on real-world project workloads (React, NestJS, Rust, Python).
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.table import Table

from .utils import (
    _echo,
    _resolve_provider,
    RICH_AVAILABLE,
    console,
)


@click.group()
def workload():
    """
    Evaluate models on real-world project workloads.

    Loads real project codebases (React, NestJS, Rust, Python),
    generates realistic coding tasks, runs models against them,
    and scores outputs on correctness, code quality, and style.

    \\b
    Examples:
      modellens workload list-projects
      modellens workload run --project nestjs-api --model qwen3.5-9b
      modellens workload run --project-source /path/to/repo --tasks 5
    """
    pass


@workload.command(name="list-projects")
def workload_list_projects():
    """List available built-in projects for workload evaluation."""
    from benchmarks.workload_bench import BUILTIN_PROJECTS

    _echo("")
    _echo("📦 Built-in Workload Projects", "bold blue")
    for name, description in BUILTIN_PROJECTS.items():
        _echo(f"   {name:<20} {description}", "dim")
    _echo("")
    _echo("You can also load any local project with --project-source <path> or a git URL.", "dim")
    _echo("")


@workload.command()
@click.option(
    "--api-base", default=None, show_default=False, help="Provider base URL (auto-detected)"
)
@click.option("--api-key", default=None, show_default=False)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["lm-studio", "ollama", "open-webui", "jan", "llama.cpp", "vllm"]),
    default=None,
    help="Provider (auto-detected if omitted)",
)
@click.option("--model", "-m", required=True, help="Model name to evaluate (required)")
@click.option(
    "--project",
    "-P",
    "project_name",
    default="nestjs-api",
    help="Built-in project name (default: nestjs-api)",
)
@click.option("--project-source", default=None, help="Local path or git URL to a real project")
@click.option("--tasks", "-t", type=int, default=5, help="Number of tasks to generate (default: 5)")
@click.option(
    "--output",
    "-o",
    "output_dir",
    default="results/workload",
    help="Output directory (default: results/workload)",
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed progress and scores")
@click.option("--json", "json_output", is_flag=True, help="Output results as JSON")
@click.option(
    "--sse-port",
    type=int,
    default=0,
    help="Start SSE event bridge on this port for real-time dashboard updates. "
    "0 = auto-select (prints SSE_PORT:N to stdout on start).",
)
@click.option(
    "--cache/--no-cache",
    "use_cache",
    default=True,
    show_default=True,
    help="Enable/disable result caching (content-addressed by model + task)",
)
@click.option(
    "--cache-dir",
    default=None,
    help="Cache directory (default: results/cache)",
)
def run(
    api_base,
    api_key,
    provider,
    model,
    project_name,
    project_source,
    tasks,
    output_dir,
    verbose,
    json_output,
    sse_port,
    use_cache,
    cache_dir,
):
    """Run workload evaluation against a model.

    \\b
    Examples:
      modellens workload run --model qwen3.5-9b
      modellens workload run --model llama3.2 --project react-app
      modellens workload run --model gemma-4 --project-source /path/to/repo --tasks 10
    """
    # Provider resolution
    if provider is None:
        provider, detected_base, detected_key = _resolve_provider()
        api_base = api_base or detected_base
        api_key = api_key or detected_key
    else:
        from providers import get_provider_config

        url, key = get_provider_config(provider)
        api_base = api_base or url
        api_key = api_key or key

    # Validate connection
    import requests

    try:
        check_url = f"{api_base}/models"
        resp = requests.get(check_url, timeout=3)
        if resp.status_code != 200:
            _echo(f"✗ {provider} is not reachable at {check_url}", "red")
            sys.exit(1)
    except Exception:
        _echo(f"✗ {provider} is not reachable", "red")
        sys.exit(1)

    _echo("")
    _echo(f"📦 Workload Evaluation", "bold blue")
    _echo(f"   Model: {model}  |  Provider: {provider}", "dim")

    if project_source:
        _echo(f"   Project source: {project_source}", "dim")
    else:
        _echo(f"   Built-in project: {project_name}", "dim")
    _echo(f"   Tasks to generate: {tasks}", "dim")
    _echo("")

    # ── Event bus infrastructure ─────────────────────────────────
    try:
        from events import default_bus
        from events.sse import EventBusSSEServer
        from events.replay import EventBusReplayWriter
        from core.metrics_store import subscribe_to_event_bus
        from core.regression import subscribe_to_run_events

        subscribe_to_event_bus(default_bus)
        subscribe_to_run_events(default_bus)
        _EVENTS_AVAILABLE = True
    except ImportError:
        default_bus = None
        EventBusSSEServer = None
        EventBusReplayWriter = None
        _EVENTS_AVAILABLE = False

    # ── SSE Bridge ──────────────────────────────────────────────
    sse_server = None
    if _EVENTS_AVAILABLE and sse_port is not None and sse_port > 0:
        try:
            sse_server = EventBusSSEServer(port=sse_port)
            actual_port = sse_server.start()
            print(f"SSE_PORT:{actual_port}", flush=True)
        except ImportError:
            _echo("⚠ events.sse not available — SSE bridge disabled", "yellow")
        except Exception as e:
            _echo(f"⚠ SSE server failed to start: {e}", "yellow")

    # ── Replay Writer ──────────────────────────────────────────
    replay_writer = None
    if _EVENTS_AVAILABLE:
        try:
            replay_writer = EventBusReplayWriter(
                output_dir=str(Path(output_dir) / "replays"),
            )
            replay_writer.start()
        except ImportError:
            pass  # events.replay not available — replay disabled
        except Exception as e:
            _echo(f"⚠ Replay writer failed to start: {e}", "yellow")

    # Import workload packages
    from core.workload import ProjectLoader, TaskGenerator, WorkloadRunner, WorkloadScorer

    # 1. Load project
    loader = ProjectLoader()
    if project_source:
        project = loader.load_project(project_source)
    else:
        project = loader.load_builtin(project_name)

    _echo(f"✅ Loaded project: {project.name}", "bold green")
    _echo(f"   Language: {project.language}  |  Framework: {project.framework}", "dim")
    _echo(f"   Files: {project.total_files}  |  Lines of code: {project.total_lines}", "dim")

    # 2. Generate tasks
    generator = TaskGenerator()
    workload_tasks = generator.generate_tasks(project, count=tasks)

    task_type_counts = {}
    for t in workload_tasks:
        task_type_counts[t.task_type.value] = task_type_counts.get(t.task_type.value, 0) + 1
    _echo(f"\n📝 Generated {len(workload_tasks)} tasks:", "bold")
    for ttype, count in sorted(task_type_counts.items()):
        _echo(f"   {ttype.replace('_', ' ').title():<25} {count}", "dim")

    # 3. Run evaluation
    _echo(f"\n🔍 Evaluating model on {len(workload_tasks)} tasks...\n", "bold")
    scorer = WorkloadScorer()

    # ── Cache setup ───────────────────────────────────────────
    resolved_cache_dir = cache_dir or "results/cache"
    if use_cache:
        from core.cache import ContentAddressableCache

        workload_cache = ContentAddressableCache(resolved_cache_dir)
        cache_status = workload_cache.status()
        if cache_status["entries_exist"]:
            _echo(f"   📦 Cache: {cache_status['total_entries']} existing entries", "dim")
        else:
            _echo("   📦 Cache: empty", "dim")
    else:
        workload_cache = None
        _echo("   📦 Caching disabled (--no-cache)", "dim")

    runner = WorkloadRunner(
        api_base=api_base,
        api_key=api_key,
        model=model,
        scorer=scorer,
        cache=workload_cache,
        use_cache=use_cache,
    )

    # Wrap execution in try/finally to ensure SSE server is stopped
    try:
        results = runner.run_batch(workload_tasks, verbose=verbose)

        # 4. Show results
        _echo(f"\n{'=' * 60}", "dim")
        _echo("📊 Workload Evaluation Results", "bold blue")
        _echo(f"{'=' * 60}", "dim")

        scores_by_type: dict = {}
        for r in results:
            scores_by_type.setdefault(r.task_type, []).append(r.score)

        if RICH_AVAILABLE:
            table = Table(title=f"{model} — {project.name}")
            table.add_column("Task Type", style="cyan")
            table.add_column("Score", style="green", justify="right")
            table.add_column("Correctness", style="magenta", justify="right")
            table.add_column("Completeness", style="yellow", justify="right")
            table.add_column("Quality", style="blue", justify="right")
            table.add_column("Style", style="purple", justify="right")
            table.add_column("Time", style="dim", justify="right")

            for r in results:
                table.add_row(
                    r.task_type.replace("_", " "),
                    f"{r.score:.3f}",
                    f"{r.score_components.get('correctness', 0):.2f}",
                    f"{r.score_components.get('completeness', 0):.2f}",
                    f"{r.score_components.get('code_quality', 0):.2f}",
                    f"{r.score_components.get('style_match', 0):.2f}",
                    f"{r.response_time_ms:.0f}ms" if r.response_time_ms else "—",
                )

            # Overall row
            overall = sum(r.score for r in results) / len(results) if results else 0
            table.add_row(
                "[bold]OVERALL[/bold]",
                f"[bold]{overall:.3f}[/bold]",
                "",
                "",
                "",
                "",
                "",
            )

            console.print("")
            console.print(table)
            console.print("")
        else:
            for r in results:
                _echo(f"   {r.task_type:<25} {r.score:.3f}  ({r.response_time_ms:.0f}ms)")
            overall = sum(r.score for r in results) / len(results) if results else 0
            _echo(f"   {'OVERALL':<25} {overall:.3f}", "bold")

        # Collect failures
        all_failures = []
        for r in results:
            all_failures.extend(r.failures)
        if all_failures:
            _echo(f"\n⚠ Common failure patterns:", "yellow")
            from collections import Counter

            for failure, count in Counter(all_failures).most_common(5):
                _echo(f"   {failure}: {count}", "dim")

        # 5. Save results
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save JSON
        results_data = {
            "model": model,
            "provider": provider,
            "project": project.name,
            "language": project.language,
            "framework": project.framework,
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(results),
            "overall_score": overall,
            "results": [
                {
                    "task_id": r.task_id,
                    "task_type": r.task_type,
                    "title": r.title,
                    "score": r.score,
                    "score_components": r.score_components,
                    "failures": r.failures,
                    "strengths": r.strengths,
                    "response_time_ms": r.response_time_ms,
                    "tokens_used": r.tokens_used,
                    "difficulty": r.difficulty,
                    "target_file": r.target_file,
                }
                for r in results
            ],
        }

        json_file = output_path / f"{project.name}.json"
        with open(json_file, "w") as f:
            json.dump(results_data, f, indent=2, default=str)

        # 6. Show cache summary
        if use_cache and runner.cache_hits > 0:
            _echo(f"\n   ↻ Cache hits: {runner.cache_hits} / {len(results)} tasks ({100 * runner.cache_hits // len(results) if results else 0}%)", "cyan")
        elif use_cache:
            _echo(f"\n   📦 Cache: no hits (all tasks freshly evaluated)", "dim")

        _echo(f"\n📁 Results saved to {json_file}", "bold green")

        if json_output:
            click.echo(json.dumps(results_data, indent=2, default=str))
    finally:
        # Stop the SSE server when the workload finishes
        if sse_server is not None:
            sse_server.stop()
        # Stop and flush the replay writer
        if replay_writer is not None:
            replay_writer.stop()
