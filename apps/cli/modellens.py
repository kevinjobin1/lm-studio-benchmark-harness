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
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import click

# Add packages/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))

from core.hardware import detect_hardware

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


def _resolve_provider(provider: Optional[str] = None) -> tuple:
    """Resolve provider and return (provider_name, api_base, api_key).

    Auto-detects if provider is None: tries LM Studio first, then Ollama.
    """
    if provider is None:
        from providers.ollama import OllamaClient
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
                provider = "lm-studio"
    api_base = "http://localhost:1234/v1" if provider == "lm-studio" else "http://localhost:11434"
    api_key = "lm-studio" if provider == "lm-studio" else "ollama"
    return provider, api_base, api_key


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


def _list_models_detailed(provider: str, api_base: str, api_key: str) -> list:
    """Query provider for model details (name, parameters, quantization, size)."""
    import requests
    models = []
    try:
        if provider == "lm-studio":
            resp = requests.get(f"{api_base}/models", timeout=5)
            if resp.status_code == 200:
                for m in resp.json().get("data", []):
                    models.append({
                        "id": m.get("id", "unknown"),
                        "provider": "lm-studio",
                        "parameters": "unknown",
                        "quantization": "unknown",
                        "size_bytes": 0,
                    })
        elif provider == "ollama":
            ollama_base = api_base.rstrip("/v1").rstrip("/")
            resp = requests.get(f"{ollama_base}/api/tags", timeout=5)
            if resp.status_code == 200:
                for m in resp.json().get("models", []):
                    full_name = m.get("name", "unknown")
                    parts = full_name.split(":")
                    base_name = parts[0]
                    tag = parts[1] if len(parts) > 1 else "latest"
                    details = m.get("details", {})
                    size = m.get("size", 0)
                    models.append({
                        "id": full_name,
                        "name": base_name,
                        "provider": "ollama",
                        "parameters": tag,
                        "quantization": details.get("quantization_level", "unknown"),
                        "size_bytes": size,
                        "family": details.get("family", ""),
                        "format": details.get("format", ""),
                    })
    except Exception:
        pass
    return models


def _fmt_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / (1024 ** 3):.1f} GB"
    elif size_bytes >= 1024 ** 2:
        return f"{size_bytes / (1024 ** 2):.0f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes} B"


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
        provider, detected_base, detected_key = _resolve_provider()
        api_base = api_base or detected_base
        api_key = api_key or detected_key
    else:
        api_base = api_base or ("http://localhost:1234/v1" if provider == "lm-studio" else "http://localhost:11434")
        api_key = api_key or ("lm-studio" if provider == "lm-studio" else "ollama")

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

    # ── Hardware detection ───────────────────────────────────────
    hw = detect_hardware()

    if not ci_mode:
        _echo("")
        _echo("🔬  ModelLens v0.1.0", "bold blue")
        _echo(f"   Provider: {provider}  |  Framework: {framework}  |  git: {sha}", "dim")
        _echo(f"   Hardware: {hw.summary()}", "dim")

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
            hardware=hw,
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
            hardware=hw,
        )

    if not ci_mode:
        _echo(f"\n✓ Results saved to {output_dir}/", "bold green")
        _echo("")


def _run_general_framework(api_base, api_key, models, config, samples,
                           quick, output_dir, verbose, ci_mode, hardware=None):
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

    # Save hardware info alongside results
    if hardware:
        hw_path = Path(output_dir) / "hardware.json"
        hw_path.parent.mkdir(parents=True, exist_ok=True)
        with open(hw_path, "w") as f:
            json.dump(hardware.to_dict(), f, indent=2, default=str)

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
                            quick, output_dir, parallel, seed, ci_mode, json_output,
                            hardware=None):
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

    # Save hardware info alongside results
    if hardware:
        hw_path = Path(output_dir) / "hardware.json"
        hw_path.parent.mkdir(parents=True, exist_ok=True)
        with open(hw_path, "w") as f:
            json.dump(hardware.to_dict(), f, indent=2, default=str)

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

    # ── Hardware ─────────────────────────────────────────────────
    hw = detect_hardware()
    _echo(f"\n🖥  Hardware: {hw.summary()}", "bold")
    _echo(f"   CPU: {hw.cpu_model} ({hw.cpu_cores_physical} phys / {hw.cpu_cores_logical} log)", "dim")
    _echo(f"   RAM: {hw.ram_total_mb / 1024:.0f} GB ({(hw.ram_total_mb - hw.ram_available_mb) / 1024:.1f} GB used)", "dim")
    if hw.gpu_available:
        vram_info = "unified" if hw.unified_memory else f"{hw.gpu_vram_mb:.0f} MB"
        _echo(f"   GPU: {hw.gpu_model} ({vram_info})", "dim")
    if hw.is_apple_silicon:
        _echo(f"   Arch: {hw.architecture} (Apple Silicon, unified memory)", "dim")
    else:
        _echo(f"   Arch: {hw.architecture}", "dim")
    _echo(f"   OS: {hw.os_name} {hw.os_version} (kernel {hw.kernel})", "dim")

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


# ── Models command ────────────────────────────────────────────────────

@cli.command()
@click.option("--api-base", default=None, show_default=False,
              help="Provider base URL (auto-detected for known providers)")
@click.option("--api-key", default=None, show_default=False)
@click.option("--provider", "-p",
              type=click.Choice(["lm-studio", "ollama"]),
              default=None,
              help="Provider to query (auto-detected if omitted)")
@click.option("--json", "json_output", is_flag=True,
              help="Output as JSON")
