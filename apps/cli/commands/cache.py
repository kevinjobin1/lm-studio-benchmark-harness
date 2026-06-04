"""
Cache management commands for modellens CLI.

Manages the content-addressable benchmark result cache:
  - status: show cache size, entry count, oldest/newest
  - clear:  remove all cached entries
  - inspect <key>: show a specific cache entry
  - config: show/hide cache directory path configuration
"""

import json
import sys
from pathlib import Path

import click
from rich.table import Table

from .utils import _echo, RICH_AVAILABLE, console


DEFAULT_CACHE_DIR = "results/cache"


@click.group()
def cache():
    """
    Manage the benchmark result cache (content-addressable).

    Caches model responses by SHA-256 hash of the input (model,
    provider, task prompt, config) to avoid re-running identical
    benchmarks.

    \b
    Examples:
      modellens cache status
      modellens cache clear
      modellens cache inspect <key>
    """
    pass


@cache.command(name="status")
@click.option(
    "--cache-dir",
    default=DEFAULT_CACHE_DIR,
    show_default=True,
    help="Cache directory path",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def cache_status(cache_dir, json_output):
    """Show cache statistics: entry count, size, oldest/newest."""
    from core.cache import ContentAddressableCache

    c = ContentAddressableCache(cache_dir)
    stats = c.status()

    if json_output:
        click.echo(json.dumps(stats, indent=2, default=str))
        return

    _echo("")
    _echo("📦 Benchmark Cache Status", "bold blue")
    _echo(f"   Cache directory: {stats['cache_dir']}", "dim")

    if not stats["entries_exist"]:
        _echo("   ℹ  Cache is empty.", "dim")
        _echo("")
        return

    _echo(f"   Total entries:    {stats['total_entries']}", "bold")
    _echo(f"   Total size:       {stats['total_size_mb']} MB ({stats['total_size_bytes']} bytes)", "dim")

    if stats["oldest_entry"]:
        from datetime import datetime
        oldest = datetime.fromtimestamp(stats["oldest_entry"]).strftime("%Y-%m-%d %H:%M:%S")
        _echo(f"   Oldest entry:     {oldest}", "dim")

    if stats["newest_entry"]:
        from datetime import datetime
        newest = datetime.fromtimestamp(stats["newest_entry"]).strftime("%Y-%m-%d %H:%M:%S")
        _echo(f"   Newest entry:     {newest}", "dim")

    _echo("")


@cache.command(name="list")
@click.option(
    "--cache-dir",
    default=DEFAULT_CACHE_DIR,
    show_default=True,
    help="Cache directory path",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--limit", type=int, default=20, help="Max entries to show")
def cache_list(cache_dir, json_output, limit):
    """List cache entries with metadata (key, size, created_at)."""
    from core.cache import ContentAddressableCache

    c = ContentAddressableCache(cache_dir)
    entries = c.list_entries()

    # Sort by created_timestamp descending (newest first)
    entries.sort(key=lambda e: e.get("created_timestamp", 0), reverse=True)
    entries = entries[:limit]

    if json_output:
        click.echo(json.dumps(entries, indent=2, default=str))
        return

    if not entries:
        _echo("ℹ  No cache entries found.", "dim")
        return

    if RICH_AVAILABLE:
        table = Table(title=f"Cache Entries (showing {len(entries)})")
        table.add_column("#", style="dim")
        table.add_column("Key", style="cyan")
        table.add_column("Size", style="green", justify="right")
        table.add_column("Created", style="dim")
        table.add_column("Model", style="magenta")

        for i, entry in enumerate(entries, 1):
            md = entry.get("metadata", {})
            model = md.get("model", "")
            table.add_row(
                str(i),
                entry["key"][:16] + "...",
                _fmt_size(entry["size_bytes"]),
                entry["created_at"],
                model,
            )
        console.print("")
        console.print(table)
        console.print("")
    else:
        for i, entry in enumerate(entries, 1):
            model = entry.get("metadata", {}).get("model", "?")
            _echo(f"   {i:3d}. {entry['key'][:16]}...  {_fmt_size(entry['size_bytes']):>8}  {entry['created_at']}  {model}", "dim")


@cache.command(name="clear")
@click.option(
    "--cache-dir",
    default=DEFAULT_CACHE_DIR,
    show_default=True,
    help="Cache directory path",
)
@click.confirmation_option(prompt="Are you sure you want to clear all cached benchmark results?")
def cache_clear(cache_dir):
    """Remove all cached entries."""
    from core.cache import ContentAddressableCache

    c = ContentAddressableCache(cache_dir)
    count = c.clear()

    if count > 0:
        _echo(f"✓ Cleared {count} cached entr{'y' if count == 1 else 'ies'}.", "bold green")
    else:
        _echo("ℹ  Cache was already empty.", "dim")


@cache.command(name="inspect")
@click.argument("key")
@click.option(
    "--cache-dir",
    default=DEFAULT_CACHE_DIR,
    show_default=True,
    help="Cache directory path",
)
def cache_inspect(key, cache_dir):
    """Show the full contents of a specific cache entry."""
    from core.cache import ContentAddressableCache

    c = ContentAddressableCache(cache_dir)
    entry = c.get_entry(key)

    if entry is None:
        _echo(f"✗ Cache entry not found: {key}", "red")
        sys.exit(1)

    meta = entry.get("_meta", {})
    data = entry.get("data", {})

    _echo("")
    _echo(f"🔍 Cache Entry: {key}", "bold blue")
    _echo(f"   Created: {meta.get('created_at', '?')}", "dim")
    _echo(f"   Model:   {meta.get('model', '?')}", "dim")
    _echo(f"   Task ID: {meta.get('task_id', '?')}", "dim")

    if isinstance(data, dict):
        # Try to show a useful summary
        result = data.get("result", data)
        if isinstance(result, dict):
            score = result.get("score", "?")
            tokens = result.get("tokens_used", "?")
            time_ms = result.get("response_time_ms", "?")
            _echo(f"   Score:   {score}", "bold green")
            _echo(f"   Tokens:  {tokens}", "dim")
            _echo(f"   Time:    {time_ms:.0f} ms" if isinstance(time_ms, (int, float)) else f"   Time:    {time_ms}", "dim")

    _echo("")
    click.echo(json.dumps(entry, indent=2, default=str))
    _echo("")


@cache.command(name="config")
def cache_config():
    """Show current cache configuration (directory and entry count).

    Displays the cache directory path and current entry count. Seeds
    the config YAML with a ``cache:`` section if one doesn't exist yet.
    """
    from core.cache import ContentAddressableCache

    current_dir = DEFAULT_CACHE_DIR
    config_path = Path("apps/cli/config.yaml")

    # Try to read current setting from config
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            cfg_cache = cfg.get("cache", {})
            current_dir = cfg_cache.get("cache_dir", DEFAULT_CACHE_DIR)
        except Exception:
            pass

    _echo("")
    _echo("⚙  Cache Configuration", "bold blue")
    _echo(f"   Cache directory: {current_dir}", "dim")
    _echo(f"   Entries:         {ContentAddressableCache(current_dir).status()['total_entries']}", "dim")
    _echo("")
    _echo("   Run 'modellens cache status' for detailed statistics.", "dim")
    _echo("")

    # Set cache config if not already present
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            if "cache" not in cfg:
                cfg["cache"] = {"cache_dir": current_dir}
                with open(config_path, "w") as f:
                    yaml.safe_dump(cfg, f, default_flow_style=False)
        except Exception:
            pass


def _fmt_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / (1024 ** 3):.1f} GB"
    elif size_bytes >= 1024 ** 2:
        return f"{size_bytes / (1024 ** 2):.0f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes} B"
