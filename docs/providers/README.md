# Provider Setup Guides

Model Lens supports multiple local LLM providers through a unified `ProviderAdapter` interface.

---

## Supported providers

| Provider | Status | Default URL | Min version |
|----------|--------|-------------|-------------|
| **LM Studio** | ✅ Stable | `http://localhost:1234/v1` | 0.3.x+ |
| **Ollama** | ✅ Stable | `http://localhost:11434/v1` | 0.1.28+ |
| **Open WebUI** | ✅ Stable | `http://localhost:3000/api/v1` | 0.5.x+ |
| **Jan** | ✅ Stable | `http://localhost:1337/v1` | 0.5.x+ |
| **llama.cpp** | ✅ Stable | `http://localhost:8080/v1` | b4200+ |
| **vLLM** | ✅ Stable | `http://localhost:8000/v1` | 0.6.x+ |

---

## LM Studio

### Setup

1. Download [LM Studio](https://lmstudio.ai/)
2. Load a model (e.g., Qwen 3.5, Gemma 4)
3. Go to **Developer** tab → enable **Local API Server**
4. Start the server (default: `http://localhost:1234`)

### Usage with Model Lens

```bash
# Auto-detect LM Studio models and run
python apps/cli/modellens.py run --quick

# Explicitly specify provider and model
python apps/cli/modellens.py run --provider lm-studio --models qwen3.5-9b-coder

# General benchmark suite
python apps/cli/modellens.py run --framework general --model-name qwen3.5-9b-coder
```

### Configuration

LM Studio uses the OpenAI-compatible `/v1/chat/completions` endpoint. Model Lens communicates with it via the `openai` Python SDK:

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

### Usage with Model Lens

```bash
# Auto-detect Ollama models and run
python apps/cli/modellens.py run --provider ollama --quick

# Use a specific Ollama model
python apps/cli/modellens.py run --provider ollama --models llama3.2:latest
```

### OpenAI-compatible API

Ollama >= 0.1.28 exposes an OpenAI-compatible API at `/v1`. Model Lens uses this:

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

Ollama models include tags: `llama3.2:latest`, `qwen2.5-coder:7b`. Model Lens's `list_models()` parses these into:
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

## Open WebUI

### Setup

1. Install [Open WebUI](https://openwebui.com/) (e.g., via Docker or pip)
2. Open WebUI serves an OpenAI-compatible API at `http://localhost:3000/api/v1`

### Usage with Model Lens

```bash
# Auto-detect
python apps/cli/modellens.py run --provider open-webui --quick

# Use a specific model
python apps/cli/modellens.py run --provider open-webui --models my-model
```

### Usage in Python

```python
from providers.openwebui import OpenWebUIClient

client = OpenWebUIClient(
    base_url="http://localhost:3000",
    api_key="open-webui",
    model_name="my-model",
)

if client.health_check():
    print("Open WebUI is running!")
```

---

## Jan

### Setup

1. Download [Jan](https://jan.ai/)
2. Load a model
3. Jan serves an OpenAI-compatible API at `http://localhost:1337/v1`

### Usage with Model Lens

```bash
# Auto-detect
python apps/cli/modellens.py run --provider jan --quick

# Use a specific model
python apps/cli/modellens.py run --provider jan --models my-model
```

### Usage in Python

```python
from providers.jan import JanClient

client = JanClient(
    base_url="http://localhost:1337",
    api_key="jan",
    model_name="my-model",
)

if client.health_check():
    print("Jan is running!")
```

---

## llama.cpp

### Setup

1. Build or download [llama.cpp](https://github.com/ggerganov/llama.cpp)
2. Run the server:
   ```bash
   ./server -m models/my-model.gguf --host 0.0.0.0 --port 8080
   ```
3. llama.cpp serves an OpenAI-compatible API at `http://localhost:8080/v1`

### Usage with Model Lens

```bash
# Auto-detect
python apps/cli/modellens.py run --provider llama.cpp --quick

# Use with specific model
python apps/cli/modellens.py run --provider llama.cpp --models llama-3.2-7b
```

### Usage in Python

```python
from providers.llamacpp import LlamaCppClient

client = LlamaCppClient(
    base_url="http://localhost:8080",
    api_key="llamacpp",
    model_name="default",
)

if client.health_check():
    print("llama.cpp server is running!")
```

---

## vLLM

### Setup

1. Install [vLLM](https://github.com/vllm-project/vllm):
   ```bash
   pip install vllm
   ```
2. Start the server:
   ```bash
   python -m vllm.entrypoints.openai.api_server --model path/to/model --port 8000
   ```
3. vLLM serves an OpenAI-compatible API at `http://localhost:8000/v1`

### Usage with Model Lens

```bash
# Auto-detect
python apps/cli/modellens.py run --provider vllm --quick

# Use a specific model
python apps/cli/modellens.py run --provider vllm --models my-model
```

### Usage in Python

```python
from providers.vllm import VLLMClient

client = VLLMClient(
    base_url="http://localhost:8000",
    api_key="vllm",
    model_name="my-model",
)

if client.health_check():
    print("vLLM is running!")
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
