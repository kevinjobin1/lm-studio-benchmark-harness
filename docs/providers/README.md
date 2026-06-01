# Provider Setup Guides

ModelLens supports multiple local LLM providers through a unified `ProviderAdapter` interface.

---

## Supported providers

| Provider | Status | Default URL | Min version |
|----------|--------|-------------|-------------|
| **LM Studio** | ✅ Stable | `http://localhost:1234/v1` | 0.3.x+ |
| **Ollama** | ✅ Stable | `http://localhost:11434/v1` | 0.1.28+ |

> Future: Open WebUI, Jan, llama.cpp, vLLM

---

## LM Studio

### Setup

1. Download [LM Studio](https://lmstudio.ai/)
2. Load a model (e.g., Qwen 3.5, Gemma 4)
3. Go to **Developer** tab → enable **Local API Server**
4. Start the server (default: `http://localhost:1234`)

### Usage with ModelLens

```bash
# Auto-detect LM Studio models and run
python apps/cli/modellens.py run --quick

# Explicitly specify provider and model
python apps/cli/modellens.py run --provider lm-studio --models qwen3.5-9b-coder

# General benchmark suite
python apps/cli/modellens.py run --framework general --model-name qwen3.5-9b-coder
```

### Configuration

LM Studio uses the OpenAI-compatible `/v1/chat/completions` endpoint. ModelLens communicates with it via the `openai` Python SDK:

```python
from core.benchmark import LMStudioClient

client = LMStudioClient(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",
    model_name="qwen3.5-9b-coder",
    timeout=120,
    max_retries=3,
)

response, metrics = client.chat_completion([
    {"role": "user", "content": "Explain TypeScript generics."}
])
# metrics.ttft, metrics.tokens_per_second, etc.
```

### Health check

```bash
curl http://localhost:1234/v1/models
```

---

## Ollama

### Setup

1. Install [Ollama](https://ollama.com/)
2. Pull a model:
   ```bash
   ollama pull llama3.2
   # or
   ollama pull qwen2.5-coder:7b
   ```
3. Ollama serves automatically at `http://localhost:11434`

### Usage with ModelLens

```bash
# Auto-detect Ollama models and run
python apps/cli/modellens.py run --provider ollama --quick

# Use a specific Ollama model
python apps/cli/modellens.py run --provider ollama --models llama3.2:latest
```

### OpenAI-compatible API

Ollama >= 0.1.28 exposes an OpenAI-compatible API at `/v1`. ModelLens uses this:

```python
from providers.ollama import OllamaClient

ollama = OllamaClient(
    base_url="http://localhost:11434",
    api_key="ollama",
    model_name="llama3.2:latest",
)

# Health check (tries /v1/models, falls back to /api/tags)
if ollama.health_check():
    print("Ollama is running!")

# List installed models
for model in ollama.list_models():
    print(f"  {model.name}:{model.parameters} ({model.size_bytes} bytes)")

# Run a prompt
from providers.base import RunRequest
result = ollama.run_prompt(RunRequest(
    prompt="Explain Kubernetes in one sentence.",
    model="llama3.2:latest",
))
print(f"Response: {result.response}")
print(f"TTFT: {result.ttft_ms:.0f}ms, Tokens/sec: {result.tokens_per_second:.1f}")
```

### Model naming

Ollama models include tags: `llama3.2:latest`, `qwen2.5-coder:7b`. ModelLens's `list_models()` parses these into:
- `name`: base name (e.g., `llama3.2`)
- `parameters`: tag (e.g., `latest`, `7b`)
- `id`: full name (e.g., `llama3.2:latest`)

When passing model names via CLI, include the tag: `--models llama3.2:latest`

### Health check

```bash
# OpenAI-compatible endpoint (Ollama >= 0.1.28)
curl http://localhost:11434/v1/models

# Native endpoint (all versions)
curl http://localhost:11434/api/tags
```

---

## ProviderAdapter interface

All providers implement this interface (see `packages/providers/base.py`):

```python
class ProviderAdapter(ABC):
    name: str
    default_port: int

    def list_models(self) -> List[Model]: ...
    def health_check(self) -> bool: ...
    def run_prompt(self, request: RunRequest) -> RunResult: ...
    def chat_completion(self, messages, temperature, max_tokens, top_p, stream) -> tuple[str, object]: ...
    def collect_metrics(self) -> ProviderMetrics: ...
```

### Shared data types

| Type | Fields |
|------|--------|
| `Model` | `id`, `name`, `provider`, `parameters`, `quantization`, `size_bytes` |
| `RunRequest` | `prompt`, `model`, `temperature`, `max_tokens`, `top_p`, `system_prompt`, `stream` |
| `RunResult` | `response`, `model`, `provider`, `ttft_ms`, `total_time_ms`, `tokens_per_second`, `prompt_tokens`, `completion_tokens`, `total_tokens` |
| `APICallMetrics` | `ttft`, `total_time`, `tokens_per_second`, `total_tokens`, `prompt_tokens`, `completion_tokens` |
| `ProviderMetrics` | `cpu_percent`, `ram_used_mb`, `ram_total_mb`, `gpu_available`, `gpu_used_mb`, `swap_used_mb` |

---

## Adding a new provider

1. Create `packages/providers/your_provider.py`
2. Implement `ProviderAdapter`:
   ```python
   from .base import ProviderAdapter, Model, RunRequest, RunResult, APICallMetrics

   class YourProvider(ProviderAdapter):
       name = "your-provider"
       default_port = 8080

       def health_check(self) -> bool: ...
       def list_models(self) -> List[Model]: ...
       def run_prompt(self, request: RunRequest) -> RunResult: ...
       def chat_completion(self, messages, ...) -> tuple[str, APICallMetrics]: ...
   ```
3. Register in `packages/providers/__init__.py`
4. Add `--provider` option to `apps/cli/modellens.py`
5. Add auto-detection logic

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for PR guidelines.
