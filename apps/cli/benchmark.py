#!/usr/bin/env python3
"""
LM Studio Benchmark Harness - Single Command Benchmark Suite

A comprehensive benchmark suite for evaluating LM Studio's OpenAI-compatible API
across dimensions that matter on X/Twitter.

Supports three evaluation modes:
- Custom: Built-in custom benchmarks
- LM Eval: Industry-standard EleutherAI framework
- OpenBench: Groq's provider-agnostic evaluation infrastructure
- Compare: Run both LM Eval and OpenBench for side-by-side comparison

Usage:
    python benchmark.py --api-base http://localhost:1234/v1 --model-name your-model
    python benchmark.py --framework lm-eval --api-base http://localhost:1234/v1 --model-name your-model
    python benchmark.py --framework openbench --api-base http://localhost:1234/v1 --model-name your-model
    python benchmark.py --framework compare --api-base http://localhost:1234/v1 --model-name your-model
"""

import os, sys
# Add packages/ to path so 'from core/benchmarks/providers' resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))

import click
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from core import BenchmarkSuite, LMStudioClient
from benchmarks import (
    MMLUProBenchmark, GSM8KBenchmark, AIMEBenchmark,
    HumanEvalBenchmark, SWEBenchLiteBenchmark, IFEvalBenchmark,
    NeedleInHaystackBenchmark, BFCLBenchmark, SpeedLatencyBenchmark,
    MemoryBenchmark, CreativityBenchmark
)
from reporting import ReportGenerator
from providers import run_lm_eval_benchmarks, run_openbench_benchmarks

console = Console()


def load_config(config_file: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    config_path = Path(config_file)
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}


def create_benchmark_suite(client, config: dict) -> BenchmarkSuite:
    """Create and configure the benchmark suite."""
    suite = BenchmarkSuite(client, config)
    benchmark_config = config.get("benchmarks", {})
    verbose = benchmark_config.get("verbose", False)
    
    def _cfg(key: str) -> dict:
        """Get sub-config with verbose flag injected."""
        c = dict(benchmark_config.get(key, {}))
        c["verbose"] = verbose or c.get("verbose", False)
        return c
    
    # Register benchmarks
    if benchmark_config.get("mmlu_pro", {}).get("enabled", True):
        suite.register_benchmark("mmlu_pro", MMLUProBenchmark(client, _cfg("mmlu_pro")))
    
    if benchmark_config.get("gsm8k", {}).get("enabled", True):
        suite.register_benchmark("gsm8k", GSM8KBenchmark(client, _cfg("gsm8k")))
    
    if benchmark_config.get("aime", {}).get("enabled", True):
        suite.register_benchmark("aime", AIMEBenchmark(client, _cfg("aime")))
    
    if benchmark_config.get("humaneval", {}).get("enabled", True):
        suite.register_benchmark("humaneval", HumanEvalBenchmark(client, _cfg("humaneval")))
    
    if benchmark_config.get("swe_bench_lite", {}).get("enabled", True):
        suite.register_benchmark("swe_bench_lite", SWEBenchLiteBenchmark(client, _cfg("swe_bench_lite")))
    
    if benchmark_config.get("ifeval", {}).get("enabled", True):
        suite.register_benchmark("if_eval", IFEvalBenchmark(client, _cfg("ifeval")))
    
    if benchmark_config.get("needle_in_haystack", {}).get("enabled", True):
        suite.register_benchmark("needle_in_haystack", NeedleInHaystackBenchmark(client, _cfg("needle_in_haystack")))
    
    if benchmark_config.get("bfcl", {}).get("enabled", True):
        suite.register_benchmark("bfcl", BFCLBenchmark(client, _cfg("bfcl")))
    
    if benchmark_config.get("speed_latency", {}).get("enabled", True):
        suite.register_benchmark("speed_latency", SpeedLatencyBenchmark(client, _cfg("speed_latency")))
    
    if benchmark_config.get("memory", {}).get("enabled", True):
        suite.register_benchmark("memory", MemoryBenchmark(client, _cfg("memory")))
    
    if benchmark_config.get("creativity", {}).get("enabled", True):
        suite.register_benchmark("creativity", CreativityBenchmark(client, _cfg("creativity")))
    
    return suite


