#!/usr/bin/env python3
"""
ModelLens — Observe. Compare. Understand.

Unified CLI for local AI model benchmarking and observability.
Wraps the general-purpose benchmark harness (benchmark.py) and
the Apple Silicon DevBench v2 (bench_apple_silicon_v2.py) behind a single command.

Usage:
    modellens run --quick
    modellens run --models qwen3.5-9b gemma-4
    modellens run --framework general --model-name my-model
    modellens info
    modellens leaderboard results/
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional, List

import click

# Add packages/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))

# ── Rich terminal output ──────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
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
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _list_provider_models(provider: str, api_base: str, api_key: str) -> List[str]:
    """Query provider for available model names via lightweight HTTP GET."""
    import requests
    try:
        if provider == "lm-studio":
            resp = requests.get(f"{api_base}/models", timeout=5)
            if resp.status_code == 200:
                return [m.get("id", "") for m in resp.json().get("data", [])]
        elif provider == "ollama":
            ollama_base = api_base.rstrip("/v1").rstrip("/")
            resp = requests.get(f"{ollama_base}/api/tags", timeout=5)
            if resp.status_code == 200:
                return [m.get("name", "") for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


# ── CLI Group ─────────────────────────────────────────────────────────

@click.group()
@click.version_option(version="0.1.0", prog_name="modellens")
def cli():
    """
    🔬 ModelLens — Observe. Compare. Understand.

    A local-first observability and evaluation platform for local AI models.
    """
    pass


# ── Run command ───────────────────────────────────────────────────────

@cli.command()
@click.option("--api-base", default=None, show_default=False,
              help="Provider base URL (auto-detected for known providers)")
@click.option("--api-key", default=None, show_default=False)
@click.option("--provider", "-p",
              type=click.Choice(["lm-studio", "ollama"]),
              default=None, show_default=False,
              help="Provider to use (auto-detected if omitted)")
@click.option("--models", "-m", multiple=True,
              help="Models to benchmark (repeatable). Auto-detects if omitted.")
@click.option("--model-name", default=None,
              help="Single model name (alias for --models with one value)")
@click.option("--framework", "-f",
              type=click.Choice(["devbench", "general", "compare"]),
              default="devbench", show_default=True,
              help="Benchmark framework: devbench (TypeScript/React/NestJS), "
                   "general (MMLU, GSM8K, HumanEval, etc.), compare (both)")
@click.option("--output-dir", "-o", default="results", show_default=True)
@click.option("--num-runs", "-n", type=int, default=5, show_default=True,
              help="Runs per prompt for statistical variance (devbench only)")
@click.option("--num-prompts", type=int, default=20, show_default=True)
@click.option("--samples", type=int, default=None,
              help="Samples per benchmark (general framework)")
@click.option("--quick", is_flag=True,
              help="Quick mode: fewer prompts and runs")
@click.option("--config", "-c", default=None,
              help="Config file path (YAML for general, JSON for devbench)")
@click.option("--parallel/--sequential", default=True, show_default=True)
@click.option("--seed", type=int, default=None)
@click.option("--verbose", "-v", is_flag=True,
              help="Verbose output: show raw model responses")
@click.option("--ci", "ci_mode", is_flag=True,
              help="CI-safe headless mode")
@click.option("--json-output", is_flag=True,
              help="Output results as JSON to stdout")
def run(api_base, api_key, provider, models, model_name, framework, output_dir,
        num_runs, num_prompts, samples, quick, config, parallel, seed,
        verbose, ci_mode, json_output):
    """
    Run benchmarks against local models.

    \\b
    Examples:
      modellens run --quick
      modellens run --provider ollama --models llama3.2
      modellens run --framework general --model-name my-model --samples 50
      modellens run --framework compare --models model-a model-b
      modellens run --ci --json-output > results.json
    """
    # Normalize model names
    if model_name and not models:
        models = (model_name,)

    # ── Provider resolution ─────────────────────────────────────
    if provider is None:
        # Auto-detect: try LM Studio first, then Ollama
        from providers.ollama import OllamaClient
        # Quick check: try LM Studio
        try:
            import requests
            lm_resp = requests.get("http://localhost:1234/v1/models", timeout=2)
            if lm_resp.status_code == 200 and len(lm_resp.json().get("data", [])) > 0:
                provider = "lm-studio"
        except Exception:
            pass
        if not provider:
            ollama = OllamaClient()
            if ollama.health_check():
                provider = "ollama"
            else:
                provider = "lm-studio"  # fallback default
        api_base = api_base or ("http://localhost:1234/v1" if provider == "lm-studio" else "http://localhost:11434")
        api_key = api_key or ("lm-studio" if provider == "lm-studio" else "ollama")
    else:
        if provider == "lm-studio":
            api_base = api_base or "http://localhost:1234/v1"
            api_key = api_key or "lm-studio"
        elif provider == "ollama":
            api_base = api_base or "http://localhost:11434"
            api_key = api_key or "ollama"

    # Validate connection
    try:
        import requests
        if provider == "lm-studio":
            check_url = "http://localhost:1234/v1/models"
            other_url = "http://localhost:11434/v1/models"
        else:
            check_url = "http://localhost:11434/v1/models"
            other_url = "http://localhost:1234/v1/models"
        resp = requests.get(check_url, timeout=3)
        if resp.status_code != 200:
            _echo(f"✗ {provider} is not running or unreachable at {check_url}", "red")
            _echo(f"  Is {provider} running? Try {other_url} for the other provider.", "dim")
            sys.exit(1)
    except Exception:
        if provider:
            url = "localhost:1234" if provider == "lm-studio" else "localhost:11434"
            _echo(f"✗ {provider} is not running at {url}.", "red")
            _echo(f"  Start {provider} and retry, or switch providers.", "dim")
        else:
            _echo(f"✗ Neither LM Studio (localhost:1234) nor Ollama (localhost:11434) is reachable.", "red")
            _echo(f"  Start one and retry with --provider lm-studio or --provider ollama", "dim")
        sys.exit(1)

    # ── Validate model names against provider ──────────────────────
    if models:
        try:
            available = _list_provider_models(provider, api_base, api_key)
            if available:
                for m in models:
                    if m not in available:
                        _echo(f"⚠  Model '{m}' not found on {provider}.", "yellow")
                        _echo(f"   Available: {', '.join(available[:8])}", "dim")
                        if len(available) > 8:
                            _echo(f"   ... and {len(available) - 8} more", "dim")
        except Exception:
            pass  # Soft validation — don't block on listing failure

    if quick:
        num_runs = 3
        num_prompts = 10
        samples = samples or 10

    sha = _get_git_sha()

    if not ci_mode:
        _echo("")
        _echo("🔬  ModelLens v0.1.0", "bold blue")
        _echo(f"   Provider: {provider}  |  Framework: {framework}  |  git: {sha}", "dim")

    # ── Framework dispatch ─────────────────────────────────────────

    if framework in ("general", "compare"):
        _run_general_framework(
            api_base=api_base,
            api_key=api_key,
            models=models,
            config=config or "apps/cli/config.yaml",
            samples=samples,
            quick=quick,
            output_dir=output_dir,
            verbose=verbose,
            ci_mode=ci_mode,
        )

    if framework in ("devbench", "compare"):
        _run_devbench_framework(
            api_base=api_base,
            api_key=api_key,
            models=models,
            num_runs=num_runs,
            num_prompts=num_prompts,
            quick=quick,
            output_dir=output_dir,
            parallel=parallel,
            seed=seed,
            ci_mode=ci_mode,
            json_output=json_output,
        )

    if not ci_mode:
        _echo(f"\n✓ Results saved to {output_dir}/", "bold green")
        _echo("")


def _run_general_framework(api_base, api_key, models, config, samples,
                           quick, output_dir, verbose, ci_mode):
    """Delegate to the general-purpose benchmark.py suite."""
    from core import BenchmarkSuite, LMStudioClient
    from benchmarks import (
        MMLUProBenchmark, GSM8KBenchmark, AIMEBenchmark,
        HumanEvalBenchmark, SWEBenchLiteBenchmark, IFEvalBenchmark,
        NeedleInHaystackBenchmark, BFCLBenchmark, SpeedLatencyBenchmark,
        MemoryBenchmark, CreativityBenchmark,
    )
    from reporting import ReportGenerator
    import yaml

    if not models:
        _echo("✗ --models or --model-name required for general framework", "red")
        sys.exit(1)

    model_name = models[0]
    sample_count = samples or (10 if quick else 100)

    # Load config
    cfg = {}
    config_path = Path(config)
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}

    cfg.setdefault("api", {})["base_url"] = api_base
    cfg.setdefault("api", {})["api_key"] = api_key
    cfg.setdefault("api", {})["model_name"] = model_name
    if verbose:
        cfg.setdefault("benchmarks", {})["verbose"] = True

    if not ci_mode:
        _echo(f"   Model: {model_name}  |  Samples: {sample_count}", "dim")

    try:
        client = LMStudioClient(
            base_url=api_base,
            api_key=api_key,
            model_name=model_name,
            timeout=cfg.get("api", {}).get("timeout", 120),
            max_retries=cfg.get("api", {}).get("max_retries", 3),
        )
    except Exception as e:
        _echo(f"✗ Failed to connect: {e}", "red")
        sys.exit(1)

    suite = BenchmarkSuite(client, cfg)
    bc = cfg.get("benchmarks", {})

    def _cfg(key):
        c = dict(bc.get(key, {}))
        c["verbose"] = verbose or c.get("verbose", False)
        return c

    # Register all benchmarks
    suite.register_benchmark("mmlu_pro", MMLUProBenchmark(client, _cfg("mmlu_pro")))
    suite.register_benchmark("gsm8k", GSM8KBenchmark(client, _cfg("gsm8k")))
    suite.register_benchmark("aime", AIMEBenchmark(client, _cfg("aime")))
    suite.register_benchmark("humaneval", HumanEvalBenchmark(client, _cfg("humaneval")))
    suite.register_benchmark("swe_bench_lite", SWEBenchLiteBenchmark(client, _cfg("swe_bench_lite")))
    suite.register_benchmark("if_eval", IFEvalBenchmark(client, _cfg("ifeval")))
    suite.register_benchmark("needle_in_haystack", NeedleInHaystackBenchmark(client, _cfg("needle_in_haystack")))
    suite.register_benchmark("bfcl", BFCLBenchmark(client, _cfg("bfcl")))
    suite.register_benchmark("speed_latency", SpeedLatencyBenchmark(client, _cfg("speed_latency")))
    suite.register_benchmark("memory", MemoryBenchmark(client, _cfg("memory")))
    suite.register_benchmark("creativity", CreativityBenchmark(client, _cfg("creativity")))

    results = suite.run_all(samples=sample_count)
    summary = suite.get_summary()

    report_gen = ReportGenerator(output_dir)
    report_gen.generate_all(summary, suite.all_results)

    if not ci_mode and RICH_AVAILABLE:
        table = Table(title=f"General Benchmark: {model_name}")
        table.add_column("Benchmark", style="cyan")
        table.add_column("Score", style="green")
        for name, data in summary.get("benchmarks", {}).items():
            for metric_name, metric_data in data.get("metrics", {}).items():
                score = metric_data.get("mean", 0)
                score_str = f"{score:.2%}" if "tokens" not in metric_name else f"{score:.2f}"
                table.add_row(f"{name}/{metric_name}", score_str)
        console.print("")
        console.print(table)


def _run_devbench_framework(api_base, api_key, models, num_runs, num_prompts,
                            quick, output_dir, parallel, seed, ci_mode, json_output):
    """Delegate to the DevBench v2 Apple Silicon benchmark."""
    import bench_apple_silicon_v2 as devbench
    from prompt_generator import PromptGenerator, GeneratedPrompt, PromptCategory
    from results_schema import (
        ResultsCollector, MetricScores, PerformanceMetrics, RunStats,
    )
    from statistics import mean, stdev
    import statistics as stats_module
    from collections import Counter

    # Detect models if not specified
    if not models:
        if not ci_mode:
            _echo("🔍 Auto-detecting LM Studio models...", "cyan")
        detector = devbench.LMStudioModelDetector()
        detected = detector.detect_models()
        if not detected:
            _echo("✗ No models detected. Specify with --models", "red")
            sys.exit(1)
        models = tuple(m["name"] for m in detected)
        if not ci_mode:
            _echo(f"✓ Found {len(models)} model(s): {', '.join(models)}", "green")

    pg = PromptGenerator()
    prompts = pg.generate_default_batch(total_prompts=num_prompts)

    if not ci_mode:
        _echo(f"   Models: {', '.join(models)}", "dim")
        _echo(f"   {num_prompts} prompts × {num_runs} runs = {num_prompts * num_runs} total", "dim")
        cat_counts = Counter([p.category.value for p in prompts])
        _echo(f"   Categories: {', '.join(f'{c}({n})' for c, n in cat_counts.items())}", "dim")

    all_results = []
    benchmark = devbench.AppleSiliconBenchmarkV2(
        api_base=api_base, api_key=api_key, num_runs=num_runs,
    )

    for model_name in models:
        if not ci_mode:
            _echo(f"\n━━━ {model_name} ━━━", "bold")
        model_results = benchmark.benchmark_model(model_name, prompts, parallel=parallel)
        all_results.extend(model_results)
        if not ci_mode and model_results:
            avg_score = mean([r.developer_score for r in model_results])
            avg_tps = mean([r.tokens_per_second_mean for r in model_results])
            _echo(f"  ✓ DevScore: {avg_score:.3f}  |  tok/s: {avg_tps:.1f}", "green")

    # Save results
    collector = ResultsCollector(output_dir)
    for model_name in models:
        model_results = [r for r in all_results if r.model == model_name]
        if not model_results:
            continue
        scores = [r.developer_score for r in model_results]
        tps_vals = [r.tokens_per_second_mean for r in model_results]
        ttft_vals = [r.ttft_mean for r in model_results]

        result = collector.create_result(
            model=model_name,
            metrics=MetricScores(overall_score=mean(scores) if scores else 0.0),
            performance=PerformanceMetrics(
                tokens_per_sec=mean(tps_vals) if tps_vals else 0.0,
                ttft_ms=mean(ttft_vals) * 1000 if ttft_vals else 0.0,
            ),
            stats=RunStats(
                mean=mean(scores) if scores else 0.0,
                std=stdev(scores) if len(scores) > 1 else 0.0,
                runs=num_runs,
            ),
            seed=seed,
        )
        collector.add_result(result)

    saved = collector.save_all()

    if json_output:
        aggregated = collector._aggregate()
        click.echo(json.dumps(aggregated, indent=2, default=str))
    elif not ci_mode and RICH_AVAILABLE:
        table = Table(title="DevBench Summary")
        table.add_column("Model", style="cyan")
        table.add_column("DevScore", style="green", justify="right")
        table.add_column("tok/s", style="magenta", justify="right")
        table.add_column("TTFT", style="yellow", justify="right")
        for r in collector.results:
            table.add_row(
                r.model,
                f"{r.metrics.overall_score:.3f}",
                f"{r.performance.tokens_per_sec:.1f}",
                f"{r.performance.ttft_ms:.0f}ms",
            )
        console.print("")
        console.print(table)


# ── Info command ──────────────────────────────────────────────────────

@cli.command()
def info():
    """Show system info, available models, and prompt packs."""
    _echo("")
    _echo("🔬  ModelLens v0.1.0", "bold blue")
    _echo(f"   git: {_get_git_sha()}", "dim")

    try:
        import bench_apple_silicon_v2 as devbench
        detector = devbench.LMStudioModelDetector()
        detected = detector.detect_models()
        if detected:
            _echo(f"\n🤖 LM Studio Models ({len(detected)}):", "bold")
            for m in detected:
                _echo(f"   {m['name']}", "dim")
        else:
            _echo("\n🤖 LM Studio Models: None detected", "yellow")
    except Exception:
        _echo("\n🤖 LM Studio Models: Could not detect", "yellow")

    _echo("")


# ── Leaderboard command ───────────────────────────────────────────────

@cli.command()
@click.argument("results_dir", type=click.Path(exists=True), default="results")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["table", "json", "markdown"]), default="table")
def leaderboard(results_dir, output_format):
    """Display leaderboard from benchmark results."""
    from results_schema import ResultsCollector, merge_results

    collector = ResultsCollector(str(Path(results_dir)))
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
        click.echo("# ModelLens Benchmark Leaderboard\n")
        click.echo("| Rank | Model | Overall | tok/s | TTFT |")
        click.echo("|------|-------|---------|-------|------|")
        for i, m in enumerate(models, 1):
            click.echo(
                f"| {i} | {m['model']} | "
                f"{m['metrics']['overall_score']:.3f} | "
                f"{m['performance']['tokens_per_sec']:.1f} | "
                f"{m['performance']['ttft_ms']:.0f}ms |"
            )
        return

    if RICH_AVAILABLE:
        table = Table(title="🏆 ModelLens Leaderboard")
        table.add_column("Rank", style="dim", justify="right")
        table.add_column("Model", style="cyan")
        table.add_column("Overall", style="bold green", justify="right")
        table.add_column("tok/s", style="magenta", justify="right")
        table.add_column("TTFT", style="yellow", justify="right")
        for i, m in enumerate(models, 1):
            table.add_row(
                str(i),
                m["model"],
                f"{m['metrics']['overall_score']:.3f}",
                f"{m['performance']['tokens_per_sec']:.1f}",
                f"{m['performance']['ttft_ms']:.0f}ms",
            )
        console.print("")
        console.print(table)
        console.print("")


# ── Entry point ───────────────────────────────────────────────────────

def main():
    cli()


if __name__ == "__main__":
    main()
