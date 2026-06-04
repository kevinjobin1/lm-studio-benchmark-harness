"""
vLLM provider adapter — high-throughput LLM serving with OpenAI-compatible API.

Usage:
    vllm = VLLMClient(base_url="http://localhost:8000/v1")
    models = vllm.list_models()
    response, metrics = vllm.chat_completion(...)

vLLM (https://github.com/vllm-project/vllm) is a high-throughput serving
engine for LLMs. It exposes an OpenAI-compatible API at /v1.

Start the server:
    python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.2-1B
"""

from typing import List

import requests

from packages.logging import get_logger
from .openai_compatible import OpenAICompatibleProvider
from .base import Model

logger = get_logger(__name__)


DEFAULT_VLLM_URL = "http://localhost:8000/v1"


class VLLMClient(OpenAICompatibleProvider):
    """
    vLLM provider adapter.

    vLLM serves LLMs with PagedAttention for high throughput and efficient
    GPU utilization. It exposes a fully OpenAI-compatible API.

    Default endpoint: http://localhost:8000/v1
    """

    name = "vllm"
    default_port = 8000
    default_url = DEFAULT_VLLM_URL
    default_api_key = "vllm"

    def list_models(self) -> List[Model]:
        """List models from vLLM's /v1/models endpoint."""
        models: List[Model] = []
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    mid = m.get("id", "unknown")
                    meta = m.get("metadata", {}) or {}
                    models.append(Model(
                        id=mid,
                        name=mid.split(":")[0] if ":" in mid else mid,
                        provider=self.name,
                        parameters=meta.get("parameter_count", "unknown"),
                        quantization=meta.get("quantization", "unknown"),
                        size_bytes=meta.get("model_size", 0),
                    ))
            # vLLM typically serves a single model; if the list is empty
            # but we know the model name, add it manually.
            if not models and self.model_name:
                models.append(Model(
                    id=self.model_name,
                    name=self.model_name,
                    provider=self.name,
                    parameters="unknown",
                    quantization="unknown",
                    size_bytes=0,
                ))
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.debug("vLLM list_models failed (connection/timeout): %s", e)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning("vLLM error listing models: %s", e)
        return models

    def health_check(self) -> bool:
        """Check if vLLM server is reachable.

        Uses /v1/models first, falls back to /health.
        """
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=5)
            if resp.status_code == 200:
                return True
        except (requests.ConnectionError, requests.Timeout):
            pass
        # vLLM has a /health endpoint for Kubernetes liveness probes
        try:
            resp = requests.get(
                self.base_url.removesuffix("/v1") + "/health",
                timeout=5,
            )
            return resp.status_code == 200
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.debug("vLLM health check fallback failed (connection/timeout): %s", e)
            return False
        except requests.RequestException as e:
            logger.warning("vLLM health check fallback failed: %s", e)
            return False


__all__ = ["VLLMClient", "DEFAULT_VLLM_URL"]
