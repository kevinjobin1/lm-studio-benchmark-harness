# Provider Plugin System

> **Spec version**: 1.0.0
> **Last updated**: 2026-06-04
> **Status**: Implemented (Phase 1, Task 1.7)

---

## Overview

Model Lens discovers LLM providers at runtime via Python
[entry points](https://packaging.python.org/en/latest/specifications/entry-points/).
A third-party package can register a new provider by declaring a single
entry in its `pyproject.toml` — no patches to Model Lens source needed.

Once installed, the new provider appears in:

- `modellens info` — auto-detected model list
- `modellens models --provider <name>` — model details table
- `modellens health --provider <name>` — reachability check
- `modellens run --provider <name>` — benchmark execution
- `modellens workload run --provider <name>` — workload evaluation

---

## Quickstart: the 4-step checklist

### 1. Subclass `ProviderAdapter` (or `OpenAICompatibleProvider`)

Create a provider class with **four required class attributes** and **four
required methods**:

```python
# my_provider/provider.py
from providers.base import ProviderAdapter, Model, RunRequest, RunResult, APICallMetrics

class MyProvider(ProviderAdapter):
    # ── Class attributes (REQUIRED for entry-point discovery) ──
    name = "my-provider"            # canonical name used by `modellens --provider`
    default_port = 9090
    default_url = "http://localhost:9090/v1"   # will be probed during auto-detection
    default_api_key = "my-key"                 # default API key (or "" if none)

    def __init__(self, base_url=None, api_key=None, model_name="", timeout=120, max_retries=3, **kwargs):
        self.base_url = (base_url or self.default_url).rstrip("/")
        self.api_key = api_key or self.default_api_key
        self.model_name = model_name
        # … initialise your HTTP client here …

    # ── Required methods ────────────────────────────────────────
    def health_check(self) -> bool:       # GET /v1/models or /health, return True/False
    def list_models(self) -> list[Model]: # query provider API, return Model objects
    def run_prompt(self, request: RunRequest) -> RunResult:
    def chat_completion(self, messages, temperature=0.0, max_tokens=4096, top_p=1.0, stream=False) -> tuple[str, APICallMetrics]:
```

**Tip:** If your provider already exposes an OpenAI-compatible `/v1` API,
subclass `OpenAICompatibleProvider` instead — you inherit `health_check`,
`list_models`, `run_prompt`, and `chat_completion` for free:

```python
from providers.openai_compatible import OpenAICompatibleProvider

class MyProvider(OpenAICompatibleProvider):
    name = "my-provider"
    default_port = 9090
    default_url = "http://localhost:9090/v1"
    default_api_key = "my-key"
    # Done! All four methods are inherited from the base class.
```

Override only the methods that need provider-specific logic (e.g., a
non-standard model list endpoint or a `/health` fallback).

### 2. Register the entry point

In your package's `pyproject.toml`, add a single entry under the
`"modellens.providers"` group:

```toml
# my_provider/pyproject.toml
[project.entry-points."modellens.providers"]
my-provider = "my_provider.provider:MyProvider"
```

The value is `module.path:ClassName` — Model Lens calls
`importlib.metadata.entry_points()` at startup to find and load it.

### 3. Install your package

```bash
pip install -e ./my_provider          # local development
pip install my-provider               # from PyPI
```

If Model Lens was installed with `pip install -e .`, the new entry
point is picked up immediately on the next command.  No restart needed.

### 4. Verify discovery

```bash
modellens info                    # lists your provider in "Available providers"
modellens health --provider my-provider
modellens models --provider my-provider
modellens run --provider my-provider --model any-model
```

---

## Reference

### Class attributes (entry-point contract)

| Attribute          | Type    | Required                 | Purpose                                                                      |
| ------------------ | ------- | ------------------------ | ---------------------------------------------------------------------------- |
| `name`             | `str`   | **Yes**                  | Canonical name used by all `--provider` flags and the entry-point registry   |
| `default_port`     | `int`   | **Yes**                  | Fallback when `default_url` is not set; used to derive `http://localhost:{port}/v1` |
| `default_url`      | `str`   | Recommended              | Base URL probed during auto-detection; set this if your path is non-standard |
| `default_api_key`  | `str`   | Recommended              | Default API key (often `""` or a well-known string like `"not-needed"`)      |

If you omit `default_url`, it is derived from `default_port` as
`http://localhost:{port}/v1`.

If you omit `default_api_key`, it defaults to `"not-needed"`.

### ProviderAdapter abstract methods

| Method            | Signature                                | Returns                            | Purpose                                   |
| ----------------- | ---------------------------------------- | ---------------------------------- | ----------------------------------------- |
| `health_check`    | `() -> bool`                             | `True` if reachable                | Probed by `modellens health` and auto-detect |
| `list_models`     | `() -> list[Model]`                      | List of available models           | Used by `modellens models` and `modellens info` |
| `run_prompt`      | `(request: RunRequest) -> RunResult`     | Structured result with metrics     | Benchmark harness calls this per prompt     |
| `chat_completion` | `(messages, temperature, max_tokens, top_p, stream) -> tuple[str, APICallMetrics]` | Response text + timing metrics | Raw API call used by the benchmark suite    |

### Helper dataclasses (`providers.base`)

```python
from providers.base import (
    ProviderAdapter,      # abstract base class
    Model,                # provider model metadata
    RunRequest,           # benchmark prompt request
    RunResult,            # completed run result
    APICallMetrics,       # ttft, tps, token counts
    ProviderMetrics,      # cpu/ram/gpu snapshots
)
```

### URL utilities

```python
from providers.base import normalize_base_url, get_root_url, url_join

base = normalize_base_url("http://localhost:9090/v1/")  # → "http://localhost:9090/v1"
root = get_root_url("http://localhost:9090/v1")          # → "http://localhost:9090"
full = url_join("http://localhost:9090/v1", "models")    # → "http://localhost:9090/v1/models"
```

Use `url_join` (not `f"{base}/{path}"`) to join URL path segments — it
correctly handles trailing/leading slashes.

---

## Advanced patterns

### Non-standard API paths

If your provider serves models at `/api/custom/models` instead of
`/v1/models`, override `list_models`:

```python
from providers.base import url_join

def list_models(self) -> list[Model]:
    import requests
    resp = requests.get(url_join(self.base_url, "api/custom/models"), timeout=10)
    …
```

The same approach works for `health_check()` — probe whatever endpoint
best indicates the provider is alive.

### Health-check fallback (`/health` endpoint)

Follow the pattern used by `LlamaCppClient` and `VLLMClient`:

```python
def health_check(self) -> bool:
    import requests
    from providers.base import get_root_url, url_join

    try:
        resp = requests.get(url_join(self.base_url, "models"), timeout=5)
        if resp.status_code == 200:
            return True
    except (requests.ConnectionError, requests.Timeout):
        pass
    # Fallback: /health at the server root
    try:
        health_url = url_join(get_root_url(self.base_url), "health")
        resp = requests.get(health_url, timeout=5)
        return resp.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False
```

### Streaming + event bus integration

`OpenAICompatibleProvider` already emits `TokenGeneratedEvent`,
`CompletionEvent`, and `ErrorEvent` to the global event bus when
streaming is enabled. If you need custom event emission, accept an
`event_bus` parameter in `__init__` and use the pattern from
`openai_compatible.py`.

### Testing a custom provider

```python
from unittest.mock import patch, MagicMock
import unittest

from my_provider.provider import MyProvider

class TestMyProvider(unittest.TestCase):
    @patch("my_provider.provider.requests.get")
    def test_health_check_ok(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        p = MyProvider()
        self.assertTrue(p.health_check())

    @patch("my_provider.provider.requests.get")
    def test_list_models(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"data": [{"id": "model-1"}]},
        )
        p = MyProvider()
        models = p.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "model-1")
```

Run with: `pytest tests/ -v`

---

## Built-in providers (reference implementations)

| Provider        | Class                    | Port   | File                                               |
| --------------- | ------------------------ | ------ | -------------------------------------------------- |
| LM Studio       | `LMStudioProvider`       | 1234   | `packages/providers/openai_compatible.py`          |
| Ollama          | `OllamaClient`           | 11434  | `packages/providers/ollama.py`                     |
| Open WebUI      | `OpenWebUIClient`        | 3000   | `packages/providers/openwebui.py`                  |
| Jan             | `JanClient`              | 1337   | `packages/providers/jan.py`                        |
| llama.cpp       | `LlamaCppClient`         | 8080   | `packages/providers/llamacpp.py`                   |
| vLLM            | `VLLMClient`             | 8000   | `packages/providers/vllm.py`                       |

Each of these is &lt;100 lines of provider-specific code — use them as
starting points for your own implementation.

---

## Entry-point registry (how it works)

```
pip install my-provider
        │
        ▼
pyproject.toml:
  [project.entry-points."modellens.providers"]
  my-provider = "my_provider:MyProvider"
        │
        ▼
importlib.metadata.entry_points(group="modellens.providers")
        │
        ▼
    ep.load()  →  MyProvider class
        │
        ▼
ProviderEntry(name="my-provider", cls=MyProvider, default_url=..., default_api_key=...)
        │
        ▼
discover_providers()["my-provider"]    ← usable everywhere
```

If no entry points are found (e.g., the package wasn't installed with
`pip install -e .`), the system falls back to a built-in registry in
`packages/providers/__init__.py`.

---

## Troubleshooting

**Provider not appearing in `modellens info`**

```bash
python -c "
from importlib.metadata import entry_points
eps = entry_points(group='modellens.providers')
print(list(eps))
"
```

If the list is empty, your package may not be installed, or the entry
point group name may be misspelled. Re-run `pip install -e .` and verify
the `pyproject.toml` entry matches exactly:
`[project.entry-points."modellens.providers"]`.

**`KeyError: Unknown provider 'my-provider'`**

Check that `name = "my-provider"` is set on your class.  Run:

```bash
python -c "from providers import discover_providers; print(list(discover_providers()))"
```

**`TypeError` on method signature**

Model Lens expects `chat_completion` to return `tuple[str, APICallMetrics]`.
Verify the return type matches the `ProviderAdapter` abstract methods.
