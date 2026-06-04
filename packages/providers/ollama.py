"""
Ollama provider adapter — local LLM provider via OpenAI-compatible API.

Usage:
    ollama = OllamaClient(base_url="http://localhost:11434/v1")
    models = ollama.list_models()
    response, metrics = ollama.chat_completion(...)
"""

import time
import requests
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

from packages.logging import get_logger
from .base import (
    ProviderAdapter,
    Model,
    RunRequest,
    RunResult,
    ProviderMetrics,
    APICallMetrics,
    normalize_base_url,
    url_join,
)

logger = get_logger(__name__)


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_V1_URL = "http://localhost:11434/v1"


class OllamaClient(ProviderAdapter):
    """
    Ollama provider adapter using the OpenAI-compatible API (Ollama >= 0.1.28).
    Falls back to the native /api/tags endpoint for model listing.
    """

    name = "ollama"
    default_port = 11434

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        api_key: str = "ollama",
        model_name: str = "",
        timeout: int = 120,
        max_retries: int = 3,
    ):
        self.base_url = normalize_base_url(base_url)
        self.v1_url = url_join(self.base_url, "v1")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

        # OpenAI-compatible client (Ollama serves this at /v1)
        self.client = OpenAI(
            base_url=self.v1_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    # ── ProviderAdapter interface ──────────────────────────────────

    def health_check(self) -> bool:
        """Check if Ollama is reachable. Tries /v1/models first, falls back to /api/tags."""
        try:
            resp = requests.get(f"{self.v1_url}/models", timeout=5)
            if resp.status_code == 200:
                return True
        except (requests.ConnectionError, requests.Timeout):
            pass
        # Fall back to native endpoint for older Ollama (< 0.1.28)
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.debug("Ollama health check failed (connection/timeout): %s", e)
            return False
        except requests.RequestException as e:
            logger.warning("Ollama health check failed: %s", e)
            return False

    def list_models(self) -> List[Model]:
        """List all models available in Ollama."""
        models: List[Model] = []

        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    # Ollama model name comes as "llama3.2:latest" or "gemma:7b"
                    full_name = m.get("name", "unknown")
                    parts = full_name.split(":")
                    base_name = parts[0]
                    tag = parts[1] if len(parts) > 1 else "latest"

                    models.append(
                        Model(
                            id=full_name,
                            name=base_name,
                            provider="ollama",
                            parameters=tag,
                            quantization=m.get("details", {}).get("quantization_level", "unknown"),
                            size_bytes=m.get("size", 0),
                        )
                    )
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.debug("Ollama list_models failed (connection/timeout): %s", e)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning("Ollama error listing models: %s", e)

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
            provider="ollama",
            ttft_ms=metrics.ttft * 1000,
            total_time_ms=total_ms,
            tokens_per_second=metrics.tokens_per_second,
            prompt_tokens=metrics.prompt_tokens,
            completion_tokens=metrics.completion_tokens,
            total_tokens=metrics.total_tokens,
        )

    # ── OpenAI-compatible interface ────────────────────────────────

    def chat_completion(
        self,
        messages: List[Dict],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        top_p: float = 1.0,
        stream: bool = False,
    ) -> Tuple[str, object]:
        """
        Chat completion via Ollama's OpenAI-compatible /v1/chat/completions.
        Returns (response_text, metrics_object).
        """
        start_time = time.time()
        first_token_time: Optional[float] = None

        if stream:
            # Streaming mode for accurate TTFT
            response_text = ""
            accumulated_tokens = 0
            stream_response = self.client.chat.completions.create(
                model=self.model_name or "llama3.2",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=True,
            )

            for chunk in stream_response:
                if chunk.choices[0].delta.content:
                    if first_token_time is None:
                        first_token_time = time.time()
                    response_text += chunk.choices[0].delta.content
                    accumulated_tokens += 1

            total_time = time.time() - start_time
            ttft = (first_token_time - start_time) if first_token_time else total_time
            prompt_tokens = sum(len(str(m["content"])) for m in messages) // 4
            completion_tokens = accumulated_tokens
        else:
            response = self.client.chat.completions.create(
                model=self.model_name or "llama3.2",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=False,
            )

            response_text = response.choices[0].message.content or ""
            total_time = time.time() - start_time
            ttft = total_time

            prompt_tokens = (
                getattr(response.usage, "prompt_tokens", 0) if hasattr(response, "usage") else 0
            )
            completion_tokens = (
                getattr(response.usage, "completion_tokens", 0) if hasattr(response, "usage") else 0
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

        return response_text, metrics


__all__ = ["OllamaClient", "DEFAULT_OLLAMA_URL"]
