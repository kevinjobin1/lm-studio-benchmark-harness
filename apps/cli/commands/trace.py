"""Trace commands for modellens CLI.

Provides tools for comparing and analyzing execution traces.

Usage:
    modellens trace diff <path_a> <path_b>
    modellens trace diff --trace-id-a <id> --trace-id-b <id> --traces-dir results/traces
"""

import json
import sys
from pathlib import Path

import click

from .utils import _echo


@click.group()
def trace():
    """Analyze and compare execution traces.

    \b
    Examples:
      modellens trace diff trace_a.json trace_b.json
      modellens trace diff --trace-id-a run_abc --trace-id-b run_def --traces-dir results/traces
    """
    pass


@trace.command()
@click.argument("path_a", required=False, default=None)
@click.argument("path_b", required=False, default=None)
@click.option(
    "--trace-id-a", default=None,
    help="Trace ID for the first trace (requires --traces-dir)",
)
@click.option(
    "--trace-id-b", default=None,
    help="Trace ID for the second trace (requires --traces-dir)",
)
@click.option(
    "--traces-dir", default="results/traces",
    help="Directory containing trace JSON files (default: results/traces)",
)
@click.option("--json", "json_output", is_flag=True, help="Output diff as JSON")
@click.option("--no-text-diff", is_flag=True, help="Skip token-level text diff (faster)")
def diff(path_a, path_b, trace_id_a, trace_id_b, traces_dir, json_output, no_text_diff):
    """Compute a structured diff between two trace files.

    Compares two execution traces at three levels:
    - Step-level: timing, type, status differences
    - Token-level: word-level insert/delete/replace in response text
    - Metric-level: latency, memory, token count deltas

    \b
    Examples:
      modellens trace diff trace_a.json trace_b.json
      modellens trace diff --trace-id-a run_123 --trace-id-b run_456
    """
    from core.trace_diff import diff_trace_files, diff_traces

    # Resolve file paths
    if path_a and path_b:
        file_a = Path(path_a)
        file_b = Path(path_b)
    elif trace_id_a and trace_id_b:
        traces_path = Path(traces_dir)
        file_a = traces_path / f"{trace_id_a}.json"
        file_b = traces_path / f"{trace_id_b}.json"
        if not file_a.exists():
            _echo(f"✗ Trace file not found: {file_a}", "red")
            sys.exit(1)
        if not file_b.exists():
            _echo(f"✗ Trace file not found: {file_b}", "red")
            sys.exit(1)
    else:
        _echo("✗ Provide either two file paths or --trace-id-a and --trace-id-b", "red")
        sys.exit(1)

    result = diff_trace_files(str(file_a), str(file_b), include_text_diff=not no_text_diff)

    if json_output:
        click.echo(json.dumps(result, indent=2, default=str))
        return

    summary = result["summary"]

    # ── Print human-readable diff ──────────────────────────────
    _echo("")
    _echo(f"🔬  Trace Diff: {summary['models']['a']} vs {summary['models']['b']}", "bold blue")
    _echo("")

    # Timing
    t = summary["timing"]
    _echo(f"⏱  Timing")
    _echo(f"   {summary['models']['a']}: {t['a_ms']:.0f}ms", "dim")
    _echo(f"   {summary['models']['b']}: {t['b_ms']:.0f}ms", "dim")
    _echo(f"   {t['summary']}", "green" if t['delta_ms'] > 0 else "yellow")

    # Tokens
    tk = summary["tokens"]
    _echo(f"📝 Tokens")
    _echo(f"   {summary['models']['a']}: {tk['a']}", "dim")
    _echo(f"   {summary['models']['b']}: {tk['b']}", "dim")
    _echo(f"   Delta: {tk['delta']:+d}", "bold")

    # Memory
    mem = summary["memory"]
    _echo(f"💾 Memory")
    _echo(f"   {summary['models']['a']}: {mem['a_mb']:.0f} MB", "dim")
    _echo(f"   {summary['models']['b']}: {mem['b_mb']:.0f} MB", "dim")
    _echo(f"   {mem['summary']}", "bold")

    # Steps
    _echo(f"📊 Steps")
    _echo(f"   Total: {summary['total_steps']}", "dim")
    _echo(f"   Matches: {summary['step_matches']}", "green")
    _echo(f"   Modified: {summary['step_modified']}", "yellow")
    _echo(f"   Added: {summary['step_added']}", "yellow")
    _echo(f"   Removed: {summary['step_removed']}", "red")

    # Step details (show first 10 modified/added/removed)
    changes = [s for s in result["steps"] if s["diff_type"] != "match"]
    if changes:
        _echo(f"\n🔍 Step Details ({len(changes)} changes — showing first 10):", "bold")
        for step in changes[:10]:
            dt = step["diff_type"]
            icon = {"match": "✓", "modified": "~", "added": "+", "removed": "-"}.get(dt, "?")
            label = step.get("label_a") or step.get("label_b") or f"Step {step['index']}"
            delta = step.get("timing_delta_ms")
            delta_str = f" ({delta:+d}ms)" if delta is not None else ""
            _echo(f"   {icon} [{step['index']}] {label}{delta_str}", "dim")

    # Metric deltas
    metric_changes = {k: v for k, v in result["metrics"].items() if v.get("delta") is not None}
    if metric_changes:
        _echo(f"\n📈 Metric Deltas:", "bold")
        for key, val in metric_changes.items():
            delta = val.get("delta", "")
            pct = val.get("delta_pct")
            pct_str = f" ({pct:+.1f}%)" if pct is not None else ""
            _echo(f"   {key:<30} {val['a']:>8} → {val['b']:<8} ({delta:+.4f}{pct_str})", "dim")

    _echo("")


