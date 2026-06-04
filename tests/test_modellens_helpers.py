"""
Unit tests for modellens CLI helpers: _resolve_provider, _list_models_detailed, _fmt_size.
Uses unittest.mock to simulate HTTP responses and provider detection.
"""

import unittest
from unittest.mock import patch, MagicMock

import requests

from apps.cli.commands.utils import (
    _resolve_provider,
    _list_models_detailed,
    _list_provider_models,
    _fmt_size,
)


class TestFmtSize(unittest.TestCase):
    """Tests for _fmt_size() — pure function, no mocking needed."""

    def test_zero_bytes(self):
        self.assertEqual(_fmt_size(0), "0 B")

    def test_bytes(self):
        self.assertEqual(_fmt_size(512), "512 B")
        self.assertEqual(_fmt_size(1023), "1023 B")

    def test_kilobytes(self):
        self.assertEqual(_fmt_size(1024), "1 KB")
        self.assertEqual(_fmt_size(1536), "2 KB")
        self.assertEqual(_fmt_size(512 * 1024), "512 KB")

    def test_megabytes(self):
        self.assertEqual(_fmt_size(1024**2), "1 MB")
        self.assertEqual(_fmt_size(5 * 1024**2), "5 MB")
        self.assertEqual(_fmt_size(999 * 1024**2), "999 MB")

    def test_gigabytes(self):
        self.assertEqual(_fmt_size(1024**3), "1.0 GB")
        self.assertEqual(_fmt_size(3826000000), "3.6 GB")
        self.assertEqual(_fmt_size(2 * 1024**3), "2.0 GB")
        self.assertEqual(_fmt_size(10 * 1024**3), "10.0 GB")

    def test_boundary_just_below_gb(self):
        """1023 MB should still format as MB, not GB."""
        self.assertEqual(_fmt_size(1023 * 1024**2), "1023 MB")

    def test_boundary_exact_mb_to_gb(self):
        """Exactly 1 GB should format as GB."""
        self.assertEqual(_fmt_size(1024**3), "1.0 GB")


