"""Shared CLI utilities for modellens commands."""

import subprocess
from typing import List, Optional

import click

from packages.modellens_logging import get_logger
from providers import discover_providers, get_provider_config
from providers.base import get_root_url

logger = get_logger(__name__)

# ── Rich terminal output ──────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    console = None
    RICH_AVAILABLE = False


def _echo(message: str, style: str = ""):
    """Print to console (rich-aware)."""
    if RICH_AVAILABLE and style:
        getattr(console, "print", print)(f"[{style}]{message}[/{style}]")
    else:
        print(message)


def _get_git_sha() -> str:
    """Get the current git short SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug("Could not determine git SHA: %s", e)
        return "unknown"


def _fmt_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.1f} GB"
    elif size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.0f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes} B"


# Provider configuration: auto-discovered from entry points.
# Use ``get_provider_config(name)`` (from providers.__init__) instead of
# directly accessing this dict.

def _resolve_provider(provider: Optional[str] = None) -> tuple:
    """Resolve provider and return (provider_name, api_base, api_key).

    Auto-detects if provider is None: checks all known providers in
    order of likelihood (LM Studio → Ollama → llama.cpp → vLLM →
    Open WebUI → Jan).
    """
    if provider is None:
        import requests

        # Probe all discovered providers in their registered order.
        # The entry-point order determines priority (pip controls this).
        for entry in discover_providers().values():
            probe_url = f"{entry.default_url}/models"
            try:
                resp = requests.get(probe_url, timeout=2)
                if resp.status_code == 200:
                    provider = entry.name
                    break
            except (requests.ConnectionError, requests.Timeout):
                continue
        if not provider:
            provider = "lm-studio"  # Default fallback

    url, key = get_provider_config(provider)
    return provider, url, key


def _list_provider_models(provider: str, api_base: str, api_key: str) -> List[str]:
    """Query provider for available model names via lightweight HTTP GET."""
    import requests

    try:
        if provider == "lm-studio":
            resp = requests.get(f"{api_base}/models", timeout=5)
            if resp.status_code == 200:
                return [m.get("id", "") for m in resp.json().get("data", [])]
        elif provider == "ollama":
            # Ollama's native API is at the server root, not /v1.
            # Extract scheme+netloc from api_base to construct the right URL.
            ollama_base = get_root_url(api_base)
            resp = requests.get(f"{ollama_base}/api/tags", timeout=5)
            if resp.status_code == 200:
                return [m.get("name", "") for m in resp.json().get("models", [])]
        else:
            # Generic OpenAI-compatible provider (open-webui, jan, llama.cpp, vllm)
            # api_base already contains the correct prefix (/v1 or /api/v1)
            resp = requests.get(f"{api_base}/models", timeout=5)
            if resp.status_code == 200:
                return [m.get("id", "") for m in resp.json().get("data", [])]
    except (requests.ConnectionError, requests.Timeout):
        pass
    except (requests.RequestException, ValueError, KeyError) as e:
        logger.debug("Could not list provider models for %s: %s", provider, e)
    return []


def _list_models_detailed(provider: str, api_base: str, api_key: str) -> list:
    """Query provider for model details (name, parameters, quantization, size)."""
    import requests

    models = []
    try:
        if provider == "lm-studio":
            resp = requests.get(f"{api_base}/models", timeout=5)
            if resp.status_code == 200:
                for m in resp.json().get("data", []):
                    models.append(
                        {
                            "id": m.get("id", "unknown"),
                            "provider": "lm-studio",
                            "parameters": "unknown",
                            "quantization": "unknown",
                            "size_bytes": 0,
                        }
                    )
        elif provider == "ollama":
            # Ollama's native API is at the server root, not /v1.
            # Extract scheme+netloc from api_base to construct the right URL.
            ollama_base = get_root_url(api_base)
            resp = requests.get(f"{ollama_base}/api/tags", timeout=5)
            if resp.status_code == 200:
                for m in resp.json().get("models", []):
                    full_name = m.get("name", "unknown")
                    parts = full_name.split(":")
                    base_name = parts[0]
                    tag = parts[1] if len(parts) > 1 else "latest"
                    details = m.get("details", {})
                    size = m.get("size", 0)
                    models.append(
                        {
                            "id": full_name,
                            "name": base_name,
                            "provider": "ollama",
                            "parameters": tag,
                            "quantization": details.get("quantization_level", "unknown"),
                            "size_bytes": size,
                            "family": details.get("family", ""),
                            "format": details.get("format", ""),
                        }
                    )
        else:
            # Generic OpenAI-compatible provider (open-webui, jan, llama.cpp, vllm)
            # api_base already contains the correct prefix (/v1 or /api/v1)
            resp = requests.get(f"{api_base}/models", timeout=5)
            if resp.status_code == 200:
                for m in resp.json().get("data", []):
                    mid = m.get("id", "unknown")
                    models.append(
                        {
                            "id": mid,
                            "name": mid,
                            "provider": provider,
                            "parameters": m.get("metadata", {}).get("parameter_count", "unknown"),
                            "quantization": m.get("metadata", {}).get("quantization", "unknown"),
                            "size_bytes": m.get("metadata", {}).get("model_size", 0),
                        }
                    )
    except (requests.ConnectionError, requests.Timeout):
        pass
    except (requests.RequestException, ValueError, KeyError) as e:
        logger.debug("Could not list detailed models for %s: %s", provider, e)
    return models



def validate_provider_connection(provider: str, api_base: str) -> bool:
    """Check if the provider is reachable. Exits on failure."""
    import requests
    import sys

    # Use api_base (which may be user-provided via --api-base) instead of cfg['url']
    models_url = f"{api_base}/models"
    try:
        resp = requests.get(models_url, timeout=3)
        if resp.status_code == 200:
            return True
        _echo(f"✗ {provider} is not running or unreachable at {models_url}", "red")
        _echo(f"  Start {provider} and retry, or use --provider to switch.", "dim")
        sys.exit(1)
    except requests.RequestException:
        _echo(f"✗ {provider} is not running at {models_url}.", "red")
        _echo(f"  Start {provider} and retry, or use --provider to switch.", "dim")
        sys.exit(1)
