#!/usr/bin/env python3
"""
lmbench - LM Studio Benchmark CLI

A single-command benchmark tool for evaluating local LLMs on Apple Silicon.
Supports prompt packs, multiple frameworks, and reproducible results.

Usage:
    lmbench run --models qwen3.5-9b gemma-4
    lmbench run --quick
    lmbench run --packs nestjs-pack react-pack
    lmbench info
    lmbench leaderboard results/
"""

import json
import sys
from pathlib import Path
from typing import Optional, List

import click

# ── Rich terminal output ──────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    console = None
    RICH_AVAILABLE = False


def _echo(message: str, style: str = ""):
    """Print to console (rich-aware)."""
    if RICH_AVAILABLE and style:
        getattr(console, "print", print)(f"[{style}]{message}[/{style}]")
    else:
        print(message)


def _get_git_sha() -> str:
    """Get current git SHA."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _get_git_branch() -> str:
    """Get current git branch."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


# ── CLI Group ─────────────────────────────────────────────────────────

@click.group()
@click.version_option(version="2.0.0", prog_name="lmbench")
def cli():
    """
    🧪 LM Studio Benchmark Harness

    A local-first benchmark framework for evaluating LLMs running
    in LM Studio on Apple Silicon.

    \b
    Quick start:
      lmbench run --quick
      lmbench run --models qwen3.5-9b gemma-4
      lmbench info
      lmbench leaderboard results/
    """
    pass


# ── Run command ───────────────────────────────────────────────────────

@cli.command()
@click.option("--api-base", default="http://localhost:1234/v1",
              help="LM Studio API base URL", show_default=True)
@click.option("--api-key", default="lm-studio",
              help="API key", show_default=True)
@click.option("--models", "-m", multiple=True,
              help="Models to benchmark (repeatable). Auto-detects if omitted.")
@click.option("--config", "-c", default=None,
              help="Configuration file path (config.json or config.yaml)")
@click.option("--packs", "-p", multiple=True,
              help="Prompt packs to use (repeatable). Uses all if omitted.")
@click.option("--framework", "-f",
              type=click.Choice(["devbench", "general", "compare"]),
              default="devbench",
              help="Benchmark framework to use", show_default=True)
@click.option("--output-dir", "-o", default="results",
              help="Output directory", show_default=True)
@click.option("--num-runs", "-n", type=int, default=5,
              help="Runs per prompt for statistical variance", show_default=True)
@click.option("--num-prompts", type=int, default=20,
              help="Total prompts to generate", show_default=True)
@click.option("--quick", is_flag=True,
              help="Quick mode: fewer prompts and runs")
@click.option("--parallel/--sequential", default=True,
              help="Enable/disable parallel execution", show_default=True)
@click.option("--seed", type=int, default=None,
              help="Random seed for reproducibility")
@click.option("--ci", "ci_mode", is_flag=True,
              help="CI-safe headless mode (no interactive output)")
@click.option("--json-output", is_flag=True,
              help="Output results as JSON to stdout (for CI piping)")