def models(api_base, api_key, provider, json_output):
    """List available models from the connected provider.

    \\b
    Examples:
      modellens models
      modellens models --provider ollama
      modellens models --json
    """
    # ── Provider resolution ─────────────────────────────────────
    if provider is None:
        provider, detected_base, detected_key = _resolve_provider()
        api_base = api_base or detected_base
        api_key = api_key or detected_key
    else:
        api_base = api_base or ("http://localhost:1234/v1" if provider == "lm-studio" else "http://localhost:11434")
        api_key = api_key or ("lm-studio" if provider == "lm-studio" else "ollama")

    # Validate connection
    try:
        import requests
        check_url = f"{api_base}/models" if provider == "lm-studio" else f"{api_base.rstrip('/v1').rstrip('/')}/v1/models"
        resp = requests.get(check_url, timeout=3)
        if resp.status_code != 200:
            _echo(f"✗ {provider} is not reachable at {check_url}", "red")
            sys.exit(1)
    except Exception:
        _echo(f"✗ {provider} is not reachable", "red")
        sys.exit(1)

    # Fetch model details
    model_list = _list_models_detailed(provider, api_base, api_key)

    if not model_list:
        _echo(f"No models found on {provider}", "yellow")
        return

    if json_output:
        click.echo(json.dumps({
            "provider": provider,
            "count": len(model_list),
            "models": model_list,
        }, indent=2, default=str))
        return

    _echo("")
    _echo(f"🤖 {provider.upper()} Models ({len(model_list)})", "bold blue")

    # LM Studio doesn't expose parameters/quantization/size
    is_lmstudio = provider == "lm-studio"

    if RICH_AVAILABLE:
        table = Table(title=None, show_header=True, header_style="bold")
        table.add_column("Name", style="cyan", no_wrap=True)
        if is_lmstudio:
            table.add_column("Details", style="dim")
        else:
            table.add_column("Params", style="green", justify="right")
            table.add_column("Quantization", style="magenta")
            table.add_column("Size", style="yellow", justify="right")
        for m in model_list:
            if is_lmstudio:
                table.add_row(m.get("id", "unknown"), "—")
            else:
                table.add_row(
                    m.get("id", m.get("name", "unknown")),
                    m.get("parameters", "unknown"),
                    m.get("quantization", "unknown"),
                    _fmt_size(m.get("size_bytes", 0)) if m.get("size_bytes") else "—",
                )
        console.print("")
        console.print(table)
        if is_lmstudio:
            _echo("   ℹ  LM Studio API doesn't expose parameter/quantization details", "dim")
        console.print("")
    else:
        for m in model_list:
            name = m.get("id", m.get("name", "unknown"))
            if is_lmstudio:
                _echo(f"  {name}")
            else:
                params = m.get("parameters", "unknown")
                quant = m.get("quantization", "unknown")
                size = _fmt_size(m.get("size_bytes", 0)) if m.get("size_bytes") else "—"
                _echo(f"  {name:<40} {params:<12} {quant:<14} {size}")
        _echo("")


# ── Publish command ──────────────────────────────────────────────

@cli.command()
@click.argument("results_dir", type=click.Path(exists=True), default="results")
@click.option("--output", "-o", default=None,
              help="Output path for leaderboard.json (default: apps/dashboard/public/leaderboard.json)")
@click.option("--merge", "merge_existing", is_flag=True,
              help="Merge with existing published results instead of overwriting")
def publish(results_dir, output, merge_existing):
    """Publish benchmark results as a community leaderboard JSON file.

    \\b
    Reads results from RESULTS_DIR, aggregates them, and writes
    a leaderboard.json to the dashboard's public/ directory.
    The dashboard reads this file to display community-submitted results.

    Examples:
      modellens publish results/
      modellens publish results/ --merge
      modellens publish results/ --output ~/my-leaderboard.json
    """
    from results_schema import ResultsCollector

    # Resolve output path
    if output is None:
        dashboard_public = Path(__file__).parent.parent / "dashboard" / "public"
        dashboard_public.mkdir(parents=True, exist_ok=True)
        output_path = dashboard_public / "leaderboard.json"
    else:
        output_path = Path(output).expanduser().resolve()

    # Load existing published results if merging
    existing_models: dict = {}
    if merge_existing and output_path.exists():
        try:
            with open(output_path) as f:
                existing = json.load(f)
            for model in existing.get("models", []):
                existing_models[model["model"]] = model
        except Exception:
            pass

    # Load results from results dir
    collector = ResultsCollector(str(Path(results_dir)))
    results = collector.load_all()

    if not results:
        _echo(f"No results found in {results_dir}", "yellow")
        return

    # Build leaderboard entries
    from results_schema import merge_results
    merged = merge_results(results)
    new_models = {m["model"]: m for m in merged.get("leaderboard", [])}

    # Merge with existing if requested
    if merge_existing:
        existing_models.update(new_models)  # Newer results take precedence
        all_models = list(existing_models.values())
    else:
        all_models = list(new_models.values())

    # Sort by overall score
    all_models.sort(key=lambda m: m["metrics"]["overall_score"], reverse=True)

    # Build output
    published = {
        "version": "1.0.0",
        "generated_at": datetime.now().isoformat(),
        "total_models": len(all_models),
        "source": "community",
        "models": all_models,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(published, f, indent=2, default=str)

    _echo("")
    _echo(f"📊 Published {len(all_models)} model(s) to community leaderboard", "bold green")
    _echo(f"   File: {output_path}", "dim")
    if merge_existing:
        _echo(f"   Mode: merged with existing ({len(existing_models) - len(new_models)} existing preserved)", "dim")
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
