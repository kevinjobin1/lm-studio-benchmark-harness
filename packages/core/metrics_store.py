"""
Metrics Store — SQLite-backed time-series metrics store.

Captures every ``MetricEvent`` emitted during benchmark runs into an
indexed SQLite database, enabling fast time-series queries from the
dashboard without parsing JSON files.

Schema:
    metrics (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,       -- e.g. "tokens_per_second", "ttft_ms"
        value       REAL NOT NULL,
        unit        TEXT DEFAULT '',      -- e.g. "tokens/s", "ms", "MB"
        tags_json   TEXT DEFAULT '{}',    -- JSON blob: {model, provider, workload, ...}
        model       TEXT DEFAULT '',
        run_id      TEXT DEFAULT '',
        source      TEXT DEFAULT '',
        timestamp_ms INTEGER,            -- Unix milliseconds for time-series precision
        created_at  TEXT NOT NULL        -- ISO 8601
    );

Usage:
    store = MetricsStore("results/metrics.db")
    store.record("tokens_per_second", 72.3, model="qwen-3.5-9b", run_id="run_abc")

    # Query last 100 metrics
    series = store.query(metric="tokens_per_second", model="qwen-3.5-9b", limit=100)

    # Get aggregated stats
    stats = store.stats(metric="tokens_per_second", model="qwen-3.5-9b")
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class MetricsStore:
    """SQLite-backed time-series store for numeric metrics.

    Thread safety: NOT thread-safe by default (check_same_thread=True).
    Use one instance per thread or a connection pool for concurrent access.

    Args:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str | Path = "results/metrics.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    # ── Connection management ──────────────────────────────────────

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy connection with WAL mode enabled."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._conn.row_factory = sqlite3.Row
            self._ensure_schema()
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ── Schema ──────────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        """Create tables and indexes if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS metrics (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                value       REAL NOT NULL,
                unit        TEXT DEFAULT '',
                tags_json   TEXT DEFAULT '{}',
                model       TEXT DEFAULT '',
                run_id      TEXT DEFAULT '',
                source      TEXT DEFAULT '',
                timestamp_ms INTEGER,
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_metrics_name
                ON metrics(name);
            CREATE INDEX IF NOT EXISTS idx_metrics_model
                ON metrics(model);
            CREATE INDEX IF NOT EXISTS idx_metrics_created
                ON metrics(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_metrics_name_created
                ON metrics(name, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_metrics_model_name
                ON metrics(model, name, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_metrics_run_id
                ON metrics(run_id);
        """)

    # ── Write ───────────────────────────────────────────────────────

    def record(
        self,
        name: str,
        value: float,
        *,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None,
        model: str = "",
        run_id: str = "",
        source: str = "",
        timestamp_ms: Optional[int] = None,
    ) -> int:
        """Record a single metric value.

        Returns the row ID of the inserted record.
        """
        now = datetime.now(timezone.utc)
        self.conn.execute(
            """
            INSERT INTO metrics (name, value, unit, tags_json, model, run_id, source, timestamp_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                value,
                unit,
                json.dumps(tags or {}),
                model,
                run_id,
                source,
                timestamp_ms or int(now.timestamp() * 1000),
                now.isoformat(),
            ),
        )
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def record_batch(
        self,
        metrics: List[Dict[str, Any]],
    ) -> int:
        """Insert multiple metrics in a single transaction.

        Each dict should have keys: name, value.
        Optional keys: unit, tags, model, run_id, source, timestamp_ms.

        Returns the number of rows inserted.
        """
        now = datetime.now(timezone.utc)
        now_ts = int(now.timestamp() * 1000)
        now_iso = now.isoformat()

        rows = []
        for m in metrics:
            rows.append((
                m["name"],
                m["value"],
                m.get("unit", ""),
                json.dumps(m.get("tags", {})),
                m.get("model", ""),
                m.get("run_id", ""),
                m.get("source", ""),
                m.get("timestamp_ms", now_ts),
                m.get("created_at", now_iso),
            ))

        self.conn.executemany(
            """
            INSERT INTO metrics (name, value, unit, tags_json, model, run_id, source, timestamp_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()
        return len(rows)

    # ── Query ───────────────────────────────────────────────────────

    def query(
        self,
        *,
        metric: Optional[str] = None,
        model: Optional[str] = None,
        run_id: Optional[str] = None,
        source: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order: str = "DESC",
    ) -> List[Dict[str, Any]]:
        """Query metric time-series data with optional filters.

        Args:
            metric: Filter by metric name (e.g. "tokens_per_second").
            model: Filter by model (case-insensitive LIKE).
            run_id: Filter by specific run.
            source: Filter by source component.
            since: ISO 8601 datetime — only return records after this.
            until: ISO 8601 datetime — only return records before this.
            limit: Maximum rows to return.
            offset: Pagination offset.
            order: "ASC" or "DESC" for chronological/reverse order.

        Returns:
            List of dicts with keys: id, name, value, unit, tags_json,
            model, run_id, source, timestamp_ms, created_at.
        """
        conditions: List[str] = []
        params: List[Any] = []

        if metric:
            conditions.append("name = ?")
            params.append(metric)
        if model:
            conditions.append("model LIKE ? COLLATE NOCASE")
            params.append(f"%{model}%")
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if since:
            conditions.append("created_at >= ?")
            params.append(since)
        if until:
            conditions.append("created_at <= ?")
            params.append(until)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order_clause = "DESC" if order.upper() == "DESC" else "ASC"

        rows = self.conn.execute(
            f"SELECT * FROM metrics {where} ORDER BY created_at {order_clause}, id {order_clause} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [dict(row) for row in rows]

    def count(
        self,
        *,
        metric: Optional[str] = None,
        model: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> int:
        """Count metrics matching optional filters."""
        conditions: List[str] = []
        params: List[Any] = []

        if metric:
            conditions.append("name = ?")
            params.append(metric)
        if model:
            conditions.append("model LIKE ? COLLATE NOCASE")
            params.append(f"%{model}%")
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        row = self.conn.execute(
            f"SELECT COUNT(*) as cnt FROM metrics {where}", params
        ).fetchone()
        return row["cnt"] if row else 0

    def distinct_metrics(self, model: Optional[str] = None) -> List[str]:
        """List distinct metric names, optionally filtered by model."""
        if model:
            rows = self.conn.execute(
                "SELECT DISTINCT name FROM metrics WHERE model LIKE ? COLLATE NOCASE ORDER BY name",
                (f"%{model}%",),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT DISTINCT name FROM metrics ORDER BY name"
            ).fetchall()
        return [row["name"] for row in rows]

    def distinct_models(self) -> List[str]:
        """List distinct model names that have metrics."""
        rows = self.conn.execute(
            "SELECT DISTINCT model FROM metrics WHERE model != '' ORDER BY model"
        ).fetchall()
        return [row["model"] for row in rows]

    # ── Aggregate queries ───────────────────────────────────────────

    def stats(
        self,
        *,
        metric: str,
        model: Optional[str] = None,
        run_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregate statistics for a specific metric.

        Returns avg, min, max, count, sum, p50 (median), p95, p99.

        Note: Percentiles use SQLite's ``PERCENTILE`` which requires
        the ``math`` extension or in-memory calculation.  We compute
        p50/p95/p99 in Python for portability.
        """
        conditions: List[str] = ["name = ?"]
        params: List[Any] = [metric]

        if model:
            conditions.append("model LIKE ? COLLATE NOCASE")
            params.append(f"%{model}%")
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)
        if since:
            conditions.append("created_at >= ?")
            params.append(since)
        if until:
            conditions.append("created_at <= ?")
            params.append(until)

        where = f"WHERE {' AND '.join(conditions)}"

        # Basic aggregates from SQL
        agg_row = self.conn.execute(
            f"""
            SELECT
                COUNT(*) as count,
                AVG(value) as avg,
                MIN(value) as min,
                MAX(value) as max,
                SUM(value) as sum,
                COUNT(DISTINCT model) as model_count,
                COUNT(DISTINCT run_id) as run_count
            FROM metrics {where}
            """,
            params,
        ).fetchone()

        if not agg_row or agg_row["count"] == 0:
            return {
                "metric": metric,
                "count": 0,
                "avg": None,
                "min": None,
                "max": None,
                "sum": None,
                "p50": None,
                "p95": None,
                "p99": None,
                "model_count": 0,
                "run_count": 0,
            }

        # Compute percentiles in Python from ordered values
        values_rows = self.conn.execute(
            f"SELECT value FROM metrics {where} ORDER BY value ASC",
            params,
        ).fetchall()
        values = [r["value"] for r in values_rows]
        n = len(values)

        def percentile(sorted_vals: List[float], p: float) -> float:
            """Linear interpolation percentile."""
            if not sorted_vals:
                return 0.0
            k = (p / 100.0) * (n - 1)
            f = int(k)
            c = k - f
            if f + 1 < n:
                return sorted_vals[f] * (1 - c) + sorted_vals[f + 1] * c
            return sorted_vals[-1]

        return {
            "metric": metric,
            "count": agg_row["count"],
            "avg": round(agg_row["avg"], 4) if agg_row["avg"] is not None else None,
            "min": round(agg_row["min"], 4) if agg_row["min"] is not None else None,
            "max": round(agg_row["max"], 4) if agg_row["max"] is not None else None,
            "sum": round(agg_row["sum"], 4) if agg_row["sum"] is not None else None,
            "p50": round(percentile(values, 50), 4),
            "p95": round(percentile(values, 95), 4),
            "p99": round(percentile(values, 99), 4),
            "model_count": agg_row["model_count"],
            "run_count": agg_row["run_count"],
        }

    def time_bucket(
        self,
        *,
        metric: str,
        model: Optional[str] = None,
        bucket_seconds: int = 3600,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregate metric values into time buckets.

        Useful for time-series charts (line charts, area charts).

        Args:
            metric: Metric name to aggregate.
            model: Optional model filter.
            bucket_seconds: Bucket width in seconds (default: 1 hour).
            since: ISO 8601 start time.
            until: ISO 8601 end time.

        Returns:
            List of dicts with keys: bucket (ISO 8601), avg, min, max, count.
        """
        conditions: List[str] = ["name = ?"]
        params: List[Any] = [metric]

        if model:
            conditions.append("model LIKE ? COLLATE NOCASE")
            params.append(f"%{model}%")
        if since:
            conditions.append("created_at >= ?")
            params.append(since)
        if until:
            conditions.append("created_at <= ?")
            params.append(until)

        where = f"WHERE {' AND '.join(conditions)}"

        # SQLite doesn't have date_trunc, so we compute bucket boundaries
        # by dividing timestamp_ms by bucket_seconds*1000 and flooring.
        bucket_ms = bucket_seconds * 1000
        rows = self.conn.execute(
            f"""
            SELECT
                (CAST(timestamp_ms AS INTEGER) / {bucket_ms}) * {bucket_ms} AS bucket_epoch,
                COUNT(*) as count,
                AVG(value) as avg,
                MIN(value) as min,
                MAX(value) as max
            FROM metrics {where}
            GROUP BY bucket_epoch
            ORDER BY bucket_epoch ASC
            """,
            params,
        ).fetchall()

        result = []
        for row in rows:
            bucket_dt = datetime.fromtimestamp(row["bucket_epoch"] / 1000, tz=timezone.utc)
            result.append({
                "bucket": bucket_dt.isoformat(),
                "count": row["count"],
                "avg": round(row["avg"], 4) if row["avg"] is not None else None,
                "min": round(row["min"], 4) if row["min"] is not None else None,
                "max": round(row["max"], 4) if row["max"] is not None else None,
            })
        return result

    def latest_values(
        self,
        *,
        metrics: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get the latest value for each metric, optionally filtered by model.

        Returns dict like {"tokens_per_second": 72.3, "ttft_ms": 340, ...}.
        """
        if metrics:
            placeholders = ", ".join("?" for _ in metrics)
            model_cond = "AND model LIKE ? COLLATE NOCASE" if model else ""
            model_params = [f"%{model}%"] if model else []
            rows = self.conn.execute(
                f"""
                SELECT name, value FROM metrics
                WHERE id IN (
                    SELECT MAX(id) FROM metrics
                    WHERE name IN ({placeholders}) {model_cond}
                    GROUP BY name
                )
                """,
                [*metrics, *model_params],
            ).fetchall()
        else:
            if model:
                rows = self.conn.execute(
                    """
                    SELECT name, value FROM metrics
                    WHERE id IN (
                        SELECT MAX(id) FROM metrics
                        WHERE model LIKE ? COLLATE NOCASE
                        GROUP BY name
                    )
                    """,
                    (f"%{model}%",),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """
                    SELECT name, value FROM metrics
                    WHERE id IN (
                        SELECT MAX(id) FROM metrics GROUP BY name
                    )
                    """
                ).fetchall()

        return {row["name"]: row["value"] for row in rows}

    # ── Lifecycle ───────────────────────────────────────────────────

    def clear(self, older_than_days: Optional[int] = None) -> int:
        """Clear metrics data.

        Args:
            older_than_days: If set, only remove records older than this.

        Returns:
            Number of rows deleted.
        """
        if older_than_days is not None:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
            cursor = self.conn.execute("DELETE FROM metrics WHERE created_at < ?", (cutoff,))
        else:
            cursor = self.conn.execute("DELETE FROM metrics")
        self.conn.commit()
        return cursor.rowcount

    def vacuum(self) -> None:
        """Reclaim disk space. Run after large deletions."""
        self.conn.execute("VACUUM;")


# ── MetricEvent bus subscriber ──────────────────────────────────────

# Global MetricsStore instance for the default event bus subscription.
# Lazy-initialized to avoid filesystem side effects at import time.
_default_store: Optional[MetricsStore] = None


def get_metrics_store(db_path: str = "results/metrics.db") -> MetricsStore:
    """Get or create the default MetricsStore instance."""
    global _default_store
    if _default_store is None:
        _default_store = MetricsStore(db_path)
    return _default_store


def subscribe_to_event_bus(bus: Any, db_path: str = "results/metrics.db") -> None:
    """Subscribe the MetricsStore to all MetricEvents on the given EventBus.

    Usage:
        from events import default_bus
        from core.metrics_store import subscribe_to_event_bus
        subscribe_to_event_bus(default_bus)
    """
    from events import MetricEvent

    store = get_metrics_store(db_path)

    def _on_metric(event: MetricEvent) -> None:
        store.record(
            name=event.name,
            value=event.value,
            unit=event.unit,
            tags=event.tags,
            model=event.model,
            run_id=event.run_id,
            source=event.source,
        )

    bus.subscribe(MetricEvent, _on_metric)


__all__ = [
    "MetricsStore",
    "get_metrics_store",
    "subscribe_to_event_bus",
]
