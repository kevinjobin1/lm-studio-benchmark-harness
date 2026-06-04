"""
Migrate command for Model Lens CLI.

Manages data migration tasks, starting with flat-file → SQLite.

Usage:
    modellens migrate sqlite                  # Run migration
    modellens migrate sqlite --dry-run        # Preview
    modellens migrate sqlite --results path   # Custom results dir
"""

import os
import sys

import click

# Ensure packages/ and apps/ are importable at runtime
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
_PACKAGES_DIR = os.path.join(_PROJECT_ROOT, "packages")
if _PACKAGES_DIR not in sys.path:
    sys.path.insert(0, _PACKAGES_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


@click.group(name="migrate")
def migrate():
    """Data migration and schema management tools."""
    pass


@migrate.command(name="sqlite")
@click.option(
    "--dry-run", is_flag=True,
    help="Preview migration without writing to the database",
)
@click.option(
    "--results", default="results", show_default=True,
    help="Path to the results directory",
)
@click.option(
    "--db", default="results/runs.db", show_default=True,
    help="Path to the SQLite database",
)
def sqlite(dry_run: bool, results: str, db: str):
    """Migrate flat-file benchmark results to SQLite.

    Reads results/runs_index.json and individual JSON result files,
    then imports them into results/runs.db.

    The original JSON files are preserved — this is non-destructive.
    """
    from core.results_store import ResultsStore

    click.echo(f"Source:      {results}/runs_index.json")
    click.echo(f"Destination: {db}")
    if dry_run:
        click.echo("Mode:        DRY RUN (no writes)")
    click.echo()

    store = ResultsStore(db)

    result = store.migrate_from_json(
        results_dir=results,
        dry_run=dry_run,
    )

    if "message" in result:
        click.secho(f"⚠  {result['message']}", fg="yellow")
        store.close()
        return

    total = result.get("total", 0)
    imported = result.get("imported", 0)
    skipped = result.get("skipped", 0)
    errors = result.get("errors", 0)

    click.echo(f"Total runs in index:  {total}")
    click.secho(f"Imported:             {imported}", fg="green")
    if skipped > 0:
        click.secho(f"Skipped (no run_id):  {skipped}", fg="yellow")
    if errors > 0:
        click.secho(f"Errors:               {errors}", fg="red")
    else:
        click.echo(f"Errors:               {errors}")

    if errors > 0:
        click.echo()
        click.echo("Errors:")
        for detail in result.get("error_details", []):
            click.secho(f"  • {detail}", fg="red")

    if not dry_run:
        after = store.count()
        click.echo(f"\nRows in database:     {after}")

    store.close()

    if dry_run:
        click.echo()
        click.secho("✓ Dry run complete — no data written.", fg="green")
        click.echo("  Run without --dry-run to execute the migration.")
    else:
        click.echo()
        click.secho("✓ Migration complete.", fg="green")
