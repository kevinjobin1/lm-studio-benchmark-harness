"""
Trace Diff Engine — token-level, step-level, and metric-level diff between two traces.

Supports three levels of comparison:

1. **Step-level**: Aligns steps from both traces by index and compares timing,
   type, status, and content.

2. **Token-level**: Uses ``difflib.SequenceMatcher`` to find
   insert/delete/replace operations in the response text and per-step output.

3. **Metric-level**: Reports latency delta, memory delta, and token count delta.

Usage:
    from core.trace_diff import diff_traces
    from core.trace_schema import Trace

    diff = diff_traces(trace_a.to_dict(), trace_b.to_dict())
    print(diff["summary"])
"""

from __future__ import annotations

import difflib
from typing import Any, Dict, List, Optional, Tuple


# ── Types ───────────────────────────────────────────────────────────


StepDiffType = str  # "match" | "modified" | "added" | "removed"


# ── Step-level diff ────────────────────────────────────────────────


def _diff_steps(
    steps_a: List[Dict[str, Any]],
    steps_b: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Align steps by index and produce a step-by-step diff.

    Each result dict contains:
        - index: Step index
        - type_a / type_b: Step types (None if missing)
        - label_a / label_b: Step labels (None if missing)
        - diff_type: "match" | "modified" | "added" | "removed"
        - timing_a_ms / timing_b_ms: Timing in ms
        - timing_delta_ms: Signed timing difference (b - a)
        - status_a / status_b: Status strings
        - text_diff: Token-level text diff (if ``detail`` differs)

    Returns:
        List of step diff dicts.
    """
    max_len = max(len(steps_a), len(steps_b))
    result: List[Dict[str, Any]] = []

    for i in range(max_len):
        step_a = steps_a[i] if i < len(steps_a) else None
        step_b = steps_b[i] if i < len(steps_b) else None

        entry: Dict[str, Any] = {"index": i}

        if step_a and step_b:
            entry["type_a"] = step_a.get("type")
            entry["type_b"] = step_b.get("type")
            entry["label_a"] = step_a.get("label")
            entry["label_b"] = step_b.get("label")
            entry["timing_a_ms"] = step_a.get("timing_ms", 0)
            entry["timing_b_ms"] = step_b.get("timing_ms", 0)
            entry["timing_delta_ms"] = step_b.get("timing_ms", 0) - step_a.get("timing_ms", 0)
            entry["status_a"] = step_a.get("status")
            entry["status_b"] = step_b.get("status")

            # Determine diff type
            if (
                step_a.get("type") == step_b.get("type")
                and step_a.get("label") == step_b.get("label")
                and abs(entry["timing_delta_ms"]) < 1
            ):
                entry["diff_type"] = "match"
            else:
                entry["diff_type"] = "modified"

            # Text diff if detail/output differs
            detail_a = step_a.get("detail") or step_a.get("output") or ""
            detail_b = step_b.get("detail") or step_b.get("output") or ""
            if detail_a != detail_b and detail_a and detail_b:
                entry["text_diff"] = _diff_text(detail_a, detail_b)
            elif detail_a and not detail_b:
                entry["text_diff"] = [{"type": "delete", "text": detail_a}]
            elif detail_b and not detail_a:
                entry["text_diff"] = [{"type": "insert", "text": detail_b}]

        elif step_a and not step_b:
            entry["type_a"] = step_a.get("type")
            entry["label_a"] = step_a.get("label")
            entry["timing_a_ms"] = step_a.get("timing_ms", 0)
            entry["timing_b_ms"] = None
            entry["timing_delta_ms"] = None
            entry["status_a"] = step_a.get("status")
            entry["status_b"] = None
            entry["diff_type"] = "removed"

            detail = step_a.get("detail") or step_a.get("output") or ""
            if detail:
                entry["text_diff"] = [{"type": "delete", "text": detail}]

        else:  # step_b only
            entry["type_a"] = None
            entry["type_b"] = step_b.get("type")
            entry["label_a"] = None
            entry["label_b"] = step_b.get("label")
            entry["timing_a_ms"] = None
            entry["timing_b_ms"] = step_b.get("timing_ms", 0)
            entry["timing_delta_ms"] = None
            entry["status_a"] = None
            entry["status_b"] = step_b.get("status")
            entry["diff_type"] = "added"

            detail = step_b.get("detail") or step_b.get("output") or ""
            if detail:
                entry["text_diff"] = [{"type": "insert", "text": detail}]

        result.append(entry)

    return result


# ── Token-level text diff ──────────────────────────────────────────


def _diff_text(text_a: str, text_b: str) -> List[Dict[str, Any]]:
    """Produce a token-level diff between two text strings.

    Uses ``difflib.SequenceMatcher`` with word-level tokenization.
    Each operation is one of: ``"equal"``, ``"replace"``, ``"delete"``,
    ``"insert"``.

    Returns:
        List of dicts with keys ``type`` and ``text``.
    """
    tokens_a = text_a.split()
    tokens_b = text_b.split()

    matcher = difflib.SequenceMatcher(None, tokens_a, tokens_b)
    result: List[Dict[str, Any]] = []

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            result.append({"type": "equal", "text": " ".join(tokens_a[i1:i2])})
        elif op == "replace":
            result.append({"type": "replace", "text": {
                "old": " ".join(tokens_a[i1:i2]),
                "new": " ".join(tokens_b[j1:j2]),
            }})
        elif op == "delete":
            result.append({"type": "delete", "text": " ".join(tokens_a[i1:i2])})
        elif op == "insert":
            result.append({"type": "insert", "text": " ".join(tokens_b[j1:j2])})

    return result


def diff_text_full(text_a: str, text_b: str) -> Dict[str, Any]:
    """Full text diff with statistics.

    Returns:
        Dict with ``operations`` (list) and ``stats`` (insertions, deletions,
        replacements, equality ratio).
    """
    ops = _diff_text(text_a, text_b)
    stats = {"insertions": 0, "deletions": 0, "replacements": 0, "equal_tokens": 0}

    for op in ops:
        if op["type"] == "insert":
            chars = len(op["text"]) if isinstance(op["text"], str) else 0
            stats["insertions"] += chars
        elif op["type"] == "delete":
            chars = len(op["text"]) if isinstance(op["text"], str) else 0
            stats["deletions"] += chars
        elif op["type"] == "replace":
            stats["replacements"] += 1
        elif op["type"] == "equal":
            chars = len(op["text"]) if isinstance(op["text"], str) else 0
            stats["equal_tokens"] += chars

    total_changed = stats["insertions"] + stats["deletions"]
    total_all = total_changed + stats["equal_tokens"] + stats["replacements"]
    stats["ratio"] = round(stats["equal_tokens"] / total_all, 4) if total_all > 0 else 1.0

    return {"operations": ops, "stats": stats}


# ── Metric-level diff ──────────────────────────────────────────────


def _diff_metrics(
    metrics_a: Optional[Dict[str, Any]],
    metrics_b: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compare metrics between two traces.

    Returns:
        Dict with delta for each metric key.
    """
    if not metrics_a and not metrics_b:
        return {}

    metrics_a = metrics_a or {}
    metrics_b = metrics_b or {}

    all_keys = set(metrics_a.keys()) | set(metrics_b.keys())
    deltas: Dict[str, Any] = {}

    for key in sorted(all_keys):
        val_a = metrics_a.get(key)
        val_b = metrics_b.get(key)

        if val_a is not None and val_b is not None:
            try:
                deltas[key] = {
                    "a": val_a,
                    "b": val_b,
                    "delta": round(val_b - val_a, 4),
                    "delta_pct": round(
                        ((val_b - val_a) / val_a) * 100, 2
                    ) if val_a != 0 else None,
                }
            except (TypeError, ValueError):
                deltas[key] = {"a": val_a, "b": val_b, "delta": None}
        elif val_a is not None:
            deltas[key] = {"a": val_a, "b": None, "delta": None}
        else:
            deltas[key] = {"a": None, "b": val_b, "delta": None}

    return deltas


# ── Artifact-level diff ──────────────────────────────────────────────


def _diff_artifacts(
    artifacts_a: Optional[Dict[str, Any]],
    artifacts_b: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compare artifacts (response text, logs, errors) between traces.

    Includes a full text diff on the response text.
    """
    if not artifacts_a and not artifacts_b:
        return {}

    artifacts_a = artifacts_a or {}
    artifacts_b = artifacts_b or {}

    diff: Dict[str, Any] = {}

    # Response text diff
    resp_a = artifacts_a.get("response", "")
    resp_b = artifacts_b.get("response", "")
    if resp_a != resp_b:
        diff["response_diff"] = diff_text_full(resp_a, resp_b)
    else:
        diff["response_diff"] = {"operations": [{"type": "equal", "text": resp_a[:100] + "..."}],
                                 "stats": {"ratio": 1.0}}

    # Logs and errors
    logs_a = artifacts_a.get("logs", [])
    logs_b = artifacts_b.get("logs", [])
    diff["log_delta"] = len(logs_b) - len(logs_a)
    diff["log_details"] = {
        "a": logs_a[:5],  # Truncate for readability
        "b": logs_b[:5],
    }

    errors_a = artifacts_a.get("errors", [])
    errors_b = artifacts_b.get("errors", [])
    diff["error_delta"] = len(errors_b) - len(errors_a)
    diff["error_details"] = {
        "a": errors_a[:5],
        "b": errors_b[:5],
    }

    return diff


# ── Summary ─────────────────────────────────────────────────────────


def _build_summary(
    trace_a: Dict[str, Any],
    trace_b: Dict[str, Any],
    step_diff: List[Dict[str, Any]],
    metric_diff: Dict[str, Any],
    artifact_diff: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a human-readable diff summary."""
    model_a = trace_a.get("model", "Unknown")
    model_b = trace_b.get("model", "Unknown")

    total_steps = len(step_diff)
    matches = sum(1 for s in step_diff if s["diff_type"] == "match")
    modified = sum(1 for s in step_diff if s["diff_type"] == "modified")
    added = sum(1 for s in step_diff if s["diff_type"] == "added")
    removed = sum(1 for s in step_diff if s["diff_type"] == "removed")

    # Timing summary
    time_a = trace_a.get("totalTimeMs", trace_a.get("metrics", {}).get("total_latency_ms", 0))
    time_b = trace_b.get("totalTimeMs", trace_b.get("metrics", {}).get("total_latency_ms", 0))
    time_delta = time_b - time_a
    faster = model_a if time_delta > 0 else model_b

    # Token summary
    metrics_a = trace_a.get("metrics", {})
    metrics_b = trace_b.get("metrics", {})
    tokens_a = metrics_a.get("total_tokens", 0)
    tokens_b = metrics_b.get("total_tokens", 0)
    token_delta = tokens_b - tokens_a

    # Memory summary
    mem_a = metrics_a.get("memory_pressure_mb", 0)
    mem_b = metrics_b.get("memory_pressure_mb", 0)
    mem_delta = mem_b - mem_a

    return {
        "models": {"a": model_a, "b": model_b},
        "total_steps": total_steps,
        "step_matches": matches,
        "step_modified": modified,
        "step_added": added,
        "step_removed": removed,
        "timing": {
            "a_ms": time_a,
            "b_ms": time_b,
            "delta_ms": round(time_delta, 2),
            "faster_model": faster,
            "summary": f"{faster} was {abs(time_delta):.0f}ms faster"
                       if abs(time_delta) > 1
                       else "Identical total time",
        },
        "tokens": {
            "a": tokens_a,
            "b": tokens_b,
            "delta": token_delta,
        },
        "memory": {
            "a_mb": mem_a,
            "b_mb": mem_b,
            "delta_mb": round(mem_delta, 2),
            "summary": f"{'Higher' if mem_delta > 0 else 'Lower'} by {abs(mem_delta):.1f} MB"
                       if mem_delta != 0
                       else "Same memory pressure",
        },
    }


# ── Main diff function ──────────────────────────────────────────────


def diff_traces(
    trace_a: Dict[str, Any],
    trace_b: Dict[str, Any],
    include_text_diff: bool = True,
) -> Dict[str, Any]:
    """Compute a full three-level diff between two trace dicts.

    Args:
        trace_a: First trace dict (e.g. from ``Trace.to_dict()``).
        trace_b: Second trace dict to compare against.
        include_text_diff: If False, skip token-level text diff (faster).

    Returns:
        Dict with keys:
        - ``summary``: High-level comparison statistics.
        - ``steps``: Per-step aligned diff entries.
        - ``metrics``: Metric-level deltas.
        - ``artifacts``: Artifact-level diff (response text, logs, errors).
    """
    # Extract steps from either the Trace dict or TraceRun dict format
    steps_a = trace_a.get("steps") or trace_a.get("events", [])
    steps_b = trace_b.get("steps") or trace_b.get("events", [])

    # Convert TraceEvent objects to dicts if they're not already
    steps_a = [_as_dict(s) for s in steps_a]
    steps_b = [_as_dict(s) for s in steps_b]

    metrics_a = trace_a.get("metrics")
    metrics_b = trace_b.get("metrics")
    artifacts_a = trace_a.get("artifacts")
    artifacts_b = trace_b.get("artifacts")

    step_diff = _diff_steps(steps_a, steps_b)
    metric_diff = _diff_metrics(metrics_a, metrics_b)
    artifact_diff = _diff_artifacts(artifacts_a, artifacts_b)
    summary = _build_summary(trace_a, trace_b, step_diff, metric_diff, artifact_diff)

    return {
        "summary": summary,
        "steps": step_diff,
        "metrics": metric_diff,
        "artifacts": artifact_diff,
    }


def diff_trace_files(
    path_a: str,
    path_b: str,
    include_text_diff: bool = True,
) -> Dict[str, Any]:
    """Load two trace JSON files and compute their diff.

    Args:
        path_a: Path to first trace JSON file.
        path_b: Path to second trace JSON file.
        include_text_diff: Passed through to ``diff_traces()``.

    Returns:
        The diff result from ``diff_traces()``.
    """
    import json

    with open(path_a) as f:
        trace_a = json.load(f)
    with open(path_b) as f:
        trace_b = json.load(f)

    return diff_traces(trace_a, trace_b, include_text_diff=include_text_diff)


def _as_dict(obj: Any) -> Dict[str, Any]:
    """Convert a potentially dataclass-backed object to a plain dict."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(obj)
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return {}


__all__ = [
    "diff_traces",
    "diff_trace_files",
    "diff_text_full",
]
