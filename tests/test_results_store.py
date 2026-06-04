#!/usr/bin/env python3
"""Smoke test for ResultsStore — validates schema, CRUD, and migration."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packages"))

from core.results_store import ResultsStore

passed = 0
failed = 0

# 1. In-memory store
print("1. In-memory store...")
s = ResultsStore(":memory:")
assert s.count() == 0, f"Expected 0, got {s.count()}"
passed += 1
print("   OK")

# 2. Insert
print("2. Insert...")
s.insert(
    id="run-test-1",
    model_id="qwen-3.5-9b",
    provider="lm-studio",
    workload_type="benchmark",
    workload_name="mmlu_pro",
    overall_score=0.89,
    tokens_per_sec=45.2,
    ttft_ms=150.0,
    memory_mb=1240.0,
    created_at="2024-06-01T12:00:00Z",
    git_sha="abc1234",
    git_branch="main",
)
assert s.count() == 1
passed += 1
print("   OK")

# 3. Get
print("3. Get...")
row = s.get("run-test-1")
assert row is not None, "Expected a row"
assert row["model_id"] == "qwen-3.5-9b"
assert row["overall_score"] == 0.89
passed += 1
print("   OK")

# 4. Upsert (update)
print("4. Upsert...")
s.upsert(
    id="run-test-1",
    model_id="qwen-3.5-9b",
    provider="lm-studio",
    workload_type="benchmark",
    workload_name="mmlu_pro",
    overall_score=0.95,
    created_at="2024-06-01T12:00:00Z",
)
row = s.get("run-test-1")
assert row["overall_score"] == 0.95
assert s.count() == 1  # Still 1 row
passed += 1
print("   OK")

# 5. Insert second row
print("5. Insert second row...")
s.insert(
    id="run-test-2",
    model_id="gemma-4-e4b",
    provider="ollama",
    workload_type="benchmark",
    workload_name="gsm8k",
    overall_score=0.76,
    created_at="2024-06-02T10:00:00Z",
)
assert s.count() == 2
passed += 1
print("   OK")

# 6. List
print("6. List...")
rows = s.list(limit=10)
assert len(rows) == 2
passed += 1
print("   OK")

# 7. List with model filter (case-insensitive)
print("7. List with model filter...")
rows = s.list(model_id="QWEN")
assert len(rows) == 1
assert rows[0]["model_id"] == "qwen-3.5-9b"
passed += 1
print("   OK")

# 8. Top models
print("8. Top models...")
top = s.top_models(limit=5)
assert len(top) == 2
assert top[0]["model_id"] == "qwen-3.5-9b"  # Higher score first
assert top[0]["best_score"] == 0.95
passed += 1
print("   OK")

# 9. Stats
print("9. Stats...")
stats = s.stats()
assert stats["total_runs"] == 2
assert stats["total_models"] == 2
passed += 1
print("   OK")

# 10. Delete
print("10. Delete...")
assert s.delete("run-test-2") is True
assert s.count() == 1
assert s.get("run-test-2") is None
assert s.delete("nonexistent") is False
passed += 1
print("    OK")

# 11. Migration from temporary JSON
print("11. Migration from JSON...")
with tempfile.TemporaryDirectory() as tmpdir:
    # Create results structure
    os.makedirs(os.path.join(tmpdir, "models", "qwen-3.5-9b"), exist_ok=True)

    # runs_index.json
    index = {
        "version": "1.0.0",
        "runs": [
            {
                "run_id": "run-migrate-1",
                "model": "llama3.2",
                "provider": "ollama",
                "workload_type": "benchmark",
                "workload_name": "humaneval",
                "overall_score": 0.72,
                "timestamp": "2024-07-01T08:00:00Z",
            }
        ],
    }
    with open(os.path.join(tmpdir, "runs_index.json"), "w") as f:
        json.dump(index, f)

    # Detail JSON file
    detail = {
        "run_id": "run-migrate-1",
        "performance": {
            "tokens_per_sec": 38.5,
            "ttft_ms": 200.0,
            "memory_pressure_mb": 980.0,
        },
    }
    # Save to the models subdirectory path
    model_dir = os.path.join(tmpdir, "models", "llama3.2")
    os.makedirs(model_dir, exist_ok=True)
    with open(os.path.join(model_dir, "run-migrate-1.json"), "w") as f:
        json.dump(detail, f)

    s2 = ResultsStore(":memory:")
    result = s2.migrate_from_json(results_dir=tmpdir)
    assert result["imported"] == 1, f"Expected 1 imported, got {result}"
    assert result["errors"] == 0
    row = s2.get("run-migrate-1")
    assert row["tokens_per_sec"] == 38.5
    assert row["provider"] == "ollama"
    s2.close()
    passed += 1
    print("    OK")

s.close()
print(f"\n✓ All {passed} tests passed, {failed} failed")
