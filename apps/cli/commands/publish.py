"""Publish command for modellens CLI.

Publishes benchmark results as a community leaderboard JSON file.
"""

import json
from datetime import datetime
from pathlib import Path

import click

from .utils import _echo


@click.command()
@click.argument("results_dir", type=click.Path(exists=True), default="results")
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output path for leaderboard.json (default: apps/dashboard/public/leaderboard.json)",
)
@click.option(
    "--merge",
    "merge_existing",
    is_flag=True,
    help="Merge with existing published results instead of overwriting",
)
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
    from apps.cli.results_schema import ResultsCollector, merge_results

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
        _echo(
            f"   Mode: merged with existing ({len(existing_models) - len(new_models)} existing preserved)",
            "dim",
        )
    _echo("")
