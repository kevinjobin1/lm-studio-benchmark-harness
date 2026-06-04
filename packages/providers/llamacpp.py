"""
llama.cpp server provider adapter — local LLM server with OpenAI-compatible API.

Usage:
    llama = LlamaCppClient(base_url="http://localhost:8080/v1")
    models = llama.list_models()
    response, metrics = llama.chat_completion(...)

llama.cpp server (https://github.com/ggerganov/llama.cpp/tree/master/examples/server)
runs GGUF models via an HTTP server with an OpenAI-compatible /v1 API.

Start the server:
    ./server -m model.gguf --port 8080
"""

from typing import List

import requests

from packages.logging import get_logger
from .openai_compatible import OpenAICompatibleProvider
from .base import Model

logger = get_logger(__name__)


DEFAULT_LLAMACPP_URL = "http://localhost:8080/v1"


class LlamaCppClient(OpenAICompatibleProvider):
    """
    llama.cpp server provider adapter.

    llama.cpp's HTTP server exposes an OpenAI-compatible API for running
    GGUF models locally. Supports streaming, chat completions, and embeddings.

    Default endpoint: http://localhost:8080/v1
    """

    name = "llama.cpp"
    default_port = 8080
    default_url = DEFAULT_LLAMACPP_URL
    default_api_key = "llamacpp"

    def list_models(self) -> List[Model]:
        """List models from llama.cpp's /v1/models endpoint.

        Note: llama.cpp server typically runs one model at a time.
        The model list reflects the currently loaded model.
        """
        models: List[Model] = []
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    mid = m.get("id", "unknown")
                    models.append(Model(
                        id=mid,
                        name=mid.split(":")[0] if ":" in mid else mid,
                        provider=self.name,
                        parameters="unknown",
                        quantization="unknown",
                        size_bytes=0,
                    ))
            # llama.cpp often returns an empty list when only one model is loaded
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
            logger.debug("llama.cpp list_models failed (connection/timeout): %s", e)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning("llama.cpp error listing models: %s", e)
        return models

    def health_check(self) -> bool:
        """Check if llama.cpp server is reachable.

        Uses /v1/models first, falls back to /health.
        """
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=5)
            if resp.status_code == 200:
                return True
        except (requests.ConnectionError, requests.Timeout):
            pass
        # llama.cpp server has a dedicated /health endpoint
        try:
            resp = requests.get(
                self.base_url.removesuffix("/v1") + "/health",
                timeout=5,
            )
            return resp.status_code == 200
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.debug("llama.cpp health check fallback failed (connection/timeout): %s", e)
            return False
        except requests.RequestException as e:
            logger.warning("llama.cpp health check fallback failed: %s", e)
            return False


__all__ = ["LlamaCppClient", "DEFAULT_LLAMACPP_URL"]
