#!/usr/bin/env python3
"""
Generate the workload results index manifest for the dashboard.

Scans results/workload/ for .json files and produces
public/workload-results.json with aggregated metadata per model/project.

Usage:
    python3 scripts/generate_workload_index.py
    python3 scripts/generate_workload_index.py --results-dir results/workload --output public/workload-results.json
"""

import json
import sys
import argparse
from collections import Counter
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def extract_result_entry(result_file: Path) -> Optional[Dict[str, Any]]:
    """Read a workload result file and produce an index entry."""
    try:
        with open(result_file) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ⚠ Skipping {result_file.name}: {e}", file=sys.stderr)
        return None

    try:
        results = data.get("results", [])

        # Aggregate task-level stats
        task_count = len(results)
        avg_score = data.get("overall_score", 0)
        total_time_ms = sum(r.get("response_time_ms", 0) for r in results)
        all_failures: List[str] = []
        all_strengths: List[str] = []
        task_types: Dict[str, int] = {}

        for r in results:
            all_failures.extend(r.get("failures", []))
            all_strengths.extend(r.get("strengths", []))
            tt = r.get("task_type", "unknown")
            task_types[tt] = task_types.get(tt, 0) + 1

        failure_counts = dict(Counter(all_failures))
        strength_counts = dict(Counter(all_strengths))

        return {
            "model": data.get("model", "unknown"),
            "provider": data.get("provider", "unknown"),
            "project": data.get("project", "unknown"),
            "language": data.get("language", ""),
            "framework": data.get("framework", ""),
            "timestamp": data.get("timestamp", ""),
            "total_tasks": task_count,
            "overall_score": avg_score,
            "total_time_ms": total_time_ms,
            "task_types": task_types,
            "failures": failure_counts,
            "strengths": strength_counts,
        }
    except Exception as e:
        print(f"  ⚠ Error parsing {result_file.name}: {e}", file=sys.stderr)
        return None


def generate_index(results_dir: Path, output_path: Path) -> str:
    """Scan results_dir and write the aggregated manifest to output_path."""
    if not results_dir.exists():
        print(f"  ℹ No workload results directory at {results_dir} — creating empty manifest.")
        entries: List[Dict[str, Any]] = []
    else:
        json_files = sorted(results_dir.glob("*.json"))
        entries = []
        for jf in json_files:
            entry = extract_result_entry(jf)
            if entry is not None:
                entries.append(entry)

    # Sort by timestamp descending (newest first)
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    # Aggregate overall stats
    total_models = len(set(e["model"] for e in entries))
    total_projects = len(set(e["project"] for e in entries))
    total_tasks = sum(e.get("total_tasks", 0) for e in entries)
    avg_scores = [e.get("overall_score", 0) for e in entries if e.get("overall_score", 0) > 0]
    mean_overall = sum(avg_scores) / len(avg_scores) if avg_scores else 0

    manifest = {
        "version": "1.0.0",
        "generated_at": datetime.now().isoformat(),
        "total_entries": len(entries),
        "total_models": total_models,
        "total_projects": total_projects,
        "total_tasks": total_tasks,
        "mean_overall_score": round(mean_overall, 4),
        "entries": entries,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Generate workload results index manifest for the dashboard"
    )
    parser.add_argument(
        "--results-dir",
        default="results/workload",
        help="Directory containing workload JSON result files (default: results/workload)",
    )
    parser.add_argument(
        "--output",
        default="public/workload-results.json",
        help="Output path for the aggregated manifest (default: public/workload-results.json)",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Working directory override (default: auto-detected project root)",
    )
    args = parser.parse_args()

    # Resolve cwd — handle being run from apps/dashboard/ vs project root.
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    if not args.cwd:
        if cwd.name == "dashboard" and (cwd.parent.name == "apps"):
            cwd = cwd.parent.parent
        elif cwd.name == "apps" and (cwd.parent / "packages").exists():
            cwd = cwd.parent

    results_dir = cwd / args.results_dir
    output_path = cwd / args.output

    print(f"🔍 Scanning workload results in {results_dir}")
    output_file = generate_index(results_dir, output_path)
    print(f"✓ Workload results manifest written to {output_file}")


if __name__ == "__main__":
    main()