@trace.command()
@click.argument("text_a_file", type=click.Path(exists=True))
@click.argument("text_b_file", type=click.Path(exists=True))
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def text_diff(text_a_file, text_b_file, json_output):
    """Compute a token-level diff between two text files.

    Useful for comparing model responses directly without the full trace context.
    """
    from core.trace_diff import diff_text_full

    with open(text_a_file) as f:
        text_a = f.read()
    with open(text_b_file) as f:
        text_b = f.read()

    result = diff_text_full(text_a, text_b)

    if json_output:
        click.echo(json.dumps(result, indent=2, default=str))
        return

    stats = result["stats"]
    _echo("")
    _echo("📝 Text Diff", "bold blue")
    _echo(f"   Equality ratio: {stats['ratio']:.2%}", "dim")
    _echo(f"   Insertions: {stats['insertions']} chars", "green")
    _echo(f"   Deletions: {stats['deletions']} chars", "red")
    _echo(f"   Replacements: {stats['replacements']}", "yellow")
    _echo("")

    # Show operations
    for op in result["operations"][:20]:  # Limit display
        text = op["text"]
        if isinstance(text, dict):
            display = text.get("old", "")[:60]
        else:
            display = text[:60] if text else ""
        if not display:
            continue
        if op["type"] == "equal":
            _echo(f"   ✓ {display}", "dim")
        elif op["type"] == "insert":
            _echo(f"   + {display}", "green")
        elif op["type"] == "delete":
            _echo(f"   - {display}", "red")
        elif op["type"] == "replace":
            _echo(f"   ~ {text.get('old', '')[:40]} → {text.get('new', '')[:40]}", "yellow")

    remaining = len(result["operations"]) - 20
    if remaining > 0:
        _echo(f"   ... and {remaining} more operations", "dim")
    _echo("")


