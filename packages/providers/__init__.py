"""Provider adapters and framework integrations for Model Lens.

Entry-point-based plugin discovery::

    from providers import discover_providers, get_provider, get_provider_config

    all_providers = discover_providers()        # {name: ProviderEntry}
    entry = get_provider("ollama")              # ProviderEntry
    url, key = get_provider_config("ollama")    # ("http://...", "ollama")

Third-party providers register via ``pyproject.toml``::

    [project.entry-points."modellens.providers"]
    my-provider = "my_package:MyProviderClass"
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, TYPE_CHECKING

from .base import ProviderAdapter, Model, RunRequest, RunResult, ProviderMetrics, APICallMetrics
from .openai_compatible import OpenAICompatibleProvider

# Lazy-load provider clients — fails gracefully if deps are missing
try:
    from .ollama import OllamaClient
except (ImportError, ModuleNotFoundError):
    OllamaClient = None  # type: ignore

try:
    from .openwebui import OpenWebUIClient
except (ImportError, ModuleNotFoundError):
    OpenWebUIClient = None  # type: ignore

try:
    from .jan import JanClient
except (ImportError, ModuleNotFoundError):
    JanClient = None  # type: ignore

try:
    from .llamacpp import LlamaCppClient
except (ImportError, ModuleNotFoundError):
    LlamaCppClient = None  # type: ignore

try:
    from .vllm import VLLMClient
except (ImportError, ModuleNotFoundError):
    VLLMClient = None  # type: ignore

# ── Entry-point discovery ────────────────────────────────────────────

_PROVIDER_CACHE: Optional[Dict[str, ProviderEntry]] = None


@dataclass
class ProviderEntry:
    """Lightweight metadata for a discovered provider.

    The ``cls`` attribute is a :class:`ProviderAdapter` *subclass* — call
    it to obtain an instance::

        instance = entry.cls(base_url=..., api_key=...)
    """

    name: str
    cls: "type"
    default_url: str
    default_api_key: str

    def __repr__(self) -> str:
        return f"ProviderEntry({self.name!r}, url={self.default_url!r})"


def discover_providers() -> Dict[str, ProviderEntry]:
    """Return all registered providers via ``importlib.metadata`` entry points.

    Results are cached after the first call so repeated lookups are cheap.

    Returns:
        Dict mapping provider name (e.g. ``"ollama"``) to
        :class:`ProviderEntry` metadata.
    """
    global _PROVIDER_CACHE
    if _PROVIDER_CACHE is not None:
        return _PROVIDER_CACHE

    providers: Dict[str, ProviderEntry] = {}
    try:
        # Python 3.12+ prefers this signature
        from importlib.metadata import entry_points

        eps = entry_points(group="modellens.providers")
    except TypeError:
        # Python 3.10 / 3.11 signature: entry_points() returns a dict
        try:
            eps = entry_points().get("modellens.providers", [])
        except Exception:
            eps = []

    # If no entry points found (e.g. package not installed with pip install -e .),
    # fall back to the hardcoded built-in registry.
    if not eps:
        eps = _builtin_providers()

    for ep in eps:
        cls = _resolve_entry_point(ep)
        if cls is None:
            continue

        name = ep.name  # Entry-point name is the canonical provider name
        providers[name] = ProviderEntry(
            name=name,
            cls=cls,
            default_url=getattr(cls, "default_url", _default_url_for(cls)),
            default_api_key=getattr(cls, "default_api_key", "not-needed"),
        )

    _PROVIDER_CACHE = providers
    return providers


def get_provider(name: str) -> ProviderEntry:
    """Look up a provider by name (e.g. ``\"ollama\"``).

    Raises:
        KeyError: If no provider with that name is registered.
    """
    providers = discover_providers()
    try:
        return providers[name]
    except KeyError:
        available = ", ".join(sorted(providers))
        raise KeyError(
            f"Unknown provider '{name}'. Registered providers: {available}"
        ) from None


def get_provider_config(name: str) -> Tuple[str, str]:
    """Return ``(default_url, default_api_key)`` for *name*.

    Backward-compatible replacement for the old ``PROVIDER_CONFIG`` dict.
    Falls back to ``\"lm-studio\"`` if *name* is not found.
    """
    providers = discover_providers()
    entry = providers.get(name) or providers.get("lm-studio")
    if entry is None:
        # Ultimate fallback — shouldn't happen if install completed
        return ("http://localhost:1234/v1", "lm-studio")
    return (entry.default_url, entry.default_api_key)


# ── Internal helpers ─────────────────────────────────────────────────


def _resolve_entry_point(ep) -> Optional["type"]:
    """Safely load a provider class from an entry point."""
    try:
        return ep.load()
    except (ImportError, ModuleNotFoundError, AttributeError) as exc:
        print(
            f"[providers] Could not load provider entry point '{ep.name}': {exc}",
            file=sys.stderr,
        )
        return None


def _default_url_for(cls: "type") -> str:
    """Derive a default URL from the class's ``default_port`` attribute."""
    port = getattr(cls, "default_port", 8000)
    return f"http://localhost:{port}/v1"


def _builtin_providers():
    """Return synthetic entry points for the six built-in providers.

    Used as a fallback when ``pip install -e .`` hasn't been run yet
    and the entry-point machinery returns nothing.
    """

    class _FakeEntryPoint:
        def __init__(self, name, module, cls_name):
            self.name = name
            self._module = module
            self._cls_name = cls_name

        def load(self):
            import importlib

            mod = importlib.import_module(self._module)
            return getattr(mod, self._cls_name)

    return [
        _FakeEntryPoint("lm-studio", "providers.openai_compatible", "LMStudioProvider"),
        _FakeEntryPoint("ollama", "providers.ollama", "OllamaClient"),
        _FakeEntryPoint("open-webui", "providers.openwebui", "OpenWebUIClient"),
        _FakeEntryPoint("jan", "providers.jan", "JanClient"),
        _FakeEntryPoint("llama.cpp", "providers.llamacpp", "LlamaCppClient"),
        _FakeEntryPoint("vllm", "providers.vllm", "VLLMClient"),
    ]


# ── Shared task mappings (no dependencies needed) ────────────────────

LM_EVAL_TASK_MAPPING = {
    "mmlu_pro": "mmlu",
    "gsm8k": "gsm8k",
    "aime": "aime",
    "humaneval": "humaneval",
    "if_eval": "ifeval",
}

OPENBENCH_TASK_MAPPING = {
    "mmlu_pro": "mmlu_pro",
    "gsm8k": "gsm8k",
    "aime": "aime_2024",
    "humaneval": "humaneval",
}


def run_lm_eval_benchmarks(base_url, api_key, model_name, benchmark_names, limit=None):
    """Run LM Eval benchmarks (lazy import to avoid requiring lm_eval at startup)."""
    from .lm_eval_integration import run_lm_eval_benchmarks as _run

    return _run(base_url, api_key, model_name, benchmark_names, limit)


def run_openbench_benchmarks(
    base_url, model_name, benchmark_names, limit=None, install_if_missing=False
):
    """Run OpenBench benchmarks (lazy import to avoid requiring openbench at startup)."""
    from .openbench_integration import run_openbench_benchmarks as _run

    return _run(base_url, model_name, benchmark_names, limit, install_if_missing)


__all__ = [
    # Core
    "ProviderAdapter",
    "OpenAICompatibleProvider",
    "APICallMetrics",
    "Model",
    "RunRequest",
    "RunResult",
    "ProviderMetrics",
    # Provider clients (lazy)
    "OllamaClient",
    "OpenWebUIClient",
    "JanClient",
    "LlamaCppClient",
    "VLLMClient",
    # Entry-point discovery
    "ProviderEntry",
    "discover_providers",
    "get_provider",
    "get_provider_config",
    # Integrations
    "run_lm_eval_benchmarks",
    "LM_EVAL_TASK_MAPPING",
    "run_openbench_benchmarks",
    "OPENBENCH_TASK_MAPPING",
]
