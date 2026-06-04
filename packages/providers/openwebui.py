"""
Open WebUI provider adapter — local LLM provider with OpenAI-compatible API.

Usage:
    openwebui = OpenWebUIClient(base_url="http://localhost:3000/api/v1")
    models = openwebui.list_models()
    response, metrics = openwebui.chat_completion(...)

Open WebUI exposes an OpenAI-compatible API at /api/v1 for external clients.
"""

from typing import List

import requests

from packages.modellens_logging import get_logger
from .openai_compatible import OpenAICompatibleProvider
from .base import Model

logger = get_logger(__name__)


DEFAULT_OPENWEBUI_URL = "http://localhost:3000/api/v1"


class OpenWebUIClient(OpenAICompatibleProvider):
    """
    Open WebUI provider adapter.

    Open WebUI (https://github.com/open-webui/open-webui) is a web-based
    interface for running LLMs locally. It exposes an OpenAI-compatible
    API for programmatic access.

    Default endpoint: http://localhost:3000/api/v1
    """

    name = "open-webui"
    default_port = 3000
    default_url = DEFAULT_OPENWEBUI_URL
    default_api_key = "open-webui"

    def list_models(self) -> List[Model]:
        """List models from Open WebUI's /api/v1/models endpoint."""
        models: List[Model] = []
        try:
            # api_base already contains /api/v1 — just append /models
            resp = requests.get(f"{self.base_url}/models", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # Open WebUI returns models in OpenAI-compatible format
                for m in data.get("data", []):
                    mid = m.get("id", "unknown")
                    info = m.get("info", {}) or {}
                    meta = m.get("meta", {}) or {}
                    models.append(
                        Model(
                            id=mid,
                            name=meta.get("name", mid),
                            provider=self.name,
                            parameters=meta.get("size", "unknown"),
                            quantization=meta.get("quantization", "unknown"),
                            size_bytes=meta.get("bytes", 0),
                        )
                    )
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.debug("Open WebUI list_models failed (connection/timeout): %s", e)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning("Open WebUI error listing models: %s", e)
        return models


__all__ = ["OpenWebUIClient", "DEFAULT_OPENWEBUI_URL"]
