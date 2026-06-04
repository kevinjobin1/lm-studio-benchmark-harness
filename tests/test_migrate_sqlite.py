"""
Integration tests for ``modellens migrate sqlite``.

Creates a temporary directory with sample ``runs_index.json`` and
per-run detail JSON files, then invokes the CLI command to verify:

- ``--dry-run`` correctly reports imported/skipped/errors without writing
- Full migration writes the expected rows to SQLite
- Edge cases: empty index, missing detail files, malformed JSON
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from apps.cli.modellens import cli
from core.results_store import ResultsStore


# ── Sample data ──────────────────────────────────────────────────

SAMPLE_INDEX = {
    "version": "1.0.0",
    "generated_at": "2025-01-15T12:00:00Z",
    "runs": [
        {
            "run_id": "run_qwen_20250115_123456",
            "model": "qwen3.5-9b-coder",
            "provider": "lm-studio",
            "workload_type": "benchmark",
            "workload_name": "mmlu_pro",
            "overall_score": 0.725,
            "status": "completed",
            "timestamp": "2025-01-15T12:34:56Z",
            "git_sha": "abc123",
            "git_branch": "main",
        },
        {
            "run_id": "run_llama_20250115_124500",
            "model": "llama3.2-3b",
            "provider": "ollama",
            "workload_type": "benchmark",
            "workload_name": "gsm8k",
            "overall_score": 0.645,
            "status": "completed",
            "timestamp": "2025-01-15T12:45:00Z",
            "git_sha": "abc123",
            "git_branch": "main",
        },
        {
            "run_id": "run_gemma_20250115_130000",
            "model": "gemma-4-9b",
            "provider": "lm-studio",
            "workload_type": "benchmark",
            "workload_name": "humaneval",
            "overall_score": 0.812,
            "status": "completed",
            "timestamp": "2025-01-15T13:00:00Z",
        },
        # Run with no run_id (should be skipped)
        {
            "model": "skip-model",
            "provider": "vllm",
            "status": "completed",
            "timestamp": "2025-01-15T13:00:00Z",
        },
    ],
}

SAMPLE_DETAIL = {
    "performance": {
        "tokens_per_sec": 42.5,
        "ttft_ms": 340.0,
        "memory_pressure_mb": 4096.0,
    },
    "config_snapshot": {
        "temperature": 0.2,
        "max_tokens": 1000,
    },
}


class TestMigrateSQLite(unittest.TestCase):
    """Integration tests for the ``modellens migrate sqlite`` command."""

    def setUp(self):
        self.runner = CliRunner()
        # Create a temp directory for test results
        self.test_dir = Path(tempfile.mkdtemp(prefix="modellens_migrate_test_"))
        self.results_dir = self.test_dir / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write_runs_index(self, runs_index: dict):
        """Write runs_index.json to the test results directory."""
        path = self.results_dir / "runs_index.json"
        with open(path, "w") as f:
            json.dump(runs_index, f, indent=2)
        return path

    def _write_detail(self, run_id: str, detail: dict = None):
        """Write a per-run detail JSON file."""
        if detail is None:
            detail = SAMPLE_DETAIL
        path = self.results_dir / f"{run_id}.json"
        with open(path, "w") as f:
            json.dump(detail, f, indent=2)
        return path

    def _db_path(self) -> str:
        return str(self.test_dir / "runs.db")

    # ── Tests ───────────────────────────────────────────────────

    def test_migrate_dry_run(self):
        """Dry-run should report correct counts without writing to the DB."""
        self._write_runs_index(SAMPLE_INDEX)
        self._write_detail("run_qwen_20250115_123456")
        self._write_detail("run_llama_20250115_124500")
        # No detail for run_gemma — should still import (with fewer fields)

        db = self._db_path()
        result = self.runner.invoke(
            cli,
            [
                "migrate",
                "sqlite",
                "--dry-run",
                "--results", str(self.results_dir),
                "--db", db,
            ],
        )

        self.assertEqual(result.exit_code, 0, msg=result.output)

        # Verify output
        self.assertIn("DRY RUN", result.output)
        self.assertIn("Total runs in index:  4", result.output)
        self.assertIn("Imported:             3", result.output)  # 4 total, 1 skipped
        self.assertIn("Skipped (no run_id):  1", result.output)
        self.assertIn("Errors:               0", result.output)

        # DB should not exist (dry run)
        self.assertFalse(os.path.exists(db), "DB file should not exist after dry run")

    def test_migrate_full(self):
        """Full migration should write rows to SQLite."""
        self._write_runs_index(SAMPLE_INDEX)
        self._write_detail("run_qwen_20250115_123456")

        db = self._db_path()
        result = self.runner.invoke(
            cli,
            [
                "migrate",
                "sqlite",
                "--results", str(self.results_dir),
                "--db", db,
            ],
        )

        self.assertEqual(result.exit_code, 0, msg=result.output)

        # Verify output
        self.assertIn("Total runs in index:  4", result.output)
        self.assertIn("Imported:             3", result.output)
        self.assertIn("Rows in database:     3", result.output)

        # DB should exist and have the right rows
        self.assertTrue(os.path.exists(db))
        store = ResultsStore(db)
        rows = store.list(limit=100)
        store.close()

        self.assertEqual(len(rows), 3)

        # Verify first row (with detail enrichment)
        qwen = [r for r in rows if r["id"] == "run_qwen_20250115_123456"]
        self.assertEqual(len(qwen), 1)
        self.assertEqual(qwen[0]["model_id"], "qwen3.5-9b-coder")
        self.assertEqual(qwen[0]["provider"], "lm-studio")
        self.assertEqual(qwen[0]["tokens_per_sec"], 42.5)
        self.assertEqual(qwen[0]["ttft_ms"], 340.0)
        self.assertEqual(qwen[0]["overall_score"], 0.725)

        # Verify row with no detail (should still have basic fields)
        gemma = [r for r in rows if r["id"] == "run_gemma_20250115_130000"]
        self.assertEqual(len(gemma), 1)
        self.assertEqual(gemma[0]["model_id"], "gemma-4-9b")
        self.assertIsNone(gemma[0]["tokens_per_sec"])  # No detail file
        self.assertIsNone(gemma[0]["ttft_ms"])

        # Config JSON should be set (from detail)
        qwen_config = json.loads(qwen[0]["config_json"]) if qwen[0]["config_json"] else {}
        self.assertEqual(qwen_config.get("temperature"), 0.2)

    def test_migrate_dry_run_empty_index(self):
        """Empty index should report no runs."""
        empty_index = {"version": "1.0.0", "runs": []}
        self._write_runs_index(empty_index)

        db = self._db_path()
        result = self.runner.invoke(
            cli,
            [
                "migrate",
                "sqlite",
                "--dry-run",
                "--results", str(self.results_dir),
                "--db", db,
            ],
        )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("contains no runs", result.output)

    def test_migrate_dry_run_no_index(self):
        """Missing runs_index.json should report a message."""
        db = self._db_path()
        result = self.runner.invoke(
            cli,
            [
                "migrate",
                "sqlite",
                "--dry-run",
                "--results", str(self.results_dir),
                "--db", db,
            ],
        )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("No runs_index.json found", result.output)

    def test_migrate_with_errors(self):
        """Runs with corrupt detail JSON should still import with errors."""
        self._write_runs_index(SAMPLE_INDEX)
        # Write a corrupt detail file
        corrupt_path = self.results_dir / "run_qwen_20250115_123456.json"
        corrupt_path.write_text("this is not valid json{{{")

        db = self._db_path()
        result = self.runner.invoke(
            cli,
            [
                "migrate",
                "sqlite",
                "--dry-run",
                "--results", str(self.results_dir),
                "--db", db,
            ],
        )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        # The run should still be imported (corrupt detail just means no enrichment)
        self.assertIn("Imported:             3", result.output)


if __name__ == "__main__":
    unittest.main()
