"""Models command for modellens CLI.

Lists available models from the connected provider.
"""

import json
from pathlib import Path

import click
from rich.table import Table

from .utils import (
    _echo,
    _fmt_size,
    _list_models_detailed,
    _resolve_provider,
    RICH_AVAILABLE,
    console,
)


@click.command()
@click.option(
    "--api-base",
    default=None,
    show_default=False,
    help="Provider base URL (auto-detected for known providers)",
)
@click.option("--api-key", default=None, show_default=False)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["lm-studio", "ollama", "open-webui", "jan", "llama.cpp", "vllm"]),
    default=None,
    help="Provider to query (auto-detected if omitted)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def models(api_base, api_key, provider, json_output):
    """List available models from the connected provider.

    \\b
    Examples:
      modellens models
      modellens models --provider ollama
      modellens models --json
    """
    # ── Provider resolution ─────────────────────────────────────
    if provider is None:
        provider, detected_base, detected_key = _resolve_provider()
        api_base = api_base or detected_base
        api_key = api_key or detected_key
    else:
        from providers import get_provider_config

        url, key = get_provider_config(provider)
        api_base = api_base or url
        api_key = api_key or key

    # Validate connection
    try:
        import requests

        # api_base already contains the correct prefix for all providers
        check_url = f"{api_base}/models"
        resp = requests.get(check_url, timeout=3)
        if resp.status_code != 200:
            _echo(f"✗ {provider} is not reachable at {check_url}", "red")
            return
    except (requests.ConnectionError, requests.Timeout):
        _echo(f"✗ {provider} is not reachable", "red")
        return
    except requests.RequestException:
        _echo(f"✗ {provider} is not reachable", "red")
        return

    # Fetch model details
    model_list = _list_models_detailed(provider, api_base, api_key)

    if not model_list:
        _echo(f"No models found on {provider}", "yellow")
        return

    if json_output:
        click.echo(
            json.dumps(
                {
                    "provider": provider,
                    "count": len(model_list),
                    "models": model_list,
                },
                indent=2,
                default=str,
            )
        )
        return

    _echo("")
    _echo(f"🤖 {provider.upper()} Models ({len(model_list)})", "bold blue")

    # LM Studio doesn't expose parameters/quantization/size
    is_lmstudio = provider == "lm-studio"

    if RICH_AVAILABLE:
        table = Table(title=None, show_header=True, header_style="bold")
        table.add_column("Name", style="cyan", no_wrap=True)
        if is_lmstudio:
            table.add_column("Details", style="dim")
        else:
            table.add_column("Params", style="green", justify="right")
            table.add_column("Quantization", style="magenta")
            table.add_column("Size", style="yellow", justify="right")
        for m in model_list:
            if is_lmstudio:
                table.add_row(m.get("id", "unknown"), "—")
            else:
                table.add_row(
                    m.get("id", m.get("name", "unknown")),
                    m.get("parameters", "unknown"),
                    m.get("quantization", "unknown"),
                    _fmt_size(m.get("size_bytes", 0)) if m.get("size_bytes") else "—",
                )
        console.print("")
        console.print(table)
        if is_lmstudio:
            _echo("   ℹ  LM Studio API doesn't expose parameter/quantization details", "dim")
        console.print("")
    else:
        for m in model_list:
            name = m.get("id", m.get("name", "unknown"))
            if is_lmstudio:
                _echo(f"  {name}")
            else:
                params = m.get("parameters", "unknown")
                quant = m.get("quantization", "unknown")
                size = _fmt_size(m.get("size_bytes", 0)) if m.get("size_bytes") else "—"
                _echo(f"  {name:<40} {params:<12} {quant:<14} {size}")
        _echo("")
