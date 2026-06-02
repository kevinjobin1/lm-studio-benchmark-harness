#!/usr/bin/env python3
"""
Generate the trace index manifest for the dashboard.

Scans results/traces/ for trace_*.json files and produces
public/traces/index.json with metadata about each trace.

Usage:
    python3 scripts/generate_traces_index.py
    python3 scripts/generate_traces_index.py --traces-dir results/traces --output public/traces/index.json
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


def extract_index_entry(trace_file: Path) -> Dict[str, Any]:
    """Read a trace file and produce an index entry with key metadata."""
    try:
        with open(trace_file) as f:
            trace = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ⚠ Skipping {trace_file.name}: {e}", file=sys.stderr)
        return None

    try:
        steps = trace.get("steps", [])
        metrics = trace.get("metrics", {})

        return {
            "trace_id": trace.get("trace_id", trace_file.stem),
            "run_id": trace.get("run_id", ""),
            "model": trace.get("model", "unknown"),
            "provider": trace.get("provider", "unknown"),
            "prompt": trace.get("prompt", "")[:200],  # truncated for index
            "timestamp": trace.get("timestamp", ""),
            "totalTimeMs": trace.get("totalTimeMs", 0),
            "status": trace.get("status", "completed"),
            "stepCount": len(steps),
            "tokenCount": metrics.get("total_tokens", 0),
            "ttft_ms": metrics.get("ttft_ms", 0),
        }
    except Exception as e:
        print(f"  ⚠ Error parsing {trace_file.name}: {e}", file=sys.stderr)
        return None


def generate_index(traces_dir: Path, output_path: Path) -> str:
    """Scan traces_dir and write the manifest to output_path."""
    if not traces_dir.exists():
        print(f"  ℹ No traces directory at {traces_dir} — creating empty manifest.")
        traces: List[Dict[str, Any]] = []
    else:
        trace_files = sorted(traces_dir.glob("trace_*.json"))
        traces = []
        for tf in trace_files:
            entry = extract_index_entry(tf)
            if entry is not None:
                traces.append(entry)

    # Sort by timestamp descending (newest first)
    traces.sort(key=lambda t: t.get("timestamp", ""), reverse=True)

    manifest = {
        "version": "1.0.0",
        "generated_at": datetime.now().isoformat(),
        "total_traces": len(traces),
        "traces": traces,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Generate trace index manifest for the dashboard"
    )
    parser.add_argument(
        "--traces-dir",
        default="results/traces",
        help="Directory containing trace JSON files (default: results/traces)",
    )
    parser.add_argument(
        "--output",
        default="public/traces/index.json",
        help="Output path for the index manifest (default: public/traces/index.json)",
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

    traces_dir = cwd / args.traces_dir
    output_path = cwd / args.output

    print(f"🔍 Scanning traces in {traces_dir}")
    output_file = generate_index(traces_dir, output_path)
    print(f"✓ Trace manifest written to {output_file}")


if __name__ == "__main__":
    main()