class TestListModelsDetailed(unittest.TestCase):
    """Tests for _list_models_detailed() with mocked HTTP responses."""

    @patch("requests.get")
    def test_lm_studio_models(self, mock_get):
        """LM Studio /v1/models returns model list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "qwen3.5-9b-coder"},
                {"id": "gemma-4-e4b"},
            ]
        }
        mock_get.return_value = mock_response

        result = _list_models_detailed("lm-studio", "http://localhost:1234/v1", "lm-studio")

        mock_get.assert_called_once_with("http://localhost:1234/v1/models", timeout=5)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "qwen3.5-9b-coder")
        self.assertEqual(result[0]["provider"], "lm-studio")
        self.assertEqual(result[0]["parameters"], "unknown")
        self.assertEqual(result[0]["quantization"], "unknown")
        self.assertEqual(result[0]["size_bytes"], 0)

        self.assertEqual(result[1]["id"], "gemma-4-e4b")

    @patch("requests.get")
    def test_ollama_models_full_details(self, mock_get):
        """Ollama /api/tags returns model list with full details."""
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
            ]
        }
        mock_get.return_value = mock_response

        result = _list_models_detailed("ollama", "http://localhost:11434", "ollama")

        # Uses get_root_url to strip /v1, so calls clean URL
        mock_get.assert_called_once_with("http://localhost:11434/api/tags", timeout=5)

        self.assertEqual(len(result), 2)

        self.assertEqual(result[0]["id"], "llama3.2:latest")
        self.assertEqual(result[0]["name"], "llama3.2")
        self.assertEqual(result[0]["provider"], "ollama")
        self.assertEqual(result[0]["parameters"], "latest")
        self.assertEqual(result[0]["quantization"], "Q4_K_M")
        self.assertEqual(result[0]["size_bytes"], 3826000000)
        self.assertEqual(result[0]["family"], "llama")
        self.assertEqual(result[0]["format"], "gguf")

        self.assertEqual(result[1]["id"], "qwen2.5-coder:7b")
        self.assertEqual(result[1]["name"], "qwen2.5-coder")
        self.assertEqual(result[1]["parameters"], "7b")

    @patch("requests.get")
    def test_ollama_strips_v1_from_base_url(self, mock_get):
        """Ollama api_base with /v1 suffix should be stripped."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}
        mock_get.return_value = mock_response

        _list_models_detailed("ollama", "http://localhost:11434/v1", "ollama")

        # Should have stripped /v1 and called the clean URL
        mock_get.assert_called_once_with("http://localhost:11434/api/tags", timeout=5)

    @patch("requests.get")
    def test_non_200_response_returns_empty(self, mock_get):
        """Non-200 status → empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = _list_models_detailed("ollama", "http://localhost:11434", "ollama")
        self.assertEqual(result, [])

    @patch("requests.get")
    def test_network_error_returns_empty(self, mock_get):
        """Network error → empty list (graceful degradation)."""
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        result = _list_models_detailed("ollama", "http://localhost:11434", "ollama")
        self.assertEqual(result, [])

    @patch("requests.get")
    def test_lm_studio_missing_id_defaults(self, mock_get):
        """LM Studio model with no id field → defaults to 'unknown'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{}]}
        mock_get.return_value = mock_response

        result = _list_models_detailed("lm-studio", "http://localhost:1234/v1", "lm-studio")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "unknown")

    @patch("requests.get")
    def test_ollama_model_without_tag(self, mock_get):
        """Ollama model name without colon tag → defaults to 'latest'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "codellama",
                    "size": 1000000,
                    "details": {},
                }
            ]
        }
        mock_get.return_value = mock_response

        result = _list_models_detailed("ollama", "http://localhost:11434", "ollama")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "codellama")
        self.assertEqual(result[0]["name"], "codellama")
        self.assertEqual(result[0]["parameters"], "latest")


class TestResolveProvider(unittest.TestCase):
    """Tests for _resolve_provider() with mocked provider discovery.

    _resolve_provider now probes all discovered providers via HTTP
    (using entry-point discovery from providers.__init__). Tests mock
    requests.get to simulate provider availability.
    """

    @patch("requests.get")
    def test_detects_lm_studio_when_available(self, mock_get):
        """When LM Studio /v1/models responds 200, it should be detected first."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "some-model"}]}
        mock_get.return_value = mock_response

        provider, api_base, api_key = _resolve_provider(provider=None)

        self.assertEqual(provider, "lm-studio")
        self.assertIn("1234", api_base)  # lm-studio default port
        self.assertEqual(api_key, "lm-studio")

    @patch("requests.get")
    def test_falls_back_to_lm_studio_when_all_unreachable(self, mock_get):
        """When all providers are unreachable, defaults to lm-studio."""
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        provider, api_base, api_key = _resolve_provider(provider=None)

        self.assertEqual(provider, "lm-studio")
        self.assertIn("1234", api_base)
        self.assertEqual(api_key, "lm-studio")

    @patch("requests.get")
    def test_lm_studio_non_200_not_detected(self, mock_get):
        """LM Studio returning 500 (non-200) should not be detected."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"data": [{"id": "model"}]}
        mock_get.return_value = mock_response

        provider, api_base, api_key = _resolve_provider(provider=None)

        # All providers return 500 or non-200 → falls through to lm-studio default
        self.assertEqual(provider, "lm-studio")

    def test_respects_explicit_provider(self):
        """When provider is explicitly passed, auto-detection is skipped."""
        provider, api_base, api_key = _resolve_provider(provider="ollama")

        self.assertEqual(provider, "ollama")
        self.assertIn("11434", api_base)
        self.assertEqual(api_key, "ollama")

        provider, api_base, api_key = _resolve_provider(provider="lm-studio")

        self.assertEqual(provider, "lm-studio")
        self.assertIn("1234", api_base)
        self.assertEqual(api_key, "lm-studio")


if __name__ == "__main__":
    unittest.main()