def run(api_base, api_key, models, config, packs, framework, output_dir,
        num_runs, num_prompts, quick, parallel, seed, ci_mode, json_output):
    """
    Run benchmarks against LM Studio models.

    \b
    Examples:
      lmbench run --quick
      lmbench run --models qwen3.5-9b gemma-4 --num-runs 5
      lmbench run --packs nestjs-pack react-pack --seed 42
      lmbench run --framework general --config config.yaml
      lmbench run --ci --json-output > results.json
    """
    if quick:
        num_runs = 3
        num_prompts = 10

    # ── Gather system info ─────────────────────────────────────────
    sha = _get_git_sha()
    branch = _get_git_branch()

    if not ci_mode:
        _echo("", "")
        _echo("🧪  LM Studio Benchmark Harness v2.0.0", "bold blue")
        _echo(f"   Git: {branch}@{sha}", "dim")
        _echo(f"   API: {api_base}", "dim")
        _echo(f"   Framework: {framework}", "dim")
        _echo(f"   Runs/prompt: {num_runs} | Prompts: {num_prompts}", "dim")
        if seed:
            _echo(f"   Seed: {seed}", "dim")
        _echo("", "")

    # ── Load prompt packs ──────────────────────────────────────────
    packs_available = []
    try:
        from prompt_packs import PackLoader
        pack_loader = PackLoader()

        if packs:
            packs_available = list(packs)
        else:
            packs_available = pack_loader.list_packs()

        if packs_available and not ci_mode:
            _echo(f"📦 Using prompt packs: {', '.join(packs_available)}", "cyan")
    except ImportError:
        if packs and not ci_mode:
            _echo("⚠️  Prompt packs not available (install prompt_packs)", "yellow")

    # ── Detect models ───────────────────────────────────────────────
    if not models:
        if not ci_mode:
            _echo("🔍 Auto-detecting LM Studio models...", "cyan")
        try:
            import bench_apple_silicon_v2 as devbench
            detector = devbench.LMStudioModelDetector()
            detected = detector.detect_models()
            if detected:
                models = tuple(m["name"] for m in detected)
                if not ci_mode:
                    _echo(f"✓ Found {len(models)} model(s): {', '.join(models)}", "green")
            else:
                _echo("✗ No models detected. Specify with --models", "red")
                sys.exit(1)
        except Exception as e:
            if not ci_mode:
                _echo(f"✗ Auto-detection failed: {e}", "red")
                _echo("  Please specify models with --models", "yellow")
            sys.exit(1)

    # ── Generate prompts from packs ─────────────────────────────────
    prompts = []
    if packs_available:
        if not ci_mode:
            _echo(f"📝 Generating {num_prompts} prompts from packs...", "cyan")
        try:
            prompt_texts = pack_loader.generate_from_packs(
                pack_names=packs_available,
                total_prompts=num_prompts,
                seed=seed
            )
            # Convert to GeneratedPrompt objects for DevBench
            from prompt_generator import GeneratedPrompt, PromptCategory
            for text in prompt_texts:
                prompts.append(GeneratedPrompt(
                    category=PromptCategory.CODE,
                    prompt=text,
                    expected_keywords=[],
                    difficulty="medium"
                ))
        except Exception as e:
            if not ci_mode:
                _echo(f"⚠️  Prompt generation failed: {e}", "yellow")
                _echo("  Falling back to default prompt generator", "yellow")

    # ── Run benchmarks ──────────────────────────────────────────────
    if not ci_mode:
        _echo(f"\n🚀 Running benchmarks for {len(models)} model(s)...", "bold cyan")
        _echo(f"   {num_prompts} prompts × {num_runs} runs = {num_prompts * num_runs} total evaluations\n", "dim")

    all_results = []

    for model_name in models:
        if not ci_mode:
            _echo(f"\n━━━ {model_name} ━━━", "bold")

        # Use the DevBench v2 runner
        try:
            import bench_apple_silicon_v2 as devbench
            benchmark = devbench.AppleSiliconBenchmarkV2(
                api_base=api_base,
                api_key=api_key,
                num_runs=num_runs
            )

            # Use generated prompts or default generator
            if not prompts:
                prompts = benchmark.prompt_generator.generate_default_batch(total_prompts=num_prompts)

            model_results = benchmark.benchmark_model(
                model_name,
                prompts,
                parallel=parallel
            )

            all_results.extend(model_results)

            if not ci_mode and model_results:
                from statistics import mean
                avg_score = mean([r.developer_score for r in model_results])
                avg_tps = mean([r.tokens_per_second_mean for r in model_results])
                _echo(f"  ✓ DevScore: {avg_score:.3f} | tok/s: {avg_tps:.1f}", "green")

        except Exception as e:
            if not ci_mode:
                _echo(f"  ✗ Failed: {e}", "red")
            continue

    # ── Save results ────────────────────────────────────────────────
    from results_schema import (
        ResultsCollector, MetricScores, PerformanceMetrics,
        RunStats, FailureBreakdown
    )
    from statistics import mean, stdev
    import statistics as stats_module

    collector = ResultsCollector(output_dir)

    for model_name in models:
        model_results = [r for r in all_results if r.model == model_name]
        if not model_results:
            continue

        scores = [r.developer_score for r in model_results]
        tps_values = [r.tokens_per_second_mean for r in model_results]
        ttft_values = [r.ttft_mean for r in model_results]

        metrics = MetricScores(
            overall_score=mean(scores) if scores else 0.0,
        )

        performance = PerformanceMetrics(
            tokens_per_sec=mean(tps_values) if tps_values else 0.0,
            ttft_ms=mean(ttft_values) * 1000 if ttft_values else 0.0,
        )

        run_stats = RunStats(
            mean=mean(scores) if scores else 0.0,
            std=stdev(scores) if len(scores) > 1 else 0.0,
            min=min(scores) if scores else 0.0,
            max=max(scores) if scores else 0.0,
            median=stats_module.median(scores) if scores else 0.0,
            runs=num_runs,
        )

        result = collector.create_result(
            model=model_name,
            metrics=metrics,
            performance=performance,
            stats=run_stats,
            model_metadata={},
            packs_used=packs_available,
            seed=seed,
        )
        collector.add_result(result)

    saved = collector.save_all()

    # ── Output ───────────────────────────────────────────────────────
    if json_output:
        import json as json_mod
        aggregated = collector._aggregate()
        click.echo(json_mod.dumps(aggregated, indent=2, default=str))
    elif not ci_mode:
        _echo(f"\n✓ Results saved to {output_dir}/", "bold green")
        for key, path in saved.items():
            _echo(f"  • {key}: {path}", "dim")

        # Print summary table
        if RICH_AVAILABLE:
            table = Table(title="📊 Benchmark Summary")
            table.add_column("Model", style="cyan")
            table.add_column("Score", style="green")
            table.add_column("tok/s", style="magenta")
            table.add_column("TTFT", style="yellow")
            table.add_column("Runs", style="dim")

            for result in collector.results:
                table.add_row(
                    result.model,
                    f"{result.metrics.overall_score:.3f}",
                    f"{result.performance.tokens_per_sec:.1f}",
                    f"{result.performance.ttft_ms:.0f}ms",
                    str(result.stats.runs),
                )

            console.print("")
            console.print(table)

    _echo("", "")


