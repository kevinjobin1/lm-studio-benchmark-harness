"""
OpenAICompatibleProvider — base class for providers that expose an OpenAI-compatible API.

Providers that use this base:
- Open WebUI (default port 3000)
- Jan (default port 1337)
- llama.cpp server (default port 8080)
- vLLM (default port 8000)
- LM Studio (default port 1234)
- Ollama (default port 11434, /v1 path)

All implement the same ProviderAdapter interface but with different
connection parameters and model metadata.
"""

import time
from typing import Dict, List, Optional, Tuple

import requests
from openai import OpenAI

from packages.modellens_logging import get_logger
from .base import (
    ProviderAdapter,
    Model,
    RunRequest,
    RunResult,
    APICallMetrics,
    normalize_base_url,
)

try:
    from events import (
        EventBus,
        default_bus,
        TokenGeneratedEvent,
        CompletionEvent,
        ErrorEvent,
    )

    _EVENTS_AVAILABLE = True
except ImportError:
    EventBus = None  # type: ignore
    default_bus = None  # type: ignore
    TokenGeneratedEvent = None  # type: ignore
    CompletionEvent = None  # type: ignore
    ErrorEvent = None  # type: ignore
    _EVENTS_AVAILABLE = False

logger = get_logger(__name__)


class OpenAICompatibleProvider(ProviderAdapter):
    """
    Base class for providers that expose an OpenAI-compatible /v1 API.

    Subclasses only need to set `name`, `default_port`, `default_url`, and
    override `list_models()` if the provider has a non-standard model endpoint.
    """

    name: str = "openai-compatible"
    default_port: int = 8000
    default_url: str = "http://localhost:8000/v1"
    default_api_key: str = "not-needed"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: str = "",
        timeout: int = 120,
        max_retries: int = 3,
        event_bus: Optional[object] = None,
        event_source: str = "",
    ):
        self.base_url = normalize_base_url(base_url or self.default_url)
        self.api_key = api_key or self.default_api_key
        self.model_name = model_name
        self.timeout = timeout

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

        # ── Event bus integration ───────────────────────────────
        self.event_bus = event_bus if event_bus is not None else default_bus
        self._event_source = event_source or f"provider.{self.name}"
        self._events_available = _EVENTS_AVAILABLE and self.event_bus is not None

    # ── ProviderAdapter interface ────────────────────────────────

    def health_check(self) -> bool:
        """Check if the provider is reachable via /v1/models."""
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=5)
            return resp.status_code == 200
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.debug("Health check failed (connection/timeout): %s", e)
            return False
        except requests.RequestException as e:
            logger.warning("Health check failed: %s", e)
            return False

    def list_models(self) -> List[Model]:
        """List models from the provider's /v1/models endpoint."""
        models: List[Model] = []
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    mid = m.get("id", "unknown")
                    meta = m.get("metadata", {}) or {}
                    models.append(
                        Model(
                            id=mid,
                            name=mid.split(":")[0] if ":" in mid else mid,
                            provider=self.name,
                            parameters=meta.get("parameter_count", "unknown"),
                            quantization=meta.get("quantization", "unknown"),
                            size_bytes=meta.get("model_size", 0),
                        )
                    )
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.debug("Cannot list models (connection/timeout): %s", e)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning("Error listing models for %s: %s", self.name, e)
        return models

    def run_prompt(self, request: RunRequest) -> RunResult:
        """Run a single prompt and return structured results."""
        start = time.time()

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        response_text, metrics = self.chat_completion(
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            stream=request.stream,
        )

        total_ms = (time.time() - start) * 1000
        return RunResult(
            response=response_text,
            model=request.model or self.model_name,
            provider=self.name,
            ttft_ms=metrics.ttft * 1000,
            total_time_ms=total_ms,
            tokens_per_second=metrics.tokens_per_second,
            prompt_tokens=metrics.prompt_tokens,
            completion_tokens=metrics.completion_tokens,
            total_tokens=metrics.total_tokens,
        )

    def chat_completion(
        self,
        messages: List[Dict],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        top_p: float = 1.0,
        stream: bool = False,
    ) -> Tuple[str, APICallMetrics]:
        """
        Chat completion via OpenAI-compatible /v1/chat/completions.
        Returns (response_text, metrics).
        """
        start_time = time.time()
        first_token_time: Optional[float] = None
        response_text = ""
        total_time = 0.0
        ttft = 0.0
        prompt_tokens = 0
        completion_tokens = 0

        run_id = (
            getattr(self, "_current_run_id", "")
            or f"{self.name}_{self.model_name}_{int(start_time)}"
        )

        try:
            if stream:
                accumulated_tokens = 0
                stream_response = self.client.chat.completions.create(
                    model=self.model_name or "default",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    stream=True,
                )

                for chunk in stream_response:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        if first_token_time is None:
                            first_token_time = time.time()
                        token_text = chunk.choices[0].delta.content
                        response_text += token_text
                        accumulated_tokens += 1

                        # ── Emit TokenGeneratedEvent ───────────
                        if self._events_available:
                            timing_ms = (time.time() - start_time) * 1000
                            self.event_bus.emit_sync(
                                TokenGeneratedEvent(
                                    model=self.model_name,
                                    token=token_text,
                                    index=accumulated_tokens - 1,
                                    timing_ms=timing_ms,
                                    provider=self.name,
                                    run_id=run_id,
                                    source=self._event_source,
                                )
                            )

                total_time = time.time() - start_time
                ttft = (first_token_time - start_time) if first_token_time else total_time
                # Rough heuristic: ~4 characters per token for English text
                prompt_tokens = sum(len(str(m.get("content", ""))) for m in messages) // 4
                completion_tokens = accumulated_tokens
            else:
                response = self.client.chat.completions.create(
                    model=self.model_name or "default",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    stream=False,
                )

                response_text = response.choices[0].message.content or ""
                total_time = time.time() - start_time
                ttft = total_time

                usage = getattr(response, "usage", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_tokens", 0)
                    completion_tokens = getattr(usage, "completion_tokens", 0)
                else:
                    # Rough heuristic: ~4 characters per token for English text
                    prompt_tokens = sum(len(str(m.get("content", ""))) for m in messages) // 4
                    completion_tokens = len(response_text) // 4

        except Exception as e:
            total_time = time.time() - start_time
            logger.error("chat_completion error for %s: %s", self.name, e, exc_info=True)

            # ── Emit Error + failed CompletionEvent ────────────
            if self._events_available:
                self.event_bus.emit_sync(
                    ErrorEvent(
                        message=f"Provider {self.name} completion failed: {e}",
                        exception=type(e).__name__,
                        component=self.name,
                        run_id=run_id,
                        source=self._event_source,
                        severity="error",
                    )
                )
                self.event_bus.emit_sync(
                    CompletionEvent(
                        model=self.model_name,
                        response="",
                        tokens_used=0,
                        latency_ms=total_time * 1000,
                        ttft_ms=0,
                        tokens_per_second=0,
                        provider=self.name,
                        run_id=run_id,
                        source=self._event_source,
                        success=False,
                        error=str(e),
                    )
                )

            return "", APICallMetrics(
                ttft=0.0,
                total_time=total_time,
                tokens_per_second=0.0,
                total_tokens=0,
                prompt_tokens=0,
                completion_tokens=0,
            )

        total_tokens = prompt_tokens + completion_tokens
        tokens_per_second = completion_tokens / total_time if total_time > 0 else 0

        metrics = APICallMetrics(
            ttft=ttft,
            total_time=total_time,
            tokens_per_second=tokens_per_second,
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        # ── Emit CompletionEvent ────────────────────────────────
        if self._events_available:
            self.event_bus.emit_sync(
                CompletionEvent(
                    model=self.model_name,
                    response=response_text,
                    tokens_used=total_tokens,
                    latency_ms=total_time * 1000,
                    ttft_ms=ttft * 1000,
                    tokens_per_second=tokens_per_second,
                    provider=self.name,
                    run_id=run_id,
                    source=self._event_source,
                    success=True,
                )
            )

        return response_text, metrics


__all__ = ["OpenAICompatibleProvider"]