@trace.command()
@click.argument("trace_id")
@click.option(
    "--traces-dir", default="results/traces",
    help="Directory containing trace JSON files (default: results/traces)",
)
@click.option(
    "--output", "-o", "output", default=None,
    help="Output file path (default: prints to stdout)",
)
@click.option(
    "--base64", "as_base64", is_flag=True,
    help="Output as base64-encoded string (for URL sharing)",
)
@click.option(
    "--url", "share_url", is_flag=True,
    help="Generate a shareable URL with embedded base64 snapshot",
)
def snapshot(trace_id, traces_dir, output, as_base64, share_url):
    """Export an execution trace as a shareable snapshot.

    Converts a trace into a compact, self-contained snapshot format.
    Use --base64 for a URL-safe encoded string, or --url for a full
    shareable link.

    \b
    Examples:
      modellens trace snapshot run_abc123
      modellens trace snapshot run_abc123 --base64
      modellens trace snapshot run_abc123 --url
      modellens trace snapshot run_abc123 -o snapshot.json
    """
    from core.trace_schema import Trace, TraceMetrics, TraceArtifacts, TraceEvent

    import json

    # Load trace
    traces_path = Path(traces_dir)
    trace_file = traces_path / f"{trace_id}.json"

    if not trace_file.exists():
        _echo(f"✗ Trace file not found: {trace_file}", "red")
        sys.exit(1)

    with open(trace_file) as f:
        trace_dict = json.load(f)

    # Reconstruct full Trace object from the dict (not just basic fields)
    trace = Trace(
        trace_id=trace_dict.get("trace_id", trace_id),
        run_id=trace_dict.get("run_id", ""),
        model=trace_dict.get("model", "unknown"),
        provider=trace_dict.get("provider", "unknown"),
        prompt=trace_dict.get("prompt", ""),
        pack=trace_dict.get("pack", ""),
        started_at=trace_dict.get("timestamp") or trace_dict.get("started_at", ""),
    )

    # Populate metrics
    md = trace_dict.get("metrics", {})
    trace.metrics = TraceMetrics(
        ttft_ms=md.get("ttft_ms", 0),
        tokens_per_second=md.get("tokens_per_second", 0),
        total_tokens=md.get("total_tokens", 0),
        prompt_tokens=md.get("prompt_tokens", 0),
        completion_tokens=md.get("completion_tokens", 0),
        total_latency_ms=md.get("total_latency_ms", 0),
        memory_pressure_mb=md.get("memory_pressure_mb", 0),
        token_timings_ms=md.get("token_timings_ms", []),
    )

    # Populate artifacts
    ad = trace_dict.get("artifacts", {})
    trace.artifacts = TraceArtifacts(
        response=ad.get("response", ""),
        logs=ad.get("logs", []),
        errors=ad.get("errors", []),
    )

    # Populate events/steps
    for step in trace_dict.get("steps", []):
        trace.events.append(TraceEvent(
            id=step.get("id", f"step_{len(trace.events)}"),
            type=step.get("type", "system"),
            label=step.get("label", ""),
            detail=step.get("detail"),
            timing_ms=step.get("timing_ms", 0),
            tool=step.get("tool"),
            input=step.get("input"),
            output=step.get("output"),
            status=step.get("status", "success"),
        ))

    trace.hardware = trace_dict.get("hardware")

    snapshot_data = trace.to_snapshot(compress=True)

    if as_base64:
        encoded = trace.to_snapshot_base64(compress=True)
        if output:
            Path(output).write_text(encoded)
            _echo(f"✓ Base64 snapshot saved to {output}", "green")
        else:
            click.echo(encoded)
    elif share_url:
        from core.trace_schema import snapshot_to_share_url
        url = snapshot_to_share_url(snapshot_data)
        if output:
            Path(output).write_text(url)
            _echo(f"✓ Shareable URL saved to {output}", "green")
        else:
            click.echo(url)
    else:
        json_str = json.dumps(snapshot_data, indent=2, default=str, ensure_ascii=False)
        if output:
            Path(output).write_text(json_str)
            _echo(f"✓ Snapshot saved to {output}", "green")
        else:
            click.echo(json_str)