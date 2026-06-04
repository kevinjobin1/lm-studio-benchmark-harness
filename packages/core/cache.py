"""
Content-Addressable Cache for benchmark/workload results.

Cache keys are SHA-256 hashes of the inputs that produced the result:
  key = sha256(model + provider + task_prompt + config_json)

Results are stored as JSON files in ``results/cache/`` with a two-level
directory prefix (first 2 hex chars of the key → subdirectory) to avoid
filesystem issues with large directories.

Usage:
    cache = ContentAddressableCache()
    key = cache.make_key(model="qwen3.5-9b", task="Implement auth", config={"temp": 0.2})
    if cache.has(key):
        result = cache.get(key)
    else:
        result = run_expensive(model)
        cache.put(key, result)
"""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class ContentAddressableCache:
    """SHA-256 content-addressed cache for benchmark/workload results.

    Thread safety: this class is safe for single-threaded use.
    For concurrent access, use one instance per thread with the same
    ``cache_dir`` (file-level locking is not implemented since cache
    writes are idempotent — last writer wins).
    """

    def __init__(self, cache_dir: str | Path = "results/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Key generation ─────────────────────────────────────────────

    @staticmethod
    def make_key(**components: Any) -> str:
        """Generate a deterministic SHA-256 content key from input components.

        Args:
            **components: Named input components that determine the result.
                          Typical keys: model, provider, task, config, prompt.

        Returns:
            64-char hex SHA-256 digest.
        """
        # Sort keys for deterministic ordering
        sorted_str = json.dumps(components, sort_keys=True, default=str)
        return hashlib.sha256(sorted_str.encode()).hexdigest()

    # ── Path helpers ───────────────────────────────────────────────

    def _key_to_path(self, key: str) -> Path:
        """Convert a 64-char hex key to a file path with directory prefix."""
        if len(key) < 4:
            raise ValueError(f"Cache key too short: {key}")
        subdir = self.cache_dir / key[:2] / key[2:4]
        subdir.mkdir(parents=True, exist_ok=True)
        return subdir / f"{key}.json"

    # ── CRUD ───────────────────────────────────────────────────────

    def put(self, key: str, data: Any, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store a value in the cache.

        Args:
            key: 64-char hex content key.
            data: JSON-serializable result data to cache.
            metadata: Optional extra metadata (e.g., model name, timestamp).

        Returns:
            The file path where the cache entry was written.
        """
        path = self._key_to_path(key)
        entry = {
            "_meta": {
                "key": key,
                "created_at": time.time(),
                "format_version": "1.0",
            },
            "data": data,
        }
        if metadata:
            entry["_meta"].update(metadata)

        with open(path, "w") as f:
            json.dump(entry, f, indent=2, default=str, ensure_ascii=False)
        return str(path)

    def get(self, key: str) -> Optional[Any]:
        """Retrieve cached data by key.

        Args:
            key: 64-char hex content key.

        Returns:
            The cached data dict, or None if not found.
        """
        path = self._key_to_path(key)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                entry = json.load(f)
            return entry.get("data")
        except (json.JSONDecodeError, OSError):
            return None

    def get_entry(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve the full cache entry (data + metadata) by key.

        Args:
            key: 64-char hex content key.

        Returns:
            The full entry dict with _meta and data, or None.
        """
        path = self._key_to_path(key)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def has(self, key: str) -> bool:
        """Check if a cache entry exists for the given key."""
        return self._key_to_path(key).exists()

    def remove(self, key: str) -> bool:
        """Remove a single cache entry. Returns True if deleted."""
        path = self._key_to_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    # ── Bulk operations ────────────────────────────────────────────

    def clear(self) -> int:
        """Remove all cached entries.

        Returns:
            Number of entries removed.
        """
        count = 0
        if self.cache_dir.exists():
            for path in self.cache_dir.rglob("*.json"):
                path.unlink()
                count += 1
            # Clean up empty subdirectories
            for root, dirs, files in os.walk(self.cache_dir, topdown=False):
                for d in dirs:
                    dir_path = Path(root) / d
                    try:
                        dir_path.rmdir()
                    except OSError:
                        pass
        return count

    def status(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with total_entries, total_size_bytes, oldest_entry,
            newest_entry, cache_dir.
        """
        total_entries = 0
        total_size = 0
        oldest: Optional[float] = None
        newest: Optional[float] = None

        for path in self.cache_dir.rglob("*.json"):
            total_entries += 1
            total_size += path.stat().st_size
            try:
                with open(path) as f:
                    entry = json.load(f)
                created = entry.get("_meta", {}).get("created_at", 0.0)
                if oldest is None or created < oldest:
                    oldest = created
                if newest is None or created > newest:
                    newest = created
            except (json.JSONDecodeError, OSError):
                pass

        return {
            "cache_dir": str(self.cache_dir.resolve()),
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest_entry": oldest,
            "newest_entry": newest,
            "entries_exist": total_entries > 0,
        }

    def list_entries(self) -> List[Dict[str, Any]]:
        """List all cache entries with their metadata.

        Returns:
            List of dicts with key, size_bytes, created_at.
        """
        entries: List[Dict[str, Any]] = []
        for path in sorted(self.cache_dir.rglob("*.json")):
            key = path.stem
            try:
                entry = self.get_entry(key)
                meta = entry.get("_meta", {}) if entry else {}
                created = meta.get("created_at", 0.0)
                try:
                    created_str = time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(created)
                    )
                except Exception:
                    created_str = str(created)
                entries.append({
                    "key": key,
                    "size_bytes": path.stat().st_size,
                    "created_at": created_str,
                    "created_timestamp": created,
                    "metadata": {k: v for k, v in meta.items() if k != "key"},
                })
            except Exception:
                entries.append({
                    "key": key,
                    "size_bytes": path.stat().st_size,
                    "created_at": "unknown",
                    "created_timestamp": 0,
                    "metadata": {},
                })
        return entries


# ── Convenience ────────────────────────────────────────────────────


def open_cache(cache_dir: str = "results/cache") -> ContentAddressableCache:
    """Open a content-addressable cache at the given directory."""
    return ContentAddressableCache(cache_dir)


def cache_result(
    cache_dir: str,
    result_key: str,
    result_data: Any,
    **metadata: Any,
) -> None:
    """One-shot cache write helper.

    Args:
        cache_dir: Path to the cache directory.
        result_key: Cache key (64-char hex SHA-256).
        result_data: JSON-serializable result to cache.
        **metadata: Extra metadata to store alongside the result.
    """
    cache = ContentAddressableCache(cache_dir)
    cache.put(result_key, result_data, metadata=metadata)


def load_cached(
    cache_dir: str,
    result_key: str,
) -> Optional[Any]:
    """One-shot cache read helper.

    Args:
        cache_dir: Path to the cache directory.
        result_key: Cache key (64-char hex SHA-256).

    Returns:
        Cached data or None.
    """
    cache = ContentAddressableCache(cache_dir)
    return cache.get(result_key)
