"""
Unit tests for OllamaClient — health_check() and list_models().
Uses unittest.mock to simulate HTTP responses without a running Ollama server.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock

import requests

from providers.base import Model

# Safely mock openai for this module. The mock must be in place BEFORE
# `from providers.ollama import OllamaClient` executes (module import time),
# otherwise the import fails on machines without the openai package.
# tearDownModule restores the original so other test files can use the real
# package (e.g. test_provider_integration.py).
_ORIG_OPENAI = sys.modules.get("openai")
sys.modules["openai"] = MagicMock()

from providers.ollama import OllamaClient


def tearDownModule():
    """Restore the original openai module so other test files aren't affected."""
    if _ORIG_OPENAI is not None:
        sys.modules["openai"] = _ORIG_OPENAI
    else:
        sys.modules.pop("openai", None)


class TestOllamaClientHealthCheck(unittest.TestCase):
    """Tests for OllamaClient.health_check() with mocked HTTP responses."""

    @patch("providers.ollama.requests.get")
    def test_health_check_success_v1_models(self, mock_get):
        """/v1/models returns 200 → True (primary path)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        client = OllamaClient()
        result = client.health_check()

        self.assertTrue(result)
        mock_get.assert_called_once_with("http://localhost:11434/v1/models", timeout=5)

    @patch("providers.ollama.requests.get")
    def test_health_check_fallback_to_api_tags(self, mock_get):
        """/v1/models fails, /api/tags returns 200 → True (fallback path)."""
        mock_get.side_effect = [
            requests.ConnectionError("Connection refused"),
            MagicMock(status_code=200),
        ]

        client = OllamaClient()
        result = client.health_check()

        self.assertTrue(result)
        self.assertEqual(mock_get.call_count, 2)
        mock_get.assert_any_call("http://localhost:11434/v1/models", timeout=5)
        mock_get.assert_any_call("http://localhost:11434/api/tags", timeout=5)

    @patch("providers.ollama.requests.get")
    def test_health_check_both_fail(self, mock_get):
        """Both /v1/models and /api/tags fail → False."""
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        client = OllamaClient()
        result = client.health_check()

        self.assertFalse(result)
        self.assertEqual(mock_get.call_count, 2)

    @patch("providers.ollama.requests.get")
    def test_health_check_non_200_response(self, mock_get):
        """/v1/models returns 500, /api/tags returns 500 → False."""
        mock_get.return_value = MagicMock(status_code=500)

        client = OllamaClient()
        result = client.health_check()

        self.assertFalse(result)
        self.assertEqual(mock_get.call_count, 2)

    @patch("providers.ollama.requests.get")
    def test_health_check_custom_base_url(self, mock_get):
        """Custom base_url should be used in health check endpoints."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        client = OllamaClient(base_url="http://192.168.1.100:11434")
        result = client.health_check()

        self.assertTrue(result)
        mock_get.assert_called_once_with("http://192.168.1.100:11434/v1/models", timeout=5)


class TestOllamaClientListModels(unittest.TestCase):
    """Tests for OllamaClient.list_models() with mocked HTTP responses."""

    @patch("providers.ollama.requests.get")
    def test_list_models_success_with_details(self, mock_get):
        """Full model list with all detail fields populated."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "llama3.2:latest",
                    "size": 3826000000,
                    "details": {
                        "quantization_level": "Q4_K_M",
                        "family": "llama",
                        "format": "gguf",
                    },
                },
                {
                    "name": "qwen2.5-coder:7b",
                    "size": 4678000000,
                    "details": {
                        "quantization_level": "Q4_K_M",
                        "family": "qwen2",
                        "format": "gguf",
                    },
                },
                {
                    "name": "gemma3:4b",
                    "size": 2550000000,
                    "details": {
                        "quantization_level": "Q4_0",
                        "family": "gemma",
                        "format": "gguf",
                    },
                },
            ]
        }
        mock_get.return_value = mock_response

        client = OllamaClient()
        models = client.list_models()

        mock_get.assert_called_once_with("http://localhost:11434/api/tags", timeout=10)

        self.assertEqual(len(models), 3)
        self.assertTrue(all(isinstance(m, Model) for m in models))

        self.assertEqual(models[0].id, "llama3.2:latest")
        self.assertEqual(models[0].name, "llama3.2")
        self.assertEqual(models[0].provider, "ollama")
        self.assertEqual(models[0].parameters, "latest")
        self.assertEqual(models[0].quantization, "Q4_K_M")
        self.assertEqual(models[0].size_bytes, 3826000000)

        self.assertEqual(models[1].id, "qwen2.5-coder:7b")
        self.assertEqual(models[1].name, "qwen2.5-coder")
        self.assertEqual(models[1].parameters, "7b")
        self.assertEqual(models[1].quantization, "Q4_K_M")
        self.assertEqual(models[1].size_bytes, 4678000000)

        self.assertEqual(models[2].id, "gemma3:4b")
        self.assertEqual(models[2].name, "gemma3")
        self.assertEqual(models[2].parameters, "4b")
        self.assertEqual(models[2].quantization, "Q4_0")
        self.assertEqual(models[2].size_bytes, 2550000000)

    @patch("providers.ollama.requests.get")
    def test_list_models_name_without_tag(self, mock_get):
        """Model name without tag (:latest) — tag defaults to 'latest'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "codellama",
                    "size": 3826000000,
                    "details": {"quantization_level": "Q4_0"},
                }
            ]
        }
        mock_get.return_value = mock_response

        client = OllamaClient()
        models = client.list_models()

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "codellama")
        self.assertEqual(models[0].name, "codellama")
        self.assertEqual(models[0].parameters, "latest")

    @patch("providers.ollama.requests.get")
    def test_list_models_missing_details(self, mock_get):
        """Model response with no details field — defaults to 'unknown'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "minimal-model:1.0",
                    "size": 0,
                }
            ]
        }
        mock_get.return_value = mock_response

        client = OllamaClient()
        models = client.list_models()

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].quantization, "unknown")
        self.assertEqual(models[0].size_bytes, 0)

    @patch("providers.ollama.requests.get")
    def test_list_models_empty_response(self, mock_get):
        """API returns empty models list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}
        mock_get.return_value = mock_response

        client = OllamaClient()
        models = client.list_models()

        self.assertEqual(models, [])

    @patch("providers.ollama.requests.get")
    def test_list_models_non_200_status(self, mock_get):
        """API returns non-200 status → empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        client = OllamaClient()
        models = client.list_models()

        self.assertEqual(models, [])

    @patch("providers.ollama.requests.get")
    def test_list_models_network_error(self, mock_get):
        """Network error → empty list (graceful degradation)."""
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        client = OllamaClient()
        models = client.list_models()

        self.assertEqual(models, [])

    @patch("providers.ollama.requests.get")
    def test_list_models_multiple_tags(self, mock_get):
        """Model name with path prefix should be parsed correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "registry.example.com/team/model:latest",
                    "size": 1000000,
                    "details": {},
                }
            ]
        }
        mock_get.return_value = mock_response

        client = OllamaClient()
        models = client.list_models()

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "registry.example.com/team/model:latest")
        self.assertEqual(models[0].name, "registry.example.com/team/model")
        self.assertEqual(models[0].parameters, "latest")


if __name__ == "__main__":
    unittest.main()