# ── Info command ──────────────────────────────────────────────────────

@cli.command()
def info():
    """
    Show information about available models, packs, and system.

    \b
    Examples:
      lmbench info
    """
    _echo("", "")
    _echo("🧪  LM Studio Benchmark Harness", "bold blue")
    _echo(f"   Version: 2.0.0", "dim")

    sha = _get_git_sha()
    if sha:
        _echo(f"   Git SHA: {sha}", "dim")

    # System info
    from results_schema import ResultsCollector
    hw = ResultsCollector.gather_system_info()
    _echo(f"\n💻 System:", "bold")
    _echo(f"   Platform: {hw.platform}", "dim")
    _echo(f"   Processor: {hw.processor}", "dim")
    _echo(f"   Memory: {hw.memory_gb}GB", "dim")
    _echo(f"   Architecture: {hw.architecture}", "dim")

    # Available packs
    try:
        from prompt_packs import PackLoader
        loader = PackLoader()

        _echo(f"\n📦 Prompt Packs ({len(loader.packs)} available):", "bold")
        for info_data in loader.get_pack_info():
            _echo(f"   {info_data['name']} v{info_data['version']} — {info_data['description']}", "dim")
            _echo(f"     Tags: {', '.join(info_data['tags'])} | Prompts: {info_data['total_prompts']}", "dim")
    except ImportError:
        _echo("\n📦 Prompt Packs: Not available", "yellow")

    # Try to detect LM Studio models
    try:
        import bench_apple_silicon_v2 as devbench
        detector = devbench.LMStudioModelDetector()
        detected = detector.detect_models()

        if detected:
            _echo(f"\n🤖 LM Studio Models ({len(detected)} detected):", "bold")
            for m in detected:
                _echo(f"   {m['name']}", "dim")
                if m.get("quantization", "unknown") != "unknown":
                    _echo(f"     Quantization: {m['quantization']} | Size: {m.get('size', 'unknown')}", "dim")
        else:
            _echo("\n🤖 LM Studio Models: None detected", "yellow")
    except Exception:
        _echo("\n🤖 LM Studio Models: Could not detect", "yellow")

    _echo("", "")


# ── Leaderboard command ───────────────────────────────────────────────

@cli.command()
@click.argument("results_dir", type=click.Path(exists=True), default="results")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["table", "json", "markdown"]),
              default="table", help="Output format")
def leaderboard(results_dir, output_format):
    """
    Display leaderboard from benchmark results.

    \b
    Arguments:
      RESULTS_DIR  Path to results directory (default: results/)

    \b
    Examples:
      lmbench leaderboard
      lmbench leaderboard results/ --format markdown
      lmbench leaderboard devbench_results/ --format json
    """
    from results_schema import ResultsCollector, merge_results

    results_dir_path = Path(results_dir)
    collector = ResultsCollector(str(results_dir_path))
    results = collector.load_all()

    if not results:
        _echo(f"No results found in {results_dir}", "yellow")
        return

    merged = merge_results(results)
    models = merged.get("leaderboard", [])

    if output_format == "json":
        click.echo(json.dumps(merged, indent=2, default=str))
        return

    if output_format == "markdown":
        click.echo("# 🍎 LM Studio Benchmark Leaderboard\n")
        click.echo(f"Generated: {merged['generated_at']}\n")
        click.echo("| Rank | Model | Overall | Coding | Reasoning | tok/s | TTFT | Failures |")
        click.echo("|------|-------|---------|--------|-----------|-------|------|----------|")
        for i, m in enumerate(models, 1):
            click.echo(
                f"| {i} | {m['model']} | "
                f"{m['metrics']['overall_score']:.3f} | "
                f"{m['metrics'].get('coding_score', 0):.3f} | "
                f"{m['metrics'].get('reasoning_score', 0):.3f} | "
                f"{m['performance']['tokens_per_sec']:.1f} | "
                f"{m['performance']['ttft_ms']:.0f}ms | "
                f"{m['total_failures']} |"
            )
        return

    # Rich table (default)
    if RICH_AVAILABLE:
        table = Table(title="🏆 Benchmark Leaderboard")
        table.add_column("Rank", style="dim", justify="right")
        table.add_column("Model", style="cyan")
        table.add_column("Overall", style="bold green", justify="right")
        table.add_column("Coding", justify="right")
        table.add_column("Reasoning", justify="right")
        table.add_column("tok/s", style="magenta", justify="right")
        table.add_column("TTFT", style="yellow", justify="right")
        table.add_column("Failures", style="red", justify="right")

        for i, m in enumerate(models, 1):
            rank_style = "bold yellow" if i == 1 else "dim"
            table.add_row(
                f"[{rank_style}]{i}[/{rank_style}]",
                m["model"],
                f"{m['metrics']['overall_score']:.3f}",
                f"{m['metrics'].get('coding_score', 0):.3f}",
                f"{m['metrics'].get('reasoning_score', 0):.3f}",
                f"{m['performance']['tokens_per_sec']:.1f}",
                f"{m['performance']['ttft_ms']:.0f}ms",
                str(m["total_failures"]),
            )

        console.print("")
        console.print(table)
        console.print("")
    else:
        # Fallback to simple print
        for i, m in enumerate(models, 1):
            click.echo(f"{i}. {m['model']} — Overall: {m['metrics']['overall_score']:.3f}, "
                       f"tok/s: {m['performance']['tokens_per_sec']:.1f}")

    click.echo("")


