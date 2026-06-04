"""
``modellens regression`` — Historical regression detection CLI.

Detects performance regressions in model metrics using statistical
change-point analysis (CUSUM + z-score).

Usage:
    modellens regression detect --model qwen-3.5-9b --metric tokens_per_second
    modellens regression check --all    # Check all models and metrics
    modellens regression history        # Show past alerts
    modellens regression monitor        # Watch for new regressions
"""

from __future__ import annotations

import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import click

from .utils import _echo, RICH_AVAILABLE, console
from core.regression import (
    detect_regression,
    detect_all,
    AlertStore,
    get_alert_store,
    RegressionAlert,
)
from core.metrics_store import get_metrics_store


# ── Shared helpers ─────────────────────────────────────────────────


def _format_alert(alert: RegressionAlert, prefix: str = "  ") -> str:
    """Format a single alert as a one-line string."""
    icon = {
        "critical": "🔴",
        "warning": "🟡",
        "info": "🟢",
    }.get(alert.severity, "⚪")

    direction_arrow = "↓" if alert.direction == "degradation" else "↑"
    return (
        f"{prefix}{icon} {alert.model}/{alert.metric} {direction_arrow} "
        f"{alert.change_magnitude:.1f}% "
        f"(z={alert.z_score:.1f}, confidence={alert.confidence:.0%})"
    )


def _render_alerts_table(alerts: list[RegressionAlert], title: str = "Regression Alerts"):
    """Render alerts as a rich table (fallback to plain text)."""
    if not alerts:
        _echo("  ✓ No regressions detected.", "green")
        return

    if RICH_AVAILABLE and console:
        from rich.table import Table
        from rich.style import Style

        table = Table(title=title)
        table.add_column("Severity", style="bold")
        table.add_column("Model")
        table.add_column("Metric")
        table.add_column("Dir")
        table.add_column("Change", justify="right")
        table.add_column("Z-Score", justify="right")
        table.add_column("Confidence", justify="right")

        for a in alerts:
            sev_style = {
                "critical": "red",
                "warning": "yellow",
                "info": "green",
            }.get(a.severity, "white")
            direction_arrow = "↓" if a.direction == "degradation" else "↑"
            table.add_row(
                a.severity.upper(),
                a.model,
                a.metric,
                direction_arrow,
                f"{a.change_magnitude:.1f}%",
                f"{a.z_score:.2f}" if a.z_score else "—",
                f"{a.confidence:.0%}",
                style=Style(color=sev_style) if a.severity == "critical" else None,
            )
        console.print("")
        console.print(table)
    else:
        _echo(f"\n  {title}:")
        for a in alerts:
            _echo(_format_alert(a), "bold red" if a.severity == "critical" else "yellow")
    _echo(f"  ({len(alerts)} alert{'s' if len(alerts) != 1 else ''})", "dim")


# ── Click group ────────────────────────────────────────────────────


@click.group()
def regression():
    """Detect performance regressions in model metrics.

    Uses statistical change-point detection (CUSUM + z-score) to
    identify when a model's performance drops significantly compared
    to its recent history.
    """
    pass


# ── detect ─────────────────────────────────────────────────────────


@regression.command()
@click.option("--model", "-m", default=None, help="Model name to check")
@click.option("--metric", "-M", default=None, help="Metric name to check (e.g. tokens_per_second)")
@click.option("--window", "-w", type=int, default=10, show_default=True, help="Detection window size")
@click.option("--threshold", "-t", type=float, default=2.0, show_default=True, help="Z-score threshold")
@click.option("--store", "store_path", default="results/metrics.db", show_default=True, help="Metrics DB path")
@click.option("--save/--no-save", default=True, help="Persist alerts to DB")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--all", "check_all", is_flag=True, help="Check all models and metrics")
def detect(
    model: Optional[str],
    metric: Optional[str],
    window: int,
    threshold: float,
    store_path: str,
    save: bool,
    json_output: bool,
    check_all: bool,
):
    """Detect regressions for a (model, metric) pair or all combinations."""
    ms = get_metrics_store(store_path)

    if check_all:
        _echo("🔍 Checking all models and metrics for regressions...", "bold blue")
        alerts = detect_all(ms, window=window, z_threshold=threshold)
    elif model and metric:
        _echo(f"🔍 Checking {model}/{metric} (window={window}, z_threshold={threshold})...", "bold blue")
        alerts = detect_regression(ms, model=model, metric=metric, window=window, z_threshold=threshold)
    elif model:
        # Check all metrics for this model
        _echo(f"🔍 Checking all metrics for {model}...", "bold blue")
        metrics = ms.distinct_metrics(model=model)
        alerts = []
        for m in metrics:
            detected = detect_regression(ms, model=model, metric=m, window=window, z_threshold=threshold)
            alerts.extend(detected)
        alerts.sort(key=lambda a: (0 if a.severity == "critical" else 1 if a.severity == "warning" else 2, -a.confidence))
    else:
        _echo("✗ Specify --model and --metric, or use --all to check everything.", "red")
        sys.exit(1)

    if save and alerts:
        alert_store = get_alert_store(store_path)
        for a in alerts:
            alert_store.store(a)
        _echo(f"  ✓ Persisted {len(alerts)} alert(s) to {store_path}", "dim")

    if json_output:
        import json as _json
        click.echo(_json.dumps([a.to_dict() for a in alerts], indent=2))
    else:
        _echo("")
        title = "All Regressions" if check_all else f"Regressions: {model}/{metric or '*'}"
        _render_alerts_table(alerts, title=title)


