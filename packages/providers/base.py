"""
ProviderAdapter — abstract base for local LLM providers (LM Studio, Ollama, etc.).

Matches the ProviderAdapter interface from ROADMAP.md.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, AsyncGenerator
from datetime import datetime
from urllib.parse import urlparse, urljoin


@dataclass
class APICallMetrics:
    """Tracks metrics for individual API calls — shared across all providers."""

    ttft: float  # Time to first token in seconds
    total_time: float  # Total generation time in seconds
    tokens_per_second: float
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int


@dataclass
class Model:
    """A model available on a provider."""

    id: str
    name: str
    provider: str
    parameters: str = "unknown"
    quantization: str = "unknown"
    size_bytes: int = 0


@dataclass
class RunRequest:
    """A request to run a prompt against a provider."""

    prompt: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 4096
    top_p: float = 1.0
    system_prompt: Optional[str] = None
    stream: bool = False


@dataclass
class Token:
    """A single token from a streaming response."""

    text: str
    index: int
    finish_reason: Optional[str] = None


@dataclass
class RunResult:
    """Result from a completed prompt execution."""

    response: str
    model: str
    provider: str
    ttft_ms: float  # Time to first token (ms)
    total_time_ms: float  # Total execution time (ms)
    tokens_per_second: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    hardware: Optional[Dict] = None  # HardwareInfo.to_dict() snapshot
    trace_id: Optional[str] = None  # Link to a captured Trace (V2)


@dataclass
class ProviderMetrics:
    """Hardware/performance metrics for the provider."""

    cpu_percent: float = 0.0
    ram_used_mb: float = 0.0
    ram_total_mb: float = 0.0
    gpu_available: bool = False
    gpu_used_mb: float = 0.0
    swap_used_mb: float = 0.0


class ProviderAdapter(ABC):
    """
    Abstract base for local LLM providers.
    All providers (LM Studio, Ollama, llama.cpp, etc.) implement this interface.
    """

    name: str
    default_port: int

    @abstractmethod
    def list_models(self) -> List[Model]:
        """Return all models available on this provider."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the provider is reachable and healthy."""
        ...

    @abstractmethod
    def run_prompt(self, request: RunRequest) -> RunResult:
        """Run a single prompt and return the result."""
        ...

    @abstractmethod
    def chat_completion(
        self,
        messages: List[Dict],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        top_p: float = 1.0,
        stream: bool = False,
    ) -> "tuple[str, object]":
        """OpenAI-compatible chat completion. Returns (response_text, metrics)."""
        ...

    def collect_metrics(self) -> ProviderMetrics:
        """Collect hardware/performance metrics from the provider."""
        import psutil

        process = psutil.Process()
        ram = process.memory_info().rss / 1024 / 1024
        total_ram = psutil.virtual_memory().total / 1024 / 1024
        cpu = process.cpu_percent(interval=0.1)
        return ProviderMetrics(
            cpu_percent=cpu,
            ram_used_mb=ram,
            ram_total_mb=total_ram,
        )


# ── URL Utility Functions ─────────────────────────────────────────


def normalize_base_url(url: str) -> str:
    """Normalize a base URL by stripping the trailing slash.

    This is used for consistent internal storage so that path joining
    via ``url_join()`` always works predictably.

    Example:
        normalize_base_url("http://localhost:8000/v1/")  # → "http://localhost:8000/v1"
    """
    return url.rstrip("/")


def get_root_url(url: str) -> str:
    """Extract scheme + netloc from a URL, dropping the entire path.

    Used when a provider exposes an endpoint at the server root (e.g.
    ``/health`` or ``/api/tags``) that lives outside the ``/v1`` namespace.

    Example:
        get_root_url("http://localhost:8000/v1")       # → "http://localhost:8000"
        get_root_url("http://localhost:3000/api/v1")   # → "http://localhost:3000"
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def url_join(base: str, path: str) -> str:
    """Safely join a path segment onto a base URL using :func:`urllib.parse.urljoin`.

    Unlike raw string concatenation (``f"{base}/{path}"``), this correctly
    handles edge cases such as the base already ending with a slash or the
    path starting with one.

    Example:
        url_join("http://localhost:8000/v1", "models")     # → "http://localhost:8000/v1/models"
        url_join("http://localhost:8000/v1/", "models")   # → "http://localhost:8000/v1/models"
        url_join("http://localhost:8000/", "health")      # → "http://localhost:8000/health"
    """
    # urljoin treats the last segment as a file unless there is a trailing
    # slash, so ensure the base ends with "/" before joining.
    base = base if base.endswith("/") else base + "/"
    return urljoin(base, path.lstrip("/"))


__all__ = [
    "ProviderAdapter",
    "APICallMetrics",
    "Model",
    "RunRequest",
    "RunResult",
    "Token",
    "ProviderMetrics",
    "normalize_base_url",
    "get_root_url",
    "url_join",
]
