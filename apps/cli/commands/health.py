"""Health check command for modellens CLI.

Checks if a provider is reachable and healthy.
"""

import sys

import click

from .utils import (
    _echo,
    _resolve_provider,
    PROVIDER_CONFIG,
)


@click.command()
@click.option("--provider", "-p",
              type=click.Choice(["lm-studio", "ollama", "open-webui", "jan", "llama.cpp", "vllm"]),
              default=None,
              help="Provider to check (auto-detected if omitted)")
@click.option("--api-base", default=None, show_default=False,
              help="Provider base URL (auto-detected for known providers)")
@click.option("--json", "json_output", is_flag=True,
              help="Output as JSON")
def health(provider, api_base, json_output):
    """Check provider health and connectivity.

    \\b
    Examples:
      modellens health
      modellens health --provider vllm
      modellens health --provider ollama --api-base http://localhost:11434/v1 --json
    """
    # ── Provider resolution ─────────────────────────────────────
    if provider is None:
        provider, detected_base, _ = _resolve_provider()
        api_base = api_base or detected_base
    else:
        cfg = PROVIDER_CONFIG.get(provider, PROVIDER_CONFIG["lm-studio"])
        api_base = api_base or cfg["url"]

    # ── Health check ────────────────────────────────────────────
    import requests

    models_url = f"{api_base}/models"
    reachable = False
    status_code = None
    error = None
    model_count = 0

    try:
        resp = requests.get(models_url, timeout=5)
        status_code = resp.status_code
        if resp.status_code == 200:
            reachable = True
            data = resp.json()
            if isinstance(data, dict):
                model_count = len(data.get("data", []))
        else:
            error = f"HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        error = "connection refused"
    except requests.exceptions.Timeout:
        error = "connection timeout"
    except requests.exceptions.RequestException as e:
        error = str(e)

    # ── Provider-specific fallback checks ────────────────────────
    if not reachable:
        if provider in ("llama.cpp", "vllm"):
            # Try /health endpoint fallback
            try:
                health_url = api_base.removesuffix("/v1") + "/health"
                resp = requests.get(health_url, timeout=5)
                if resp.status_code == 200:
                    reachable = True
                    error = None
                    status_code = 200
            except (requests.ConnectionError, requests.Timeout):
                pass

    # ── Output ──────────────────────────────────────────────────
    if json_output:
        import json as json_mod
        click.echo(json_mod.dumps({
            "provider": provider,
            "api_base": api_base,
            "reachable": reachable,
            "status_code": status_code,
            "error": error,
            "models_detected": model_count,
        }, indent=2, default=str))
        return

    _echo("")
    if reachable:
        _echo(f"✅ {provider.upper()} is healthy", "bold green")
        _echo(f"   URL: {api_base}", "dim")
        if model_count > 0:
            _echo(f"   Models: {model_count} available", "dim")
        else:
            _echo(f"   Models: 0 (server running, no models loaded)", "yellow")
    else:
        _echo(f"❌ {provider.upper()} is unreachable", "bold red")
        _echo(f"   URL: {api_base}", "dim")
        if error:
            _echo(f"   Error: {error}", "red")
        _echo(f"   Start {provider} and retry.", "dim")
        sys.exit(1)
    _echo("")
