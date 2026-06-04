"""
Results Store — SQLite-backed persistence for benchmark results.

Replaces the flat-file ``runs_index.json`` with an indexed SQLite database
for O(1) lookups, pagination, and efficient filtering.

Architecture:
    ResultsStore
      ├── insert(run)        → INSERT INTO runs
      ├── get(id)            → SELECT by primary key
      ├── list(model?, ...)  → SELECT with filters, LIMIT/OFFSET
      ├── delete(id)         → DELETE by primary key
      └── migrate_from_json()→ Bulk import from runs_index.json

Schema:
    runs (
        id            TEXT PRIMARY KEY,
        model_id      TEXT NOT NULL,
        provider      TEXT NOT NULL,
        workload_type TEXT NOT NULL,
        workload_name TEXT NOT NULL,
        overall_score REAL,
        tokens_per_sec REAL,
        ttft_ms       REAL,
        memory_mb     REAL,
        status        TEXT DEFAULT 'completed',
        config_json   TEXT,
        trace_path    TEXT,
        created_at    TEXT NOT NULL,
        git_sha       TEXT,
        git_branch    TEXT
    )

Usage:
    store = ResultsStore("results/runs.db")
    store.insert(
        run_id="run_20240601_123456_qwen-3.5-9b",
        model_id="qwen-3.5-9b-coder",
        provider="lm-studio",
        ...
    )
    runs = store.list(model_id="qwen-3.5-9b", limit=20)
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class ResultsStore:
    """SQLite-backed store for benchmark run metadata.

    Thread safety: this class is NOT thread-safe by default.  The
    connection uses ``check_same_thread=True`` (sqlite3 default).
    Use one instance per thread, or use a connection pool for
    concurrent access.
    """

    # Canonical column list — single source of truth for insert/upsert
    COLUMNS: tuple[str, ...] = (
        "id", "model_id", "provider", "workload_type", "workload_name",
        "overall_score", "tokens_per_sec", "ttft_ms", "memory_mb",
        "status", "config_json", "trace_path", "created_at",
        "git_sha", "git_branch",
    )

    def __init__(self, db_path: str | Path = "results/runs.db"):
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

    # ── Schema ──────────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        """Create tables and indexes if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id            TEXT PRIMARY KEY,
                model_id      TEXT NOT NULL,
                provider      TEXT NOT NULL,
                workload_type TEXT NOT NULL,
                workload_name TEXT NOT NULL,
                overall_score REAL,
                tokens_per_sec REAL,
                ttft_ms       REAL,
                memory_mb     REAL,
                status        TEXT NOT NULL DEFAULT 'completed',
                config_json   TEXT,
                trace_path    TEXT,
                created_at    TEXT NOT NULL,
                git_sha       TEXT,
                git_branch    TEXT,
                schema_version TEXT NOT NULL DEFAULT '1.0.0'
            );

            CREATE INDEX IF NOT EXISTS idx_runs_model
                ON runs(model_id);
            CREATE INDEX IF NOT EXISTS idx_runs_created
                ON runs(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_runs_score
                ON runs(overall_score DESC);
            CREATE INDEX IF NOT EXISTS idx_runs_workload
                ON runs(workload_type, workload_name);
            CREATE INDEX IF NOT EXISTS idx_runs_status
                ON runs(status);
        """)

    # ── CRUD ────────────────────────────────────────────────────────

    def _build_values(self, **kwargs: Any) -> tuple[dict[str, Any], list[str]]:
        """Build a values dict from keyword arguments for the canonical columns.

        Returns (values, columns_used) where columns_used only includes
        columns that were explicitly provided in kwargs — this prevents
        NULL overwrites on columns with DB-level defaults like
        ``schema_version``.
        """
        values: dict[str, Any] = {}
        columns_used: list[str] = []
        for col in self.COLUMNS:
            if col in kwargs:
                values[col] = kwargs[col]
                columns_used.append(col)
        return values, columns_used

    def insert(self, **kwargs: Any) -> None:
        """Insert a new run row. See module docstring for column names.

        Raises sqlite3.IntegrityError if a run with this ``id`` already exists.
        """
        values, columns_used = self._build_values(**kwargs)
        placeholders = ", ".join(f":{col}" for col in columns_used)

        self.conn.execute(
            f"INSERT INTO runs ({', '.join(columns_used)}) VALUES ({placeholders})",
            values,
        )
        self.conn.commit()

    def upsert(self, **kwargs: Any) -> None:
        """Insert or replace a run row (overwrites on conflict).

        Only columns explicitly provided in kwargs are upserted — columns
        not passed (e.g., ``schema_version``) keep their existing values
        or DB defaults.
        """
        values, columns_used = self._build_values(**kwargs)
        placeholders = ", ".join(f":{col}" for col in columns_used)
        updates = ", ".join(
            f"{col}=excluded.{col}" for col in columns_used if col != "id"
        )

        self.conn.execute(
            f"INSERT INTO runs ({', '.join(columns_used)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            values,
        )
        self.conn.commit()

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a single run by ID. Returns None if not found."""
        row = self.conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def list(
        self,
        model_id: str | None = None,
        provider: str | None = None,
        workload_type: str | None = None,
        workload_name: str | None = None,
        status: str | None = None,
        limit: int | None = 50,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> List[Dict[str, Any]]:
        """List runs with optional filters, pagination, and ordering.

        Args:
            model_id: Filter by model (case-insensitive LIKE).
            provider: Filter by provider name.
            workload_type: Filter by workload type.
            workload_name: Filter by workload name.
            status: Filter by run status.
            limit: Maximum rows (None = no limit).
            offset: Pagination offset.
            order_by: SQL ORDER BY clause.
        """
        conditions: List[str] = []
        params: List[Any] = []

        if model_id:
            conditions.append("model_id LIKE ? COLLATE NOCASE")
            params.append(f"%{model_id}%")
        if provider:
            conditions.append("provider = ?")
            params.append(provider)
        if workload_type:
            conditions.append("workload_type = ?")
            params.append(workload_type)
        if workload_name:
            conditions.append("workload_name = ?")
            params.append(workload_name)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_clause = f"LIMIT ?" if limit is not None else ""
        query = f"SELECT * FROM runs {where} ORDER BY {order_by} {limit_clause} OFFSET ?"

        if limit is not None:
            params.extend([limit, offset])
        else:
            params.append(offset)

        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def count(
        self,
        model_id: str | None = None,
        provider: str | None = None,
        status: str | None = None,
    ) -> int:
        """Count runs matching optional filters."""
        conditions: List[str] = []
        params: List[Any] = []

        if model_id:
            conditions.append("model_id LIKE ? COLLATE NOCASE")
            params.append(f"%{model_id}%")
        if provider:
            conditions.append("provider = ?")
            params.append(provider)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        row = self.conn.execute(
            f"SELECT COUNT(*) as cnt FROM runs {where}", params
        ).fetchone()
        return row["cnt"] if row else 0

    def delete(self, run_id: str) -> bool:
        """Delete a run by ID. Returns True if a row was deleted."""
        cursor = self.conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def latest(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent runs."""
        return self.list(limit=limit, order_by="created_at DESC")

    def top_models(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get models ordered by best overall_score."""
        rows = self.conn.execute("""
            SELECT
                model_id,
                MAX(overall_score) as best_score,
                COUNT(*) as run_count,
                provider
            FROM runs
            WHERE overall_score IS NOT NULL
            GROUP BY model_id
            ORDER BY best_score DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

    # ── Migration ───────────────────────────────────────────────────

    def migrate_from_json(
        self,
        results_dir: str | Path = "results",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Import runs from an existing ``runs_index.json`` and JSON result files.

        Args:
            results_dir: Path to the ``results/`` directory.
            dry_run: If True, return a diff without writing to the database.

        Returns:
            Dict with ``imported``, ``skipped``, and ``errors`` counts.
        """
        results_dir = Path(results_dir)
        index_path = results_dir / "runs_index.json"

        if not index_path.exists():
            return {"imported": 0, "skipped": 0, "errors": 0,
                    "message": f"No runs_index.json found at {index_path}"}

        with open(index_path) as f:
            index_data = json.load(f)

        runs = index_data.get("runs", [])
        if not runs:
            return {"imported": 0, "skipped": 0, "errors": 0,
                    "message": "runs_index.json contains no runs"}

        imported = 0
        skipped = 0
        errors = 0
        error_details: List[str] = []

        for run in runs:
            run_id = run.get("run_id", "")
            if not run_id:
                skipped += 1
                continue

            # Check for detail JSON file
            detail_path = None
            for pattern in [
                results_dir / f"{run_id}.json",
                results_dir / "models" / run.get("model", "") / f"{run_id}.json",
            ]:
                if pattern.exists():
                    detail_path = pattern
                    break

            try:
                row = self._run_index_to_row(run, detail_path)

                if dry_run:
                    imported += 1
                else:
                    self.upsert(**row)
                    imported += 1
            except Exception as exc:
                errors += 1
                error_details.append(f"{run_id}: {exc}")

        if not dry_run:
            self.conn.commit()

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "total": len(runs),
            "error_details": error_details[:10],  # Truncate for readability
        }

    def _run_index_to_row(
        self,
        run: Dict[str, Any],
        detail_path: Path | None,
    ) -> Dict[str, Any]:
        """Convert a runs_index.json entry + optional detail JSON to a DB row."""
        row: Dict[str, Any] = {
            "id": run.get("run_id", ""),
            "model_id": run.get("model", ""),
            "provider": run.get("provider", ""),
            "workload_type": run.get("workload_type", "benchmark"),
            "workload_name": run.get("workload_name", ""),
            "overall_score": run.get("overall_score"),
            "status": run.get("status", "completed"),
            "created_at": run.get("timestamp", ""),
            "git_sha": run.get("git_sha"),
            "git_branch": run.get("git_branch"),
        }

        # If a detail JSON file exists, enrich from it
        if detail_path and detail_path.exists():
            try:
                with open(detail_path) as f:
                    detail = json.load(f)
            except (json.JSONDecodeError, OSError):
                detail = {}

            perf = detail.get("performance", {})
            row["tokens_per_sec"] = perf.get("tokens_per_sec")
            row["ttft_ms"] = perf.get("ttft_ms")
            row["memory_mb"] = perf.get("memory_pressure_mb")

            # Snapshot the config for reproducibility
            config = detail.get("config_snapshot")
            if config:
                row["config_json"] = json.dumps(config)

            trace = detail.get("trace_file") or detail.get("trace_id")
            if trace:
                row["trace_path"] = str(trace)

        return row

    # ── Aggregate queries ───────────────────────────────────────────

    def stats(self, model_id: str | None = None) -> Dict[str, Any]:
        """Get aggregate statistics across all (or filtered) runs."""
        conditions = ""
        params: Sequence[Any] = ()
        if model_id:
            conditions = "WHERE model_id LIKE ?"
            params = (f"%{model_id}%",)

        row = self.conn.execute(f"""
            SELECT
                COUNT(*) as total_runs,
                COUNT(DISTINCT model_id) as total_models,
                AVG(overall_score) as avg_score,
                AVG(tokens_per_sec) as avg_tps,
                AVG(ttft_ms) as avg_ttft,
                MIN(created_at) as first_run,
                MAX(created_at) as last_run
            FROM runs
            {conditions}
        """, params).fetchone()

        return dict(row) if row else {}


# ── Convenience ────────────────────────────────────────────────────


def open_store(db_path: str = "results/runs.db") -> ResultsStore:
    """Open a ResultsStore at the given path.

    The caller is responsible for calling ``store.close()`` when done.
    For use as a context manager, see :class:`ResultsStoreContext`.
    """
    return ResultsStore(db_path)


class ResultsStoreContext:
    """Context manager for ResultsStore — auto-closes on exit."""

    def __init__(self, db_path: str = "results/runs.db"):
        self.store = ResultsStore(db_path)

    def __enter__(self) -> ResultsStore:
        return self.store

    def __exit__(self, *args: Any) -> None:
        self.store.close()