# ── history ────────────────────────────────────────────────────────


@regression.command()
@click.option("--model", "-m", default=None, help="Filter by model")
@click.option("--metric", "-M", default=None, help="Filter by metric")
@click.option("--severity", "-s", type=click.Choice(["critical", "warning", "info"]), default=None, help="Filter by severity")
@click.option("--limit", type=int, default=50, show_default=True, help="Max alerts to show")
@click.option("--store", "store_path", default="results/metrics.db", show_default=True, help="Metrics DB path")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def history(
    model: Optional[str],
    metric: Optional[str],
    severity: Optional[str],
    limit: int,
    store_path: str,
    json_output: bool,
):
    """Show historical regression alerts."""
    alert_store = get_alert_store(store_path)
    stats = alert_store.stats()

    if stats.get("total", 0) == 0:
        _echo("  ℹ No regression alerts recorded yet.", "dim")
        _echo("  Run 'modellens regression detect' or benchmarks to generate alerts.", "dim")
        return

    alerts = alert_store.list_alerts(
        model=model,
        metric=metric,
        severity=severity,
        limit=limit,
    )

    if json_output:
        import json as _json
        click.echo(_json.dumps({
            "stats": {
                "total": stats.get("total", 0),
                "critical": stats.get("critical", 0),
                "warning": stats.get("warning", 0),
                "info": stats.get("info", 0),
                "models": stats.get("model_count", 0),
                "metrics": stats.get("metric_count", 0),
            },
            "alerts": [a.to_dict() for a in alerts],
        }, indent=2))
    else:
        _echo(f"\n📊 Alert History (total: {stats.get('total', 0)}", "bold blue")
        _echo(f"   Critical: {stats.get('critical', 0)}  |  "
              f"Warning: {stats.get('warning', 0)}  |  "
              f"Info: {stats.get('info', 0)}  |  "
              f"Models: {stats.get('model_count', 0)}  |  "
              f"Metrics: {stats.get('metric_count', 0)}", "dim")
        _render_alerts_table(alerts, title=f"Recent Alerts (last {limit})")


# ── monitor ────────────────────────────────────────────────────────


@regression.command()
@click.option("--interval", "-i", type=int, default=60, show_default=True, help="Polling interval in seconds")
@click.option("--store", "store_path", default="results/metrics.db", show_default=True, help="Metrics DB path")
@click.option("--window", "-w", type=int, default=10, show_default=True, help="Detection window size")
@click.option("--threshold", "-t", type=float, default=2.0, show_default=True, help="Z-score threshold")
def monitor(interval: int, store_path: str, window: int, threshold: float):
    """Continuously monitor for regressions.

    Polls MetricsStore every N seconds and prints new alerts.
    Press Ctrl+C to stop.
    """
    ms = get_metrics_store(store_path)
    alert_store = get_alert_store(store_path)

    _echo("🔍 Regression Monitor", "bold blue")
    _echo(f"   Polling {store_path} every {interval}s  (window={window}, z_threshold={threshold})", "dim")
    _echo("   Press Ctrl+C to stop.\n", "dim")

    # Track which alerts we've already seen (by their identity)
    seen: set[str] = set()
    running = True

    def _signal_handler(signum, frame):
        nonlocal running
        running = False
        _echo("\n⏹ Stopped.", "yellow")

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    while running:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        alerts = detect_all(ms, window=window, z_threshold=threshold)

        for alert in alerts:
            # Build a unique key to avoid duplicate notifications
            key = f"{alert.model}/{alert.metric}/{alert.severity}"
            if key not in seen:
                seen.add(key)
                alert_store.store(alert)
                _echo(f"[{timestamp}] {_format_alert(alert)}",
                      "bold red" if alert.severity == "critical" else "yellow")

            # Remove previous, non-critical alerts when a newer one supersedes
            if alert.severity == "info":
                seen.discard(key)

        if not alerts:
            _echo(f"[{timestamp}] ✓ No regressions detected.", "dim")

        # Wait for the next poll (check every 1s for interrupt)
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)


# ── stats ──────────────────────────────────────────────────────────


@regression.command()
@click.option("--store", "store_path", default="results/metrics.db", show_default=True, help="Metrics DB path")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def stats(store_path: str, json_output: bool):
    """Show aggregate alert statistics."""
    alert_store = get_alert_store(store_path)
    s = alert_store.stats()

    if json_output:
        import json as _json
        click.echo(_json.dumps(s, indent=2))
    else:
        _echo("\n📊 Regression Alert Stats", "bold blue")
        _echo(f"   Total alerts:    {s.get('total', 0)}", "white")
        _echo(f"   Critical:        {s.get('critical', 0)}", "red")
        _echo(f"   Warning:         {s.get('warning', 0)}", "yellow")
        _echo(f"   Info:            {s.get('info', 0)}", "green")
        _echo(f"   Unique models:   {s.get('model_count', 0)}", "dim")
        _echo(f"   Unique metrics:  {s.get('metric_count', 0)}", "dim")
        _echo(f"   Latest alert:    {s.get('latest_alert', '—')}", "dim")
