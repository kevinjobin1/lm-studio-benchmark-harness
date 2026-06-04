"""Leaderboard command for modellens CLI.

Displays leaderboard from benchmark results.
"""

import json
from pathlib import Path

import click
from rich.table import Table

from .utils import _echo, RICH_AVAILABLE, console


@click.command()
@click.argument("results_dir", type=click.Path(), default="results")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "markdown"]),
    default="table",
)
def leaderboard(results_dir, output_format):
    """Display leaderboard from benchmark results."""
    from apps.cli.results_schema import ResultsCollector, merge_results

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
        click.echo("# Model Lens Benchmark Leaderboard\n")
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
        table = Table(title="🏆 Model Lens Leaderboard")
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
