"""Run command for modellens CLI.

Delegates to the general-purpose benchmark harness and the Apple Silicon
DevBench v2 behind a single command.
"""

import json
import sys
from pathlib import Path
from typing import Optional, List

import click
from rich.table import Table

from core.hardware import detect_hardware
from .utils import (
    _echo,
    _get_git_sha,
    PROVIDER_CONFIG,
    _resolve_provider,
    _list_provider_models,
    validate_provider_connection,
    RICH_AVAILABLE,
    console,
)

# ── Event bus infrastructure (graceful fallback if unavailable) ───
try:
    from events import default_bus
    from events.sse import EventBusSSEServer
    from events.replay import EventBusReplayWriter

    _EVENTS_AVAILABLE = True
except ImportError:
    default_bus = None  # type: ignore
    EventBusSSEServer = None  # type: ignore
    EventBusReplayWriter = None  # type: ignore
    _EVENTS_AVAILABLE = False


@click.command()
@click.option(
    "--api-base",
    default=None,
    show_default=False,
    help="Provider base URL (auto-detected for known providers)",
)
@click.option("--api-key", default=None, show_default=False)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["lm-studio", "ollama", "open-webui", "jan", "llama.cpp", "vllm"]),
    default=None,
    show_default=False,
    help="Provider to use (auto-detected if omitted)",
)
@click.option(
    "--models",
    "-m",
    multiple=True,
    help="Models to benchmark (repeatable). Auto-detects if omitted.",
)
@click.option(
    "--model-name", default=None, help="Single model name (alias for --models with one value)"
)
@click.option(
    "--framework",
    "-f",
    type=click.Choice(["devbench", "general", "compare"]),
    default="devbench",
    show_default=True,
    help="Benchmark framework: devbench (TypeScript/React/NestJS), "
    "general (MMLU, GSM8K, HumanEval, etc.), compare (both)",
)
@click.option("--output-dir", "-o", default="results", show_default=True)
@click.option(
    "--num-runs",
    "-n",
    type=int,
    default=5,
    show_default=True,
    help="Runs per prompt for statistical variance (devbench only)",
)
@click.option("--num-prompts", type=int, default=20, show_default=True)
@click.option("--samples", type=int, default=None, help="Samples per benchmark (general framework)")
@click.option("--quick", is_flag=True, help="Quick mode: fewer prompts and runs")
@click.option(
    "--config",
    "-c",
    default=None,
    help="Config file path (unified YAML; devbench settings live under the 'devbench:' section)",
)
@click.option("--parallel/--sequential", default=True, show_default=True)
@click.option("--seed", type=int, default=None)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output: show raw model responses")
@click.option("--ci", "ci_mode", is_flag=True, help="CI-safe headless mode")
@click.option(
    "--traces-dir",
    "traces_dir",
    default="results/traces",
    show_default=True,
    help="Directory for captured execution traces (V2)",
)
@click.option(
    "--no-traces", "no_traces", is_flag=True, help="Disable trace capture for faster benchmark runs"
)
@click.option("--json-output", is_flag=True, help="Output results as JSON to stdout")
@click.option(
    "--sse-port",
    type=int,
    default=None,
    help="Start SSE event bridge on this port for real-time dashboard updates. "
    "0 = auto-select (prints SSE_PORT:N to stdout on start).",
)
def run(
    api_base,
    api_key,
    provider,
    models,
    model_name,
    framework,
    output_dir,
    num_runs,
    num_prompts,
    samples,
    quick,
    config,
    parallel,
    seed,
    verbose,
    ci_mode,
    json_output,
    traces_dir,
    no_traces,
    sse_port,
):
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
        cfg = PROVIDER_CONFIG.get(provider, PROVIDER_CONFIG["lm-studio"])
        api_base = api_base or cfg["url"]
        api_key = api_key or cfg["key"]

    # Validate connection
    validate_provider_connection(provider, api_base)

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
        _echo("🔬  Model Lens v0.1.0", "bold blue")
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
            sse_port=sse_port,
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
            traces_dir=traces_dir,
            no_traces=no_traces,
            config=config,
            sse_port=sse_port,
        )

    if not ci_mode:
        _echo(f"\n✓ Results saved to {output_dir}/", "bold green")
        _echo("")