@click.command()
@click.option('--api-base', default='http://localhost:1234/v1', help='LM Studio API base URL')
@click.option('--api-key', default='lm-studio', help='API key (default: lm-studio)')
@click.option('--model-name', required=True, help='Model name to benchmark')
@click.option('--config', default='apps/cli/config.yaml', help='Configuration file path')
@click.option('--benchmarks', multiple=True, help='Specific benchmarks to run (default: all)')
@click.option('--samples', type=int, help='Number of samples per benchmark')
@click.option('--quick', is_flag=True, help='Quick mode with fewer samples')
@click.option('--output-dir', default='results', help='Output directory for results')
@click.option('--framework', type=click.Choice(['custom', 'lm-eval', 'openbench', 'compare', 'agentic']), default='custom', help='Evaluation framework to use')
@click.option('--install-openbench', is_flag=True, help='Install OpenBench if not present')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging: show raw model responses and parser traces')
def main(api_base, api_key, model_name, config, benchmarks, samples, quick, output_dir, framework, install_openbench, verbose):
    """Run LM Studio benchmark suite."""
    
    console.print("\n[bold blue]🚀 LM Studio Benchmark Harness[/bold blue]\n")
    
    # Load configuration
    cfg = load_config(config)
    
    # Override config with CLI options
    if api_base:
        cfg.setdefault("api", {})["base_url"] = api_base
    if api_key:
        cfg.setdefault("api", {})["api_key"] = api_key
    if model_name:
        cfg.setdefault("api", {})["model_name"] = model_name
    if samples:
        cfg.setdefault("benchmarks", {})["samples_per_benchmark"] = samples
    if quick:
        samples = cfg.get("benchmarks", {}).get("quick_mode_samples", 10)
    if verbose:
        cfg.setdefault("benchmarks", {})["verbose"] = True
    
    # Get sample count
    sample_count = samples or cfg.get("benchmarks", {}).get("samples_per_benchmark", 100)
    
    # Get API config
    api_config = cfg.get("api", {})
    base_url = api_config.get("base_url", api_base)
    api_key_val = api_config.get("api_key", api_key)
    model_name_val = api_config.get("model_name", model_name)
    
    console.print(f"[bold]Framework:[/bold] {framework}")
    console.print(f"[bold]API Base:[/bold] {base_url}")
    console.print(f"[bold]Model:[/bold] {model_name_val}\n")
    
    # Run based on framework selection
    if framework == "custom":
        run_custom_framework(console, base_url, api_key_val, model_name_val, cfg, benchmarks, sample_count, output_dir)
    elif framework == "lm-eval":
        run_lm_eval_framework(console, base_url, api_key_val, model_name_val, benchmarks, sample_count, output_dir)
    elif framework == "openbench":
        run_openbench_framework(console, base_url, model_name_val, benchmarks, sample_count, output_dir, install_openbench)
    elif framework == "compare":
        run_comparison_mode(console, base_url, api_key_val, model_name_val, cfg, benchmarks, sample_count, output_dir, install_openbench)
    elif framework == "agentic":
        run_agentic_framework(console, model_name_val, sample_count, output_dir)


