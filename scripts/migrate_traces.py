#!/usr/bin/env python3
"""
Batch trace schema migration — scans ``results/traces/`` and migrates every
trace file to the latest schema version.

Usage:
    python scripts/migrate_traces.py                       # migrate all traces
    python scripts/migrate_traces.py --dry-run             # preview changes only
    python scripts/migrate_traces.py --trace-dir results/traces  # custom dir
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Ensure packages/ is importable
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_PACKAGES_DIR = os.path.join(_PROJECT_ROOT, "packages")
sys.path.insert(0, _PACKAGES_DIR)

from core.trace_schema import migrate_trace, CURRENT_TRACE_VERSION


def migrate_file(path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Migrate a single trace file. Returns {path, version_before, version_after, changed}."""
    with open(path) as f:
        original = json.load(f)

    version_before = original.get("version", "(missing)")

    try:
        migrated = migrate_trace(original)
    except Exception as e:
        return {
            "path": str(path),
            "version_before": version_before,
            "error": str(e),
        }

    version_after = migrated.get("version", "(missing)")
    changed = original != migrated

    if changed and not dry_run:
        with open(path, "w") as f:
            json.dump(migrated, f, indent=2, ensure_ascii=False)

    return {
        "path": str(path),
        "version_before": version_before,
        "version_after": version_after,
        "changed": changed,
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(description="Migrate trace files to the latest schema version")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without writing",
    )
    parser.add_argument(
        "--trace-dir", default="results/traces",
        help="Directory containing trace JSON files (default: results/traces)",
    )
    args = parser.parse_args()

    trace_dir = Path(args.trace_dir)
    if not trace_dir.exists():
        print(f"✗ Trace directory not found: {trace_dir}")
        sys.exit(1)

    trace_files = sorted(trace_dir.glob("*.json"))
    if not trace_files:
        print(f"✓ No trace files found in {trace_dir} — nothing to migrate.")
        return

    print(f"Trace schema migration")
    print(f"  Directory:        {trace_dir}")
    print(f"  Files found:      {len(trace_files)}")
    print(f"  Current version:  {CURRENT_TRACE_VERSION}")
    print(f"  Mode:             {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    results = []
    for tf in trace_files:
        result = migrate_file(tf, dry_run=args.dry_run)
        results.append(result)

        if "error" in result:
            print(f"  ✗ {tf.name}: ERROR — {result['error']}")
        elif result["changed"]:
            print(f"  ↻ {tf.name}: {result['version_before']} → {result['version_after']}{' (dry run)' if args.dry_run else ''}")
        else:
            print(f"  ✓ {tf.name}: {result['version_after']} (up to date)")

    changed = sum(1 for r in results if r.get("changed"))
    errors = sum(1 for r in results if "error" in r)
    unchanged = len(results) - changed - errors

    print()
    print(f"Summary: {unchanged} unchanged, {changed} updated, {errors} errors")

    if args.dry_run and changed:
        print()
        print("  Run without --dry-run to apply these migrations.")


if __name__ == "__main__":
    main()
