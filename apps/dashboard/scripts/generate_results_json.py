#!/usr/bin/env python3
"""
Generate dashboard/public/results.json from benchmark results in ./results/ directory.

Reads all benchmark result JSON files and aggregates them into a single results.json
that the Astro dashboard consumes at runtime.

Usage:
    python3 dashboard/scripts/generate_results_json.py [--results-dir ./results] [--output dashboard/public/results.json]
    python3 dashboard/scripts/generate_results_json.py --demo  # generate demo data
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def find_result_files(results_dir: Path) -> list[Path]:
    """Find all result JSON files in the results directory tree."""
    result_files = []
    if not results_dir.exists():
        return result_files
    
    for path in results_dir.rglob("*.json"):
        # Skip manifest files and non-result JSONs
        if path.name in ("manifest.json", "config_snapshot.json", "lockfile.json"):
            continue
        result_files.append(path)
    
    result_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return result_files


def load_result_file(path: Path) -> dict[str, Any] | None:
    """Load a single result JSON file. Returns None if invalid."""
    try:
        with open(path) as f:
            data = json.load(f)
        # Handle both single-result and multi-result files
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return None
    except (json.JSONDecodeError, OSError) as e:
        print(f"  Skipping {path}: {e}", file=sys.stderr)
        return None


def _get_first(obj: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Get the first key from obj that exists and is not None."""
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    """Safely convert to float, returning default on failure."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    """Safely convert to int, returning default on failure."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def normalize_result(raw: dict[str, Any], source_file: str) -> dict[str, Any] | None:
    """Normalize a raw result dict into the dashboard's BenchmarkResult shape."""
    try:
        # Extract model name
        model = _get_first(raw, "model_name", "model", default="unknown")
        
        # Extract metadata
        metadata = _get_first(raw, "model_metadata", "metadata", default={})
        if not isinstance(metadata, dict):
            metadata = {"raw": str(metadata)}
        
        # Extract hardware
        hw = _get_first(raw, "hardware", default={})
        if not isinstance(hw, dict):
            hw = {"processor": "Unknown", "memory_gb": 0, "platform": "Unknown", "architecture": "Unknown"}
        
        hardware = {
            "platform": str(hw.get("platform", "macOS")),
            "processor": str(hw.get("processor", "Apple Silicon")),
            "memory_gb": _safe_float(hw.get("memory_gb", hw.get("memory", 0))),
            "architecture": str(hw.get("architecture", "arm64")),
        }
        
        # Extract metrics - try multiple possible shapes
        metrics_raw = _get_first(raw, "metrics", "scores", default={})
        if isinstance(metrics_raw, (int, float)):
            # Single score case
            metrics_raw = {"overall_score": float(metrics_raw)}
        
        metrics = {
            "coding_score": _safe_float(_get_first(metrics_raw, "coding_score", "coding")),
            "reasoning_score": _safe_float(_get_first(metrics_raw, "reasoning_score", "reasoning")),
            "instruction_score": _safe_float(_get_first(metrics_raw, "instruction_score", "instruction", "instructions")),
            "frontend_score": _safe_float(_get_first(metrics_raw, "frontend_score", "frontend")),
            "math_score": _safe_float(_get_first(metrics_raw, "math_score", "math")),
            "debugging_score": _safe_float(_get_first(metrics_raw, "debugging_score", "debugging")),
            "overall_score": _safe_float(_get_first(metrics_raw, "overall_score", "overall", "accuracy")),
        }
        
        # Extract performance
        perf_raw = _get_first(raw, "performance", "speed", default={})
        performance = {
            "tokens_per_sec": _safe_float(_get_first(perf_raw, "tokens_per_sec", "tokens_per_second")),
            "normalized_tps": _safe_float(_get_first(perf_raw, "normalized_tps", default=_safe_float(_get_first(perf_raw, "tokens_per_sec")) * 0.95)),
            "ttft_ms": _safe_float(_get_first(perf_raw, "ttft_ms", "ttft", "time_to_first_token")),
            "total_latency_ms": _safe_float(_get_first(perf_raw, "total_latency_ms", "total_time", "latency")),
            "memory_pressure_mb": _safe_float(_get_first(perf_raw, "memory_pressure_mb", "memory_mb", "ram_usage_mb")),
        }
        
        # Extract stats
        stats_raw = _get_first(raw, "stats", "statistics", default={})
        stats = {
            "mean": _safe_float(_get_first(stats_raw, "mean", default=metrics["overall_score"])),
            "std": _safe_float(_get_first(stats_raw, "std", "std_dev", default=0.05)),
            "min": _safe_float(stats_raw.get("min", 0)),
            "max": _safe_float(stats_raw.get("max", 0)),
            "median": _safe_float(_get_first(stats_raw, "median", default=metrics["overall_score"])),
            "runs": _safe_int(_get_first(stats_raw, "runs", "samples", default=1)),
            "confidence_95": stats_raw.get("confidence_95", None),
            "coefficient_of_variation": _safe_float(_get_first(stats_raw, "coefficient_of_variation", "cv", default=0.1)),
        }
        
        # Extract failures
        failures_raw = _get_first(raw, "failures", "errors", default={})
        failures = {
            "hallucinated_api": int(failures_raw.get("hallucinated_api", 0)),
            "wrong_async_usage": int(failures_raw.get("wrong_async_usage", 0)),
            "incorrect_json_schema": int(failures_raw.get("incorrect_json_schema", 0)),
            "syntax_error": int(failures_raw.get("syntax_error", 0)),
            "logic_error": int(failures_raw.get("logic_error", 0)),
            "type_error": int(failures_raw.get("type_error", 0)),
            "missing_import": int(failures_raw.get("missing_import", 0)),
            "stale_closure": int(failures_raw.get("stale_closure", 0)),
            "race_condition": int(failures_raw.get("race_condition", 0)),
            "incorrect_di": int(failures_raw.get("incorrect_di", 0)),
            "oververbose": int(failures_raw.get("oververbose", 0)),
            "missed_constraint": int(failures_raw.get("missed_constraint", 0)),
            "other": int(failures_raw.get("other", 0)),
        }
        
        category_scores = raw.get("category_scores", raw.get("breakdown", {}))
        if not isinstance(category_scores, dict):
            category_scores = {}
        
        return {
            "run_id": raw.get("run_id", source_file),
            "model": model,
            "model_metadata": metadata,
            "hardware": hardware,
            "timestamp": raw.get("timestamp", datetime.now().isoformat()),
            "git_sha": raw.get("git_sha", raw.get("git_commit", "")),
            "git_branch": raw.get("git_branch", raw.get("branch", "main")),
            "metrics": metrics,
            "performance": performance,
            "stats": stats,
            "failures": failures,
            "category_scores": category_scores,
            "config_snapshot": raw.get("config", raw.get("config_snapshot", {})),
            "prompt_version": raw.get("prompt_version", "v1"),
            "packs_used": raw.get("packs_used", raw.get("packs", [])),
            "seed": raw.get("seed", None),
        }
    except Exception as e:
        print(f"  Failed to normalize result from {source_file}: {e}", file=sys.stderr)
        return None