def _run_general_framework(
    api_base,
    api_key,
    models,
    config,
    samples,
    quick,
    output_dir,
    verbose,
    ci_mode,
    hardware=None,
    sse_port=None,
):
    """Delegate to the general-purpose benchmark.py suite."""
    from core import BenchmarkSuite
    from benchmarks import (
        MMLUProBenchmark,
        GSM8KBenchmark,
        AIMEBenchmark,
        HumanEvalBenchmark,
        SWEBenchLiteBenchmark,
        IFEvalBenchmark,
        NeedleInHaystackBenchmark,
        BFCLBenchmark,
        SpeedLatencyBenchmark,
        MemoryBenchmark,
        CreativityBenchmark,
    )
    from providers.openai_compatible import OpenAICompatibleProvider
    from apps.cli.reporting import ReportGenerator
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

    # ── Set up SSE server and replay writer ───────────────────────
    sse_server = None
    replay_writer = None
    if _EVENTS_AVAILABLE and not ci_mode:
        # Start replay writer (persists all events to disk)
        try:
            replay_dir = str(Path(output_dir) / "replays")
            replay_writer = EventBusReplayWriter(output_dir=replay_dir)
            replay_writer.start()
        except Exception:
            pass

        # Start SSE server if port was requested
        if sse_port is not None and sse_port > 0 and EventBusSSEServer is not None:
            try:
                sse_server = EventBusSSEServer(port=sse_port)
                actual_port = sse_server.start()
                print(f"SSE_PORT:{actual_port}", flush=True)
            except Exception as e:
                print(f"⚠ SSE server failed to start: {e}", flush=True)

    event_source = f"general.{model_name}"
    try:
        client = OpenAICompatibleProvider(
            base_url=api_base,
            api_key=api_key,
            model_name=model_name,
            timeout=cfg.get("api", {}).get("timeout", 120),
            max_retries=cfg.get("api", {}).get("max_retries", 3),
            event_bus=default_bus if _EVENTS_AVAILABLE else None,
            event_source=event_source,
        )
    except Exception as e:
        _echo(f"✗ Failed to connect: {e}", "red")
        _cleanup_event_infra(sse_server, replay_writer)
        sys.exit(1)

    suite = BenchmarkSuite(
        client, cfg, event_bus=default_bus if _EVENTS_AVAILABLE else None, event_source=event_source
    )
    bc = cfg.get("benchmarks", {})

    def _cfg(key):
        c = dict(bc.get(key, {}))
        c["verbose"] = verbose or c.get("verbose", False)
        return c

    # Register all benchmarks
    # Register all benchmarks
    suite.register_benchmark("mmlu_pro", MMLUProBenchmark(client, _cfg("mmlu_pro")))
    suite.register_benchmark("gsm8k", GSM8KBenchmark(client, _cfg("gsm8k")))
    suite.register_benchmark("aime", AIMEBenchmark(client, _cfg("aime")))
    suite.register_benchmark("humaneval", HumanEvalBenchmark(client, _cfg("humaneval")))
    suite.register_benchmark(
        "swe_bench_lite", SWEBenchLiteBenchmark(client, _cfg("swe_bench_lite"))
    )
    suite.register_benchmark("if_eval", IFEvalBenchmark(client, _cfg("ifeval")))
    suite.register_benchmark(
        "needle_in_haystack", NeedleInHaystackBenchmark(client, _cfg("needle_in_haystack"))
    )
    suite.register_benchmark("bfcl", BFCLBenchmark(client, _cfg("bfcl")))
    suite.register_benchmark("speed_latency", SpeedLatencyBenchmark(client, _cfg("speed_latency")))
    suite.register_benchmark("memory", MemoryBenchmark(client, _cfg("memory")))
    suite.register_benchmark("creativity", CreativityBenchmark(client, _cfg("creativity")))

    summary = {}
    try:
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
    finally:
        # ── Clean up SSE + replay (always runs, even on error) ─
        _cleanup_event_infra(sse_server, replay_writer)

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


def _run_devbench_framework(
    api_base,
    api_key,
    models,
    num_runs,
    num_prompts,
    quick,
    output_dir,
    parallel,
    seed,
    ci_mode,
    json_output,
    hardware=None,
    traces_dir="results/traces",
    no_traces=False,
    config=None,
    sse_port=None,
):
    """Delegate to the DevBench v2 Apple Silicon benchmark."""
    import apps.cli.bench_apple_silicon_v2 as devbench
    from apps.cli.prompt_generator import PromptGenerator, GeneratedPrompt, PromptCategory
    from apps.cli.results_schema import (
        ResultsCollector,
        MetricScores,
        PerformanceMetrics,
        RunStats,
    )
    from statistics import mean, stdev
    from collections import Counter
    import yaml

    # ── Load unified config (devbench section) ───────────────────
    devbench_cfg = {}
    config_path = Path(config) if config else Path("apps/cli/config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        devbench_cfg = cfg.get("devbench", {})

    # Override defaults with config values
    num_runs = devbench_cfg.get("evaluation", {}).get("runs_per_prompt", num_runs)
    num_prompts = devbench_cfg.get("prompts", {}).get("total_count", num_prompts)
    parallel = devbench_cfg.get("evaluation", {}).get("parallel_execution", parallel)

    # ── Set up SSE server and replay writer ───────────────────────
    sse_server = None
    replay_writer = None
    if _EVENTS_AVAILABLE and not ci_mode:
        try:
            replay_dir = str(Path(output_dir) / "replays")
            replay_writer = EventBusReplayWriter(output_dir=replay_dir)
            replay_writer.start()
        except Exception:
            pass

        if sse_port is not None and sse_port > 0 and EventBusSSEServer is not None:
            try:
                sse_server = EventBusSSEServer(port=sse_port)
                actual_port = sse_server.start()
                print(f"SSE_PORT:{actual_port}", flush=True)
            except Exception as e:
                print(f"⚠ SSE server failed to start: {e}", flush=True)

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
        api_base=api_base,
        api_key=api_key,
        num_runs=num_runs,
        traces_dir=traces_dir,
        no_traces=no_traces,
        event_bus=default_bus if _EVENTS_AVAILABLE else None,
    )

    try:
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
    finally:
        # ── Clean up SSE + replay (always runs, even on error) ─
        _cleanup_event_infra(sse_server, replay_writer)

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


# ── Event infrastructure lifecycle helpers ────────────────────────


def _cleanup_event_infra(sse_server, replay_writer):
    """Safely stop the SSE server and flush the replay writer."""
    if sse_server is not None:
        try:
            sse_server.stop()
        except (AttributeError, TypeError, OSError):
            pass  # Already stopped or partially initialized
    if replay_writer is not None:
        try:
            replay_writer.stop()
        except (AttributeError, TypeError, OSError):
            pass  # Already stopped or partially initialized
