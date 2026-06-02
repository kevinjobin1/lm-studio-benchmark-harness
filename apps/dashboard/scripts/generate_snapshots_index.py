#!/usr/bin/env python3
"""
Generate the snapshot index manifest for the dashboard.

Scans results/snapshots/ for snapshot JSON files and produces
public/snapshots/index.json with metadata about each snapshot.

Usage:
    python3 scripts/generate_snapshots_index.py
    python3 scripts/generate_snapshots_index.py --snapshots-dir results/snapshots --output public/snapshots/index.json
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def extract_index_entry(snapshot_file: Path) -> Optional[Dict[str, Any]]:
    """Read a snapshot file and produce an index entry with key metadata."""
    try:
        with open(snapshot_file) as f:
            snapshot = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ⚠ Skipping {snapshot_file.name}: {e}", file=sys.stderr)
        return None

    try:
        trace = snapshot.get("trace", {})
        steps = trace.get("steps", [])
        metrics = snapshot.get("metrics", {})

        return {
            "snapshot_id": snapshot.get("snapshot_id", snapshot_file.stem),
            "model": snapshot.get("model", "unknown"),
            "provider": snapshot.get("provider", "unknown"),
            "prompt": snapshot.get("prompt", "")[:200],  # truncated for index
            "pack": snapshot.get("pack", ""),
            "timestamp": snapshot.get("timestamp", ""),
            "totalTimeMs": trace.get("totalTimeMs", 0),
            "tokenCount": metrics.get("total_tokens", 0),
            "stepCount": len(steps),
            "note": snapshot.get("note"),
        }
    except Exception as e:
        print(f"  ⚠ Error parsing {snapshot_file.name}: {e}", file=sys.stderr)
        return None


def generate_index(snapshots_dir: Path, output_path: Path) -> str:
    """Scan snapshots_dir and write the manifest to output_path."""
    if not snapshots_dir.exists():
        print(f"  ℹ No snapshots directory at {snapshots_dir} — creating empty manifest.")
        snapshots: List[Dict[str, Any]] = []
    else:
        snapshot_files = sorted(snapshots_dir.glob("snap-*.json"))
        snapshots = []
        for sf in snapshot_files:
            # Skip the index file itself
            if sf.name == "index.json":
                continue
            entry = extract_index_entry(sf)
            if entry is not None:
                snapshots.append(entry)

    # Sort by timestamp descending (newest first)
    snapshots.sort(key=lambda t: t.get("timestamp", ""), reverse=True)

    manifest = {
        "version": "1.0.0",
        "generated_at": datetime.now().isoformat(),
        "total_snapshots": len(snapshots),
        "snapshots": snapshots,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Generate snapshot index manifest for the dashboard"
    )
    parser.add_argument(
        "--snapshots-dir",
        default="results/snapshots",
        help="Directory containing snapshot JSON files (default: results/snapshots)",
    )
    parser.add_argument(
        "--output",
        default="public/snapshots/index.json",
        help="Output path for the index manifest (default: public/snapshots/index.json)",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Working directory override (default: auto-detected project root)",
    )
    args = parser.parse_args()

    # Resolve cwd — handle being run from apps/dashboard/ vs project root.
    # Only auto-ascend when no explicit --cwd is provided.
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    if not args.cwd:
        if cwd.name == "dashboard" and (cwd.parent.name == "apps"):
            cwd = cwd.parent.parent
        elif cwd.name == "apps" and (cwd.parent / "packages").exists():
            cwd = cwd.parent

    snapshots_dir = cwd / args.snapshots_dir
    output_path = cwd / args.output

    print(f"🔍 Scanning snapshots in {snapshots_dir}")
    output_file = generate_index(snapshots_dir, output_path)
    print(f"✓ Snapshot manifest written to {output_file}")


if __name__ == "__main__":
    main()
