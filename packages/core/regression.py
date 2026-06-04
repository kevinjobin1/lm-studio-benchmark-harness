"""
Regression Detection — statistical change-point detection for model performance metrics.

Detects when a model's performance degrades significantly compared to its own
recent history, using cumulative sum (CUSUM) change-point detection with a
z-score fallback when ``scipy`` is not available.

Usage:
    from core.regression import detect_regression
    from core.metrics_store import MetricsStore

    store = MetricsStore("results/metrics.db")
    alerts = detect_regression(store, model="qwen-3.5-9b", metric="tokens_per_second")
    for alert in alerts:
        print(f"{alert.severity}: {alert.model}/{alert.metric} "
              f"dropped {alert.change_magnitude:.1f}%")
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ── Regression Alert ───────────────────────────────────────────────


@dataclass
class RegressionAlert:
    """A detected performance regression.

    Attributes:
        model: Model name (e.g. "qwen-3.5-9b").
        metric: Metric name (e.g. "tokens_per_second", "ttft_ms").
        severity: Alert severity: "info", "warning", "critical".
        direction: "degradation" (downward) or "improvement" (upward).
        confidence: Statistical confidence (0.0–1.0).
        change_magnitude: Percentage change relative to baseline mean.
        previous_avg: Baseline mean before the shift.
        current_value: Latest detected value.
        baseline_std: Standard deviation of the baseline window.
        z_score: Z-score of the current value vs baseline.
        window_size: Number of data points in the detection window.
        timestamp: ISO 8601 timestamp when detected.
        run_id: Associated run (if detected during a benchmark).
    """

    model: str
    metric: str
    severity: str = "warning"  # info, warning, critical
    direction: str = "degradation"  # degradation, improvement
    confidence: float = 0.0
    change_magnitude: float = 0.0
    previous_avg: Optional[float] = None
    current_value: Optional[float] = None
    baseline_std: Optional[float] = None
    z_score: Optional[float] = None
    window_size: int = 10
    timestamp: str = ""
    run_id: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegressionAlert":
        """Deserialize from a dict."""
        return cls(**data)


# ── Detection Methods ──────────────────────────────────────────────


def _z_score(values: Sequence[float]) -> List[float]:
    """Compute z-scores for a sequence of values."""
    n = len(values)
    if n < 2:
        return [0.0] * n
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    std = math.sqrt(variance) if variance > 0 else 1e-10
    return [(v - mean) / std for v in values]


def _cusum(values: Sequence[float], threshold: float = 5.0) -> Tuple[List[float], List[int]]:
    """CUSUM change-point detection.

    Computes the cumulative sum of deviations from the mean, then flags
    points where the cumulative sum exceeds the threshold.

    Args:
        values: Time-ordered metric values.
        threshold: CUSUM threshold in standard deviations.

    Returns:
        Tuple of (cumulative_sums, change_point_indices).
    """
    n = len(values)
    if n < 2:
        return [0.0] * n, []

    mean = sum(values) / n
    # Use mean absolute deviation as a robust scale estimate
    mad = sum(abs(v - mean) for v in values) / n
    scale = mad if mad > 1e-10 else mean * 0.1 if abs(mean) > 1e-10 else 1.0

    cumsum = [0.0]
    change_points: List[int] = []

    for i in range(1, n):
        s = cumsum[-1] + (values[i] - mean) / scale
        cumsum.append(s)

    # Detect change points where the cumulative sum exceeds the threshold
    drift = 0.0
    for i in range(1, n):
        if abs(cumsum[i]) > threshold:
            if drift == 0.0:
                # Start of a drift
                drift = cumsum[i]
                change_points.append(i)
            elif abs(cumsum[i]) < abs(drift) * 0.5:
                # Returned toward baseline — end of drift
                drift = 0.0
        else:
            drift = 0.0

    return cumsum, change_points


def detect_regression(
    store: Any,
    model: str,
    metric: str,
    *,
    window: int = 10,
    z_threshold: float = 2.0,
    cusum_threshold: float = 5.0,
    min_samples: int = 5,
    method: str = "auto",
) -> List[RegressionAlert]:
    """Detect performance regression for a (model, metric) pair.

    Queries the last ``window`` values from MetricsStore, then checks
    for statistical change-points using CUSUM (preferred) or z-score.

    Args:
        store: A ``MetricsStore`` instance.
        model: Model name to check.
        metric: Metric name to check (e.g. "tokens_per_second").
        window: Number of most-recent data points to examine.
        z_threshold: Z-score threshold for flagging a regression (default 2.0).
        cusum_threshold: CUSUM threshold in std-dev units (default 5.0).
        min_samples: Minimum number of data points required for detection.
        method: "cusum", "zscore", or "auto" (tries CUSUM first, falls back).

    Returns:
        List of ``RegressionAlert`` objects, empty if no regression detected.
    """
    from core.metrics_store import MetricsStore

    if not isinstance(store, MetricsStore):
        raise TypeError(f"Expected MetricsStore, got {type(store).__name__}")

    # Query recent values (most recent first, then reverse for chronological)
    raw = store.query(
        metric=metric,
        model=model,
        limit=window + 20,  # fetch extra to get a clean baseline
        order="DESC",
    )
    if len(raw) < min_samples:
        return []

    # Chronological order (oldest first) for time-series analysis
    values_chrono = [r["value"] for r in reversed(raw)]
    if len(values_chrono) > window:
        values_chrono = values_chrono[-window:]

    n = len(values_chrono)
    if n < min_samples:
        return []

    # Latest value and baseline (all but the last N/4 values, minimum 3)
    baseline_end = max(3, n - n // 4)
    baseline = values_chrono[:baseline_end]
    recent = values_chrono[baseline_end:]

    if len(baseline) < 3 or len(recent) < 1:
        return []

    baseline_mean = sum(baseline) / len(baseline)
    baseline_var = (
        sum((v - baseline_mean) ** 2 for v in baseline) / (len(baseline) - 1)
        if len(baseline) > 1
        else 1e-10
    )
    baseline_std = math.sqrt(baseline_var) if baseline_var > 0 else 1e-10
    current_value = recent[-1]
    z = (current_value - baseline_mean) / baseline_std if baseline_std > 0 else 0.0

    # Run CUSUM if requested
    cusum_cps = []
    if method in ("cusum", "auto"):
        _, cusum_cps = _cusum(values_chrono, threshold=cusum_threshold)

    # Determine if there's a regression
    is_regression = False
    confidence = 0.0
    severity = "info"
    direction = "degradation" if current_value < baseline_mean else "improvement"

    # Prefer CUSUM for detection
    if cusum_cps:
        last_cp = cusum_cps[-1]
        if last_cp >= baseline_end:
            is_regression = True
            # Confidence based on how far into the recent window the change point is
            cp_offset = (last_cp - baseline_end) / max(len(recent), 1)
            confidence = min(0.95, 0.5 + cp_offset * 0.5)
            severity = "critical" if abs(z) > 3.0 else ("warning" if abs(z) > 2.0 else "info")
        elif abs(z) > z_threshold:
            # CUSUM found a change point in baseline, but the latest value
            # still deviates — flag it
            is_regression = True
            confidence = min(0.8, 0.3 + abs(z) * 0.1)
            severity = "critical" if abs(z) > 3.0 else "warning"
    elif abs(z) >= z_threshold:
        # Fallback to z-score
        is_regression = True
        confidence = min(0.9, 0.3 + abs(z) * 0.1)
        severity = "critical" if abs(z) > 3.0 else ("warning" if abs(z) > 2.0 else "info")

    if not is_regression:
        return []

    # Compute percentage change
    if abs(baseline_mean) > 1e-10:
        change_mag = abs((current_value - baseline_mean) / baseline_mean) * 100.0
    else:
        change_mag = 0.0

    return [
        RegressionAlert(
            model=model,
            metric=metric,
            severity=severity,
            direction=direction,
            confidence=round(confidence, 4),
            change_magnitude=round(change_mag, 2),
            previous_avg=round(baseline_mean, 4),
            current_value=round(current_value, 4),
            baseline_std=round(baseline_std, 4),
            z_score=round(z, 4),
            window_size=n,
        )
    ]


# ── Bulk Detection ─────────────────────────────────────────────────


def detect_all(
    store: Any,
    *,
    metrics: Optional[List[str]] = None,
    models: Optional[List[str]] = None,
    window: int = 10,
    z_threshold: float = 2.0,
) -> List[RegressionAlert]:
    """Run regression detection across all (model, metric) combinations.

    Args:
        store: A ``MetricsStore`` instance.
        metrics: Metric names to check (default: all distinct metrics in store).
        models: Model names to check (default: all distinct models in store).
        window: Detection window size.
        z_threshold: Z-score threshold.

    Returns:
        List of all detected ``RegressionAlert`` objects.
    """
    from core.metrics_store import MetricsStore

    if not isinstance(store, MetricsStore):
        raise TypeError(f"Expected MetricsStore, got {type(store).__name__}")

    all_metrics = metrics or store.distinct_metrics()
    all_models = models or store.distinct_models()

    alerts: List[RegressionAlert] = []
    for model in all_models:
        for metric in all_metrics:
            try:
                detected = detect_regression(
                    store,
                    model=model,
                    metric=metric,
                    window=window,
                    z_threshold=z_threshold,
                )
                alerts.extend(detected)
            except Exception:
                # Skip (model, metric) pairs that error (e.g., no data)
                continue

    # Sort by severity (critical first) then confidence
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: (severity_order.get(a.severity, 99), -a.confidence))
    return alerts


# ── Alert Store (persists alerts to SQLite for dashboard queries) ──


class AlertStore:
    """Persistent storage for regression alerts.

    Stores alerts in the same SQLite database as MetricsStore for easy
    dashboard queries.  Creates a separate ``regression_alerts`` table.

    Usage:
        alert_store = AlertStore(\"results/metrics.db\")
        alert_store.store(alert)
        history = alert_store.list_alerts(model=\"qwen-3.5-9b\")
    """

    def __init__(self, db_path: str | Path = "results/metrics.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None

    @property
    def conn(self):
        """Lazy connection with WAL mode."""
        if self._conn is None:
            import sqlite3

            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.row_factory = sqlite3.Row
            self._ensure_schema()
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _ensure_schema(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS regression_alerts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                model       TEXT NOT NULL,
                metric      TEXT NOT NULL,
                severity    TEXT NOT NULL DEFAULT 'warning',
                direction   TEXT NOT NULL DEFAULT 'degradation',
                confidence  REAL DEFAULT 0.0,
                change_magnitude REAL DEFAULT 0.0,
                previous_avg    REAL,
                current_value   REAL,
                baseline_std    REAL,
                z_score         REAL,
                window_size     INTEGER DEFAULT 10,
                run_id      TEXT DEFAULT '',
                timestamp   TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_alerts_model
                ON regression_alerts(model);
            CREATE INDEX IF NOT EXISTS idx_alerts_severity
                ON regression_alerts(severity);
            CREATE INDEX IF NOT EXISTS idx_alerts_created
                ON regression_alerts(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_alerts_model_metric
                ON regression_alerts(model, metric);
        """)

    def store(self, alert: RegressionAlert) -> int:
        """Persist a regression alert.

        Returns the row ID.
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO regression_alerts
                (model, metric, severity, direction, confidence,
                 change_magnitude, previous_avg, current_value,
                 baseline_std, z_score, window_size, run_id, timestamp, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.model,
                alert.metric,
                alert.severity,
                alert.direction,
                alert.confidence,
                alert.change_magnitude,
                alert.previous_avg,
                alert.current_value,
                alert.baseline_std,
                alert.z_score,
                alert.window_size,
                alert.run_id,
                alert.timestamp,
                now,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def list_alerts(
        self,
        *,
        model: Optional[str] = None,
        metric: Optional[str] = None,
        severity: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RegressionAlert]:
        """List stored alerts with optional filters."""
        conditions: List[str] = []
        params: List[Any] = []

        if model:
            conditions.append("model LIKE ? COLLATE NOCASE")
            params.append(f"%{model}%")
        if metric:
            conditions.append("metric = ?")
            params.append(metric)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.conn.execute(
            f"SELECT * FROM regression_alerts {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()

        return [
            RegressionAlert(
                model=row["model"],
                metric=row["metric"],
                severity=row["severity"],
                direction=row["direction"],
                confidence=row["confidence"],
                change_magnitude=row["change_magnitude"],
                previous_avg=row["previous_avg"],
                current_value=row["current_value"],
                baseline_std=row["baseline_std"],
                z_score=row["z_score"],
                window_size=row["window_size"],
                run_id=row["run_id"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]

    def stats(self) -> Dict[str, Any]:
        """Get aggregate alert stats."""
        rows = self.conn.execute(
            """
            SELECT
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END), 0) as critical,
                COALESCE(SUM(CASE WHEN severity = 'warning' THEN 1 ELSE 0 END), 0) as warning,
                COALESCE(SUM(CASE WHEN severity = 'info' THEN 1 ELSE 0 END), 0) as info,
                COALESCE(COUNT(DISTINCT model), 0) as model_count,
                COALESCE(COUNT(DISTINCT metric), 0) as metric_count,
                MAX(timestamp) as latest_alert
            FROM regression_alerts
            """
        ).fetchone()
        return dict(rows) if rows else {}


# ── Event bus integration ──────────────────────────────────────────


def subscribe_to_run_events(
    bus: Any,
    *,
    store_path: str = "results/metrics.db",
    window: int = 10,
    z_threshold: float = 2.0,
) -> None:
    """Subscribe to ``RunLifecycleEvent`` to auto-detect regressions after each run.

    When a run completes, queries MetricsStore for the model's recent
    metrics and checks for regressions.  Persists any alerts to AlertStore.

    Usage:
        from events import default_bus
        from core.regression import subscribe_to_run_events
        subscribe_to_run_events(default_bus)
    """
    from events import RunLifecycleEvent

    alert_store = AlertStore(store_path)

    def _on_run_completed(event: RunLifecycleEvent) -> None:
        if event.status != "completed":
            return
        model = event.model
        if not model:
            return

        from core.metrics_store import get_metrics_store

        ms = get_metrics_store(store_path)

        # Check all metrics that this model has data for
        metrics = ms.distinct_metrics(model=model)
        for metric in metrics:
            try:
                alerts = detect_regression(
                    ms,
                    model=model,
                    metric=metric,
                    window=window,
                    z_threshold=z_threshold,
                )
                for alert in alerts:
                    alert.run_id = event.run_id or ""
                    alert_store.store(alert)
                    # Also emit an ErrorEvent for critical regressions
                    if alert.severity == "critical":
                        from events import ErrorEvent

                        bus.emit_sync(
                            ErrorEvent(
                                message=f"Critical regression detected: {model}/{metric} "
                                f"dropped {alert.change_magnitude:.1f}% "
                                f"(z={alert.z_score:.1f})",
                                component="regression",
                                run_id=event.run_id or "",
                                severity="warning",
                            )
                        )
            except Exception:
                continue

    bus.subscribe(RunLifecycleEvent, _on_run_completed)


# ── Convenience functions ──────────────────────────────────────────

_alert_store_registry: Dict[str, AlertStore] = {}


def get_alert_store(db_path: str = "results/metrics.db") -> AlertStore:
    """Get or create a cached AlertStore instance for the given path.

    Returns the same instance for repeated calls with the same path,
    and a different instance for different paths.
    """
    global _alert_store_registry
    resolved = str(Path(db_path).resolve())
    if resolved not in _alert_store_registry:
        _alert_store_registry[resolved] = AlertStore(resolved)
    return _alert_store_registry[resolved]


__all__ = [
    "RegressionAlert",
    "detect_regression",
    "detect_all",
    "AlertStore",
    "subscribe_to_run_events",
    "get_alert_store",
]