def generate_demo_data() -> dict[str, Any]:
    """Generate demo benchmark results for development."""
    models = [
        {"name": "qwopus3.5-9b-coder", "coding": 0.82, "reasoning": 0.78, "instruction": 0.90, "tps": 72, "ttft": 420},
        {"name": "gemma-4-e4b", "coding": 0.76, "reasoning": 0.80, "instruction": 0.94, "tps": 65, "ttft": 340},
        {"name": "lfm2.5-8b-a1b", "coding": 0.80, "reasoning": 0.85, "instruction": 0.88, "tps": 58, "ttft": 510},
        {"name": "llama-3.1-8b", "coding": 0.71, "reasoning": 0.74, "instruction": 0.82, "tps": 55, "ttft": 380},
        {"name": "mistral-7b-v0.3", "coding": 0.68, "reasoning": 0.72, "instruction": 0.78, "tps": 48, "ttft": 450},
    ]
    
    failure_templates = [
        {"hallucinated_api": 3, "wrong_async_usage": 2, "incorrect_json_schema": 1, "syntax_error": 0, "logic_error": 4, "type_error": 2, "missing_import": 1, "stale_closure": 1, "race_condition": 2, "incorrect_di": 0, "oververbose": 1, "missed_constraint": 0, "other": 0},
        {"hallucinated_api": 1, "wrong_async_usage": 1, "incorrect_json_schema": 0, "syntax_error": 2, "logic_error": 3, "type_error": 3, "missing_import": 2, "stale_closure": 0, "race_condition": 1, "incorrect_di": 0, "oververbose": 2, "missed_constraint": 1, "other": 0},
        {"hallucinated_api": 0, "wrong_async_usage": 1, "incorrect_json_schema": 0, "syntax_error": 0, "logic_error": 2, "type_error": 1, "missing_import": 0, "stale_closure": 0, "race_condition": 0, "incorrect_di": 1, "oververbose": 0, "missed_constraint": 0, "other": 1},
        {"hallucinated_api": 2, "wrong_async_usage": 3, "incorrect_json_schema": 1, "syntax_error": 1, "logic_error": 5, "type_error": 2, "missing_import": 3, "stale_closure": 1, "race_condition": 0, "incorrect_di": 2, "oververbose": 1, "missed_constraint": 1, "other": 0},
        {"hallucinated_api": 1, "wrong_async_usage": 2, "incorrect_json_schema": 2, "syntax_error": 1, "logic_error": 3, "type_error": 1, "missing_import": 1, "stale_closure": 2, "race_condition": 1, "incorrect_di": 1, "oververbose": 3, "missed_constraint": 0, "other": 1},
    ]
    
    runs = []
    for i, m in enumerate(models):
        overall = m["coding"] * 0.4 + m["reasoning"] * 0.3 + m["instruction"] * 0.2 + 0.72 * 0.1
        runs.append({
            "run_id": f"demo_run_{i+1}_{m['name']}",
            "model": m["name"],
            "model_metadata": {"size": "7B-9B", "quantization": "Q4_K_M"},
            "hardware": {"platform": "macOS 14.5", "processor": "Apple M3 Max", "memory_gb": 64, "architecture": "arm64"},
            "timestamp": datetime.now().isoformat(),
            "git_sha": "abc1234",
            "git_branch": "main",
            "metrics": {
                "coding_score": m["coding"],
                "reasoning_score": m["reasoning"],
                "instruction_score": m["instruction"],
                "frontend_score": 0.72,
                "math_score": 0.75,
                "debugging_score": 0.68,
                "overall_score": overall,
            },
            "performance": {
                "tokens_per_sec": m["tps"],
                "normalized_tps": m["tps"] * 0.95,
                "ttft_ms": m["ttft"],
                "total_latency_ms": m["ttft"] + 2500,
                "memory_pressure_mb": 1200 + i * 400,
            },
            "stats": {
                "mean": overall,
                "std": 0.05 + i * 0.01,
                "min": overall - 0.1,
                "max": overall + 0.05,
                "median": overall,
                "runs": 5,
                "confidence_95": [overall - 0.05, overall + 0.03],
                "coefficient_of_variation": 0.06 + i * 0.01,
            },
            "failures": failure_templates[i],
            "category_scores": {},
            "config_snapshot": {"temperature": 0.2, "max_tokens": 1000},
            "prompt_version": "v1",
            "packs_used": ["nestjs-pack", "react-pack", "debugging-pack"],
            "seed": 42 + i,
        })
    
    return {
        "version": "1.0.0-demo",
        "generated_at": datetime.now().isoformat(),
        "total_models": len(models),
        "total_runs": len(runs),
        "runs": runs,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate dashboard results.json from benchmark output")
    parser.add_argument("--results-dir", default="./results", help="Path to benchmark results directory")
    parser.add_argument("--output", default="./public/results.json", help="Output path for results.json (relative to CWD, typically the dashboard/ directory)")
    parser.add_argument("--demo", action="store_true", help="Generate demo data instead of loading real results")
    args = parser.parse_args()
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if args.demo:
        print("Generating demo data...")
        data = generate_demo_data()
    else:
        results_dir = Path(args.results_dir)
        print(f"Scanning {results_dir.absolute()} for benchmark results...")
        
        result_files = find_result_files(results_dir)
        print(f"Found {len(result_files)} result files")
        
        if not result_files:
            print("No benchmark results found. Generating demo data instead.")
            print("Run: python3 benchmark.py --quick to generate real results.")
            data = generate_demo_data()
        else:
            all_runs = []
            for path in result_files:
                raw_results = load_result_file(path)
                if not raw_results:
                    continue
                
                for raw in raw_results:
                    normalized = normalize_result(raw, path.name)
                    if normalized:
                        all_runs.append(normalized)
            
            print(f"Normalized {len(all_runs)} benchmark runs")
            
            data = {
                "version": "1.0.0",
                "generated_at": datetime.now().isoformat(),
                "total_models": len(set(r["model"] for r in all_runs)),
                "total_runs": len(all_runs),
                "runs": all_runs,
            }
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"✓ Wrote {len(data['runs'])} runs ({data['total_models']} models) to {output_path}")


if __name__ == "__main__":
    main()