def run_custom_framework(console, base_url, api_key, model_name, cfg, benchmarks, sample_count, output_dir):
    """Run custom benchmark framework."""
    console.print(f"[dim]Connecting to {base_url}...[/dim]")
    
    try:
        client = LMStudioClient(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=cfg.get("api", {}).get("timeout", 120),
            max_retries=cfg.get("api", {}).get("max_retries", 3)
        )
        console.print("[green]✓ Connected to API[/green]\n")
    except Exception as e:
        console.print(f"[red]✗ Failed to connect: {e}[/red]")
        return
    
    # Create benchmark suite
    suite = create_benchmark_suite(client, cfg)
    
    # Determine which benchmarks to run
    if benchmarks:
        benchmark_list = list(benchmarks)
    else:
        benchmark_list = list(suite.benchmarks.keys())
    
    console.print(f"[bold]Benchmarks to run:[/bold] {', '.join(benchmark_list)}")
    console.print(f"[bold]Samples per benchmark:[/bold] {sample_count}\n")
    
    # Run benchmarks
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Running benchmarks...", total=None)
        
        try:
            results = suite.run_all(
                samples=sample_count,
                benchmark_names=benchmark_list if benchmarks else None
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Benchmark interrupted by user[/yellow]")
            return
        except Exception as e:
            console.print(f"\n[red]Error running benchmarks: {e}[/red]")
            return
    
    # Generate summary
    console.print("\n[bold blue]📊 Generating Results[/bold blue]\n")
    summary = suite.get_summary()
    
    # Display summary table
    table = Table(title="Custom Benchmark Results")
    table.add_column("Benchmark", style="cyan")
    table.add_column("Metric", style="magenta")
    table.add_column("Score", style="green")
    
    for benchmark_name, benchmark_data in summary.get("benchmarks", {}).items():
        for metric_name, metric_data in benchmark_data.get("metrics", {}).items():
            score = metric_data.get("mean", 0)
            if "tokens" in metric_name or "ttft" in metric_name:
                score_str = f"{score:.2f}"
            else:
                score_str = f"{score:.2%}"
            table.add_row(benchmark_name, metric_name, score_str)
    
    console.print(table)
    
    # Generate reports
    console.print("\n[bold blue]💾 Saving Reports[/bold blue]\n")
    report_gen = ReportGenerator(output_dir)
    report_files = report_gen.generate_all(summary, suite.all_results)
    
    console.print("[green]✓ Reports generated:[/green]")
    for format_name, file_path in report_files.items():
        console.print(f"  • {format_name.upper()}: {file_path}")
    
    console.print(f"\n[bold green]✓ Custom benchmark complete![/bold green]\n")


def run_lm_eval_framework(console, base_url, api_key, model_name, benchmarks, sample_count, output_dir):
    """Run LM Eval framework."""
    console.print(f"[dim]Running LM Eval framework...[/dim]\n")
    
    # Determine which benchmarks to run
    if benchmarks:
        benchmark_list = list(benchmarks)
    else:
        # Default to LM Eval supported benchmarks
        benchmark_list = ["mmlu_pro", "gsm8k", "aime", "humaneval", "if_eval"]
    
    console.print(f"[bold]Benchmarks to run:[/bold] {', '.join(benchmark_list)}")
    console.print(f"[bold]Limit:[/bold] {sample_count}\n")
    
    try:
        results = run_lm_eval_benchmarks(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            benchmark_names=benchmark_list,
            limit=sample_count
        )
        
        console.print("\n[bold blue]📊 LM Eval Results[/bold blue]\n")
        
        if "error" in results.get("lm_eval", {}):
            console.print(f"[red]Error: {results['lm_eval']['error']}[/red]")
        else:
            # Display results
            table = Table(title="LM Eval Results")
            table.add_column("Task", style="cyan")
            table.add_column("Metric", style="magenta")
            table.add_column("Score", style="green")
            
            lm_eval_results = results.get("lm_eval", {})
            if "results" in lm_eval_results:
                for task, task_results in lm_eval_results["results"].items():
                    for metric, value in task_results.items():
                        if isinstance(value, (int, float)):
                            table.add_row(task, metric, f"{value:.4f}")
            
            console.print(table)
        
        # Save results
        report_gen = ReportGenerator(output_dir)
        import json
        output_file = report_gen.run_dir / "lm_eval_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        console.print(f"\n[green]✓ LM Eval results saved to: {output_file}[/green]")
        console.print(f"\n[bold green]✓ LM Eval benchmark complete![/bold green]\n")
        
    except Exception as e:
        console.print(f"\n[red]Error running LM Eval: {e}[/red]")
        console.print("[yellow]Note: Make sure lm-eval is installed: pip install lm-eval[/yellow]\n")


def run_openbench_framework(console, base_url, model_name, benchmarks, sample_count, output_dir, install_if_missing):
    """Run OpenBench framework."""
    console.print(f"[dim]Running OpenBench framework...[/dim]\n")
    
    # Determine which benchmarks to run
    if benchmarks:
        benchmark_list = list(benchmarks)
    else:
        # Default to OpenBench supported benchmarks
        benchmark_list = ["mmlu_pro", "gsm8k", "aime", "humaneval"]
    
    console.print(f"[bold]Benchmarks to run:[/bold] {', '.join(benchmark_list)}")
    console.print(f"[bold]Limit:[/bold] {sample_count}\n")
    
    try:
        results = run_openbench_benchmarks(
            base_url=base_url,
            model_name=model_name,
            benchmark_names=benchmark_list,
            limit=sample_count,
            install_if_missing=install_if_missing
        )
        
        console.print("\n[bold blue]📊 OpenBench Results[/bold blue]\n")
        
        if "error" in results:
            console.print(f"[red]Error: {results['error']}[/red]")
        else:
            # Display results
            table = Table(title="OpenBench Results")
            table.add_column("Benchmark", style="cyan")
            table.add_column("Status", style="magenta")
            table.add_column("Details", style="green")
            
            for benchmark, result in results.get("openbench", {}).items():
                if result.get("success", False):
                    table.add_row(benchmark, "✓ Success", str(result.get("raw_output", "")[:50]))
                else:
                    table.add_row(benchmark, "✗ Failed", str(result.get("error", ""))[:50])
            
            console.print(table)
        
        # Save results
        report_gen = ReportGenerator(output_dir)
        import json
        output_file = report_gen.run_dir / "openbench_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        console.print(f"\n[green]✓ OpenBench results saved to: {output_file}[/green]")
        console.print(f"\n[bold green]✓ OpenBench benchmark complete![/bold green]\n")
        
    except Exception as e:
        console.print(f"\n[red]Error running OpenBench: {e}[/red]")
        console.print("[yellow]Note: Make sure OpenBench is installed: uv pip install openbench[/yellow]\n")


def run_comparison_mode(console, base_url, api_key, model_name, cfg, benchmarks, sample_count, output_dir, install_openbench):
    """Run comparison mode between LM Eval and OpenBench."""
    console.print(f"[bold yellow]🔄 Comparison Mode: LM Eval vs OpenBench[/bold yellow]\n")
    
    # Determine which benchmarks to run (intersection of both frameworks)
    if benchmarks:
        benchmark_list = list(benchmarks)
    else:
        # Default to benchmarks supported by both
        benchmark_list = ["mmlu_pro", "gsm8k", "humaneval"]
    
    console.print(f"[bold]Benchmarks to compare:[/bold] {', '.join(benchmark_list)}")
    console.print(f"[bold]Limit:[/bold] {sample_count}\n")
    
    comparison_results = {
        "lm_eval": {},
        "openbench": {},
        "custom": {}
    }
    
    # Run LM Eval
    console.print("[bold cyan]Running LM Eval...[/bold cyan]")
    try:
        lm_eval_results = run_lm_eval_benchmarks(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            benchmark_names=benchmark_list,
            limit=sample_count
        )
        comparison_results["lm_eval"] = lm_eval_results
        console.print("[green]✓ LM Eval complete[/green]\n")
    except Exception as e:
        console.print(f"[yellow]LM Eval failed: {e}[/yellow]\n")
        comparison_results["lm_eval"]["error"] = str(e)
    
    # Run OpenBench
    console.print("[bold cyan]Running OpenBench...[/bold cyan]")
    try:
        openbench_results = run_openbench_benchmarks(
            base_url=base_url,
            model_name=model_name,
            benchmark_names=benchmark_list,
            limit=sample_count,
            install_if_missing=install_openbench
        )
        comparison_results["openbench"] = openbench_results
        console.print("[green]✓ OpenBench complete[/green]\n")
    except Exception as e:
        console.print(f"[yellow]OpenBench failed: {e}[/yellow]\n")
        comparison_results["openbench"]["error"] = str(e)
    
    # Run custom benchmarks for comparison
    console.print("[bold cyan]Running Custom Benchmarks...[/bold cyan]")
    try:
        client = LMStudioClient(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=cfg.get("api", {}).get("timeout", 120),
            max_retries=cfg.get("api", {}).get("max_retries", 3)
        )
        
        suite = create_benchmark_suite(client, cfg)
        custom_results = suite.run_all(
            samples=sample_count,
            benchmark_names=benchmark_list
        )
        comparison_results["custom"] = suite.get_summary()
        console.print("[green]✓ Custom benchmarks complete[/green]\n")
    except Exception as e:
        console.print(f"[yellow]Custom benchmarks failed: {e}[/yellow]\n")
        comparison_results["custom"]["error"] = str(e)
    
    # Display comparison table
    console.print("\n[bold blue]📊 Comparison Results[/bold blue]\n")
    
    table = Table(title="Framework Comparison")
    table.add_column("Benchmark", style="cyan")
    table.add_column("LM Eval", style="magenta")
    table.add_column("OpenBench", style="green")
    table.add_column("Custom", style="yellow")
    
    for benchmark in benchmark_list:
        lm_eval_score = "N/A"
        openbench_score = "N/A"
        custom_score = "N/A"
        
        # Extract LM Eval score
        lm_eval_data = comparison_results.get("lm_eval", {}).get("lm_eval", {}).get("results", {})
        if benchmark in LM_EVAL_TASK_MAPPING:
            task_name = LM_EVAL_TASK_MAPPING[benchmark]
            if task_name in lm_eval_data:
                # Get first metric
                metrics = lm_eval_data[task_name]
                if metrics:
                    first_metric = list(metrics.values())[0]
                    lm_eval_score = f"{first_metric:.2%}" if isinstance(first_metric, float) else str(first_metric)
        
        # Extract OpenBench score
        openbench_data = comparison_results.get("openbench", {}).get("openbench", {})
        if benchmark in OPENBENCH_TASK_MAPPING:
            task_name = OPENBENCH_TASK_MAPPING[benchmark]
            if task_name in openbench_data:
                if openbench_data[task_name].get("success"):
                    openbench_score = "✓"
                else:
                    openbench_score = "✗"
        
        # Extract Custom score
        custom_data = comparison_results.get("custom", {}).get("benchmarks", {})
        if benchmark in custom_data:
            metrics = custom_data[benchmark].get("metrics", {})
            if metrics:
                first_metric = list(metrics.values())[0]
                custom_score = f"{first_metric.get('mean', 0):.2%}"
        
        table.add_row(benchmark, lm_eval_score, openbench_score, custom_score)
    
    console.print(table)
    
    # Save comparison results
    report_gen = ReportGenerator(output_dir)
    import json
    output_file = report_gen.run_dir / "comparison_results.json"
    with open(output_file, 'w') as f:
        json.dump(comparison_results, f, indent=2, default=str)
    
    # Generate comparison report
    comparison_report = report_gen.generate_comparison_report(comparison_results)
    
    console.print(f"\n[green]✓ Comparison results saved to: {output_file}[/green]")
    console.print(f"[green]✓ Comparison report saved to: {comparison_report}[/green]")
    console.print(f"\n[bold green]✓ Comparison complete![/bold green]\n")


def run_agentic_framework(console, model_name, sample_count, output_dir):
    """Run agentic/tool-use benchmark framework."""
    console.print("\n[bold blue]🧠 Agentic Skills Benchmark Mode[/bold blue]\n")
    console.print("[dim]Evaluating tool selection, planning, and constraint adherence...[/dim]\n")

    try:
        from skills.agentic_benchmark import run_agentic_benchmark_sync

        console.print(f"[bold]Model:[/bold] {model_name}")
        console.print(f"[bold]Prompts:[/bold] {sample_count or 5}")
        console.print(f"[bold]Runs per prompt:[/bold] 3\n")

        summary = run_agentic_benchmark_sync(
            model_name=model_name,
            num_prompts=sample_count or 5,
            runs_per_prompt=3,
            verbose=True,
        )

        console.print("\n[bold blue]📊 Agentic Benchmark Results[/bold blue]\n")

        table = Table(title=f"Agentic Score: {model_name}")
        table.add_column("Metric", style="cyan")
        table.add_column("Score", style="green")
        table.add_column("Details", style="dim")

        table.add_row(
            "Overall Agentic Score",
            f"{summary.overall_agentic_score:.1%}",
            f"{summary.total_prompts} prompts × {summary.total_runs // max(summary.total_prompts, 1)} runs",
        )
        table.add_row("Validity", f"{summary.mean_validity:.1%}", "JSON + schema + skill existence")
        table.add_row("Planning", f"{summary.mean_planning:.1%}", "Correct sequence, minimal steps")
        table.add_row("Skill Correctness", f"{summary.mean_skill_correctness:.1%}", "Correct tool + correct params")
        table.add_row("Constraint Adherence", f"{summary.mean_constraint_adherence:.1%}", "No hallucinations")
        table.add_row("Hallucination Rate", f"{summary.hallucination_rate:.1%}", "Invalid tool usage")

        console.print(table)

        if summary.lockfile_errors:
            console.print("\n[yellow]⚠️  Lockfile errors detected:[/yellow]")
            for err in summary.lockfile_errors:
                console.print(f"  [dim]{err}[/dim]")

        # Save results
        from results_schema import ResultsCollector, MetricScores, PerformanceMetrics, RunStats, AgenticScoreData
        collector = ResultsCollector(output_dir)

        agentic_data = AgenticScoreData(
            overall_agentic_score=summary.overall_agentic_score,
            validity_score=summary.mean_validity,
            planning_score=summary.mean_planning,
            skill_correctness_score=summary.mean_skill_correctness,
            constraint_adherence_score=summary.mean_constraint_adherence,
            hallucination_rate=summary.hallucination_rate,
        )

        result = collector.create_result(
            model=model_name,
            metrics=MetricScores(overall_score=summary.overall_agentic_score),
            performance=PerformanceMetrics(),
            stats=RunStats(mean=summary.overall_agentic_score, runs=summary.total_runs),
            prompt_version="agentic-v1",
        )
        result.agentic_score = agentic_data
        result.agentic_mode = True

        collector.add_result(result)
        paths = collector.save_all()

        console.print(f"\n[green]✓ Agentic benchmark results saved to: {paths.get('aggregated', output_dir)}[/green]")
        console.print(f"\n[bold green]✓ Agentic benchmark complete![/bold green]\n")

    except ImportError as e:
        console.print(f"[red]Error: Agentic skills system not available: {e}[/red]")
        console.print("[yellow]Make sure skills/ package is properly installed.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error running agentic benchmark: {e}[/red]")


if __name__ == "__main__":
    main()