# ── Packs command ────────────────────────────────────────────────────

@cli.command()
def packs():
    """
    List available prompt packs.

    \b
    Examples:
      lmbench packs
    """
    try:
        from prompt_packs import PackLoader
        loader = PackLoader()

        if RICH_AVAILABLE:
            table = Table(title="📦 Available Prompt Packs")
            table.add_column("Name", style="cyan")
            table.add_column("Version", style="dim")
            table.add_column("Description")
            table.add_column("Prompts", justify="right")
            table.add_column("Tags")

            for info_data in loader.get_pack_info():
                table.add_row(
                    info_data["name"],
                    info_data["version"],
                    info_data["description"][:60],
                    str(info_data["total_prompts"]),
                    ", ".join(info_data["tags"]),
                )

            console.print("")
            console.print(table)
            console.print("")
        else:
            for info_data in loader.get_pack_info():
                click.echo(f"  {info_data['name']} v{info_data['version']}: {info_data['description']}")
    except ImportError:
        _echo("Prompt packs not available", "yellow")


# ── Pack management commands ─────────────────────────────────────────

@cli.group()
def pack():
    """
    Manage benchmark packs (scaffold, install, validate, etc.)

    \b
    Examples:
      lmbench pack scaffold my-react-pack
      lmbench pack install ./community-packs/cool-pack
      lmbench pack list
      lmbench pack validate nestjs-pack
    """
    pass


@pack.command()
@click.argument("name")
@click.option("--description", "-d", default="", help="Pack description")
@click.option("--author", "-a", default="", help="Author name")
@click.option("--tags", "-t", multiple=True, help="Tags (repeatable)")
def scaffold(name, description, author, tags):
    """Scaffold a new benchmark pack from template."""
    from skill_pack_sdk import PackSDK
    sdk = PackSDK()
    sdk.scaffold(name, description, author, list(tags) if tags else None)


@pack.command()
@click.argument("path")
@click.option("--force", is_flag=True, help="Force overwrite existing installation")
def install(path, force):
    """Install a pack from a local path."""
    from skill_pack_sdk import PackSDK
    sdk = PackSDK()
    try:
        sdk.install(path, force=force)
    except Exception as e:
        _echo(f"✗ Install failed: {e}", "red")


@pack.command()
@click.argument("name")
def uninstall(name):
    """Uninstall a pack by name."""
    from skill_pack_sdk import PackSDK
    sdk = PackSDK()
    sdk.uninstall(name)


@pack.command()
@click.argument("name", required=False)
def validate(name):
    """Validate a pack (or all packs if no name given)."""
    from skill_pack_sdk import PackSDK
    sdk = PackSDK()
    if name:
        sdk.validate(name)
    else:
        sdk.validate_all()


@pack.command("list")
def pack_list():
    """List installed packs."""
    from skill_pack_sdk import PackSDK
    sdk = PackSDK()
    sdk.list_packs()


@pack.command()
@click.argument("name")
def info(name):
    """Show details about an installed pack."""
    from skill_pack_sdk import PackSDK
    sdk = PackSDK()
    sdk.info(name)


# ── Entry point ───────────────────────────────────────────────────────

def main():
    """Entry point for the lmbench CLI."""
    cli()


if __name__ == "__main__":
    main()
