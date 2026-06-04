"""
Jan provider adapter — local LLM provider with OpenAI-compatible API.

Usage:
    jan = JanClient(base_url="http://localhost:1337/v1")
    models = jan.list_models()
    response, metrics = jan.chat_completion(...)

Jan (https://jan.ai) is a local-first AI platform that runs models
locally. It exposes an OpenAI-compatible API at /v1.
"""

from typing import List

import requests

from packages.logging import get_logger
from .openai_compatible import OpenAICompatibleProvider
from .base import Model

logger = get_logger(__name__)


DEFAULT_JAN_URL = "http://localhost:1337/v1"


class JanClient(OpenAICompatibleProvider):
    """
    Jan provider adapter.

    Jan (https://jan.ai) runs LLMs locally and exposes an OpenAI-compatible
    API for programmatic access. Models are managed via Jan's model hub.

    Default endpoint: http://localhost:1337/v1
    """

    name = "jan"
    default_port = 1337
    default_url = DEFAULT_JAN_URL
    default_api_key = "jan"

    def list_models(self) -> List[Model]:
        """List models from Jan's /v1/models endpoint."""
        models: List[Model] = []
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    mid = m.get("id", "unknown")
                    meta = m.get("metadata", {}) or {}
                    # Jan typically stores model info in metadata
                    models.append(Model(
                        id=mid,
                        name=meta.get("name", mid),
                        provider=self.name,
                        parameters=meta.get("parameters") or meta.get("parameter_count", "unknown"),
                        quantization=meta.get("quantization", "unknown"),
                        size_bytes=meta.get("size_bytes", 0),
                    ))
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.debug("Jan list_models failed (connection/timeout): %s", e)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning("Jan error listing models: %s", e)
        return models


__all__ = ["JanClient", "DEFAULT_JAN_URL"]
