"""
Open WebUI provider adapter — local LLM provider via OpenAI-compatible API.

Open WebUI serves an OpenAI-compatible API at http://localhost:3000/api/v1.

Usage:
    client = OpenWebUIClient()
    models = client.list_models()
    response, metrics = client.chat_completion(...)
"""

import time
import requests
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

from .base import (
    ProviderAdapter,
    Model,
    RunRequest,
    RunResult,
    ProviderMetrics,
    APICallMetrics,
)


DEFAULT_OPENWEBUI_URL = "http://localhost:3000"
DEFAULT_OPENWEBUI_V1_URL = "http://localhost:3000/api/v1"


class OpenWebUIClient(ProviderAdapter):
    """
    Open WebUI provider adapter using the OpenAI-compatible API.
    Open WebUI exposes /api/v1/chat/completions matching the OpenAI spec.
    """

    name = "open-webui"
    default_port = 3000

    def __init__(
        self,
        base_url: str = DEFAULT_OPENWEBUI_URL,
        api_key: str = "open-webui",
        model_name: str = "",
        timeout: int = 120,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.v1_url = f"{self.base_url}/api/v1"
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

        self.client = OpenAI(
            base_url=self.v1_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    # ── ProviderAdapter interface ──────────────────────────────────

    def health_check(self) -> bool:
        """Check if Open WebUI is reachable."""
        try:
            resp = requests.get(f"{self.v1_url}/models", timeout=5)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        # Fall back to root health endpoint
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[Model]:
        """List all models available in Open WebUI."""
        models: List[Model] = []
        try:
            resp = requests.get(f"{self.v1_url}/models", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    mid = m.get("id", "unknown")
                    models.append(Model(
                        id=mid,
                        name=mid,
                        provider="open-webui",
                        parameters=m.get("details", {}).get("parameter_size", "unknown"),
                        quantization="unknown",
                        size_bytes=m.get("size", 0),
                    ))
        except Exception as e:
            print(f"[open-webui] Error listing models: {e}")
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
            provider="open-webui",
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
        """Chat completion via Open WebUI's OpenAI-compatible API."""
        start_time = time.time()
        first_token_time: Optional[float] = None

        if stream:
            response_text = ""
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

            prompt_tokens = getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') else 0
            completion_tokens = getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') else 0

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


__all__ = ["OpenWebUIClient", "DEFAULT_OPENWEBUI_URL"]
