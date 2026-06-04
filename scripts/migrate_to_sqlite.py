#!/usr/bin/env python3
"""
Migrate flat-file benchmark results to SQLite.

Reads ``results/runs_index.json`` and individual ``results/*.json`` files and
imports them into ``results/runs.db`` (SQLite) via :class:`ResultsStore`.

Usage:
    python scripts/migrate_to_sqlite.py                  # Full migration
    python scripts/migrate_to_sqlite.py --dry-run        # Preview without writing
    python scripts/migrate_to_sqlite.py --results results_v2  # Custom path
"""

import argparse
import os
import sys

# Ensure packages/ is importable
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PACKAGES_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), "packages")
if _PACKAGES_DIR not in sys.path:
    sys.path.insert(0, _PACKAGES_DIR)

from core.results_store import ResultsStore


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate flat-file benchmark results to SQLite",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview migration without writing to the database",
    )
    parser.add_argument(
        "--results", default="results",
        help="Path to the results directory (default: results)",
    )
    parser.add_argument(
        "--db", default="results/runs.db",
        help="Path to the SQLite database (default: results/runs.db)",
    )
    args = parser.parse_args()

    store = ResultsStore(args.db)

    print(f"Source:      {args.results}/runs_index.json")
    print(f"Destination: {args.db}")
    if args.dry_run:
        print("Mode:        DRY RUN (no writes)")
    print()

    result = store.migrate_from_json(
        results_dir=args.results,
        dry_run=args.dry_run,
    )

    if "message" in result:
        print(f"⚠  {result['message']}")
        store.close()
        return 0 if args.dry_run else 1

    total = result.get("total", 0)
    imported = result.get("imported", 0)
    skipped = result.get("skipped", 0)
    errors = result.get("errors", 0)

    print(f"Total runs in index:  {total}")
    print(f"Imported:             {imported}")
    print(f"Skipped (no run_id):  {skipped}")
    print(f"Errors:               {errors}")

    if errors > 0:
        print()
        print("Errors:")
        for detail in result.get("error_details", []):
            print(f"  • {detail}")

    if not args.dry_run:
        after = store.count()
        print(f"\nRows in database:     {after}")

    store.close()

    if args.dry_run:
        print("\n✓ Dry run complete — no data written.")
        print("  Run without --dry-run to execute the migration.")
    else:
        print("\n✓ Migration complete.")

    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
