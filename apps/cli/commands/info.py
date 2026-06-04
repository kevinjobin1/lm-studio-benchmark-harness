"""Info command for modellens CLI.

Shows system info, available models, and prompt packs.
"""

import click

from core.hardware import detect_hardware
from .utils import (
    _echo,
    _get_git_sha,
    _resolve_provider,
    _list_models_detailed,
    _fmt_size,
)


@click.command()
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["lm-studio", "ollama", "open-webui", "jan", "llama.cpp", "vllm"]),
    default=None,
    help="Provider to query (auto-detected if omitted)",
)
@click.option(
    "--api-base",
    default=None,
    show_default=False,
    help="Provider base URL (auto-detected for known providers)",
)
@click.option("--api-key", default=None, show_default=False)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def info(provider, api_base, api_key, json_output):
    """Show system info, available models, and prompt packs.

    \\b
    Examples:
      modellens info
      modellens info --provider vllm
      modellens info --provider ollama --api-base http://localhost:11434/v1
    """
    # ── Collect data first ───────────────────────────────────────
    hw = detect_hardware()
    git_sha = _get_git_sha()

    if provider is None:
        provider, detected_base, detected_key = _resolve_provider()
        api_base = api_base or detected_base
        api_key = api_key or detected_key
    else:
        from providers import get_provider_config

        url, key = get_provider_config(provider)
        api_base = api_base or url
        api_key = api_key or key

    try:
        models = _list_models_detailed(provider, api_base, api_key)
    except Exception:
        models = []

    # ── JSON output ────────────────────────────────────────────
    if json_output:
        import json as json_mod

        click.echo(
            json_mod.dumps(
                {
                    "hardware": hw.to_dict() if hasattr(hw, "to_dict") else str(hw),
                    "provider": provider,
                    "api_base": api_base,
                    "models": models,
                    "model_count": len(models),
                },
                indent=2,
                default=str,
            )
        )
        return

    # ── Rich text output ───────────────────────────────────────
    _echo("")
    _echo("🔬  Model Lens v0.1.0", "bold blue")
    _echo(f"   git: {git_sha}", "dim")

    _echo(f"\n🖥  Hardware: {hw.summary()}", "bold")
    _echo(
        f"   CPU: {hw.cpu_model} ({hw.cpu_cores_physical} phys / {hw.cpu_cores_logical} log)", "dim"
    )
    _echo(
        f"   RAM: {hw.ram_total_mb / 1024:.0f} GB ({(hw.ram_total_mb - hw.ram_available_mb) / 1024:.1f} GB used)",
        "dim",
    )
    if hw.gpu_available:
        vram_info = "unified" if hw.unified_memory else f"{hw.gpu_vram_mb:.0f} MB"
        _echo(f"   GPU: {hw.gpu_model} ({vram_info})", "dim")
    if hw.is_apple_silicon:
        _echo(f"   Arch: {hw.architecture} (Apple Silicon, unified memory)", "dim")
    else:
        _echo(f"   Arch: {hw.architecture}", "dim")
    _echo(f"   OS: {hw.os_name} {hw.os_version} (kernel {hw.kernel})", "dim")

    if models:
        _echo(f"\n🤖 {provider.upper()} Models ({len(models)}):", "bold")
        for m in models:
            name = m.get("id", m.get("name", "unknown"))
            params = m.get("parameters", "unknown")
            quant = m.get("quantization", "unknown")
            size = _fmt_size(m.get("size_bytes", 0)) if m.get("size_bytes") else "—"
            if provider == "lm-studio":
                _echo(f"   {name}", "dim")
            else:
                _echo(f"   {name:<40} {params:<12} {quant:<14} {size}", "dim")
    else:
        _echo(f"\n🤖 {provider.upper()}: None detected (is {provider} running?)", "yellow")

    _echo("")
