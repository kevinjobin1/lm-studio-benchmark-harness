"""Tests for provider clients (Ollama, Open WebUI, Jan, llama.cpp, vLLM)."""

import json
import unittest
from unittest.mock import patch, MagicMock

from providers.base import Model, RunRequest, ProviderAdapter
from providers.openai_compatible import OpenAICompatibleProvider
from providers.openwebui import OpenWebUIClient, DEFAULT_OPENWEBUI_URL
from providers.jan import JanClient, DEFAULT_JAN_URL
from providers.llamacpp import LlamaCppClient, DEFAULT_LLAMACPP_URL
from providers.vllm import VLLMClient, DEFAULT_VLLM_URL


class MockResponse:
    """Fake requests.Response for testing."""
    def __init__(self, json_data=None, status_code=200, text=""):
        self._json = json_data or {}
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._json


# ── OpenAICompatibleProvider (base class) ──────────────────────

class TestOpenAICompatibleProvider(unittest.TestCase):
    def setUp(self):
        # Patch OpenAI client init to avoid real network calls
        patcher = patch("providers.openai_compatible.OpenAI")
        self.mock_openai = patcher.start()
        self.addCleanup(patcher.stop)

        self.mock_client = MagicMock()
        self.mock_openai.return_value = self.mock_client

    def test_init_defaults(self):
        p = OpenAICompatibleProvider()
        self.assertEqual(p.base_url, "http://localhost:8000/v1")
        self.assertEqual(p.name, "openai-compatible")

    def test_init_custom_url(self):
        p = OpenAICompatibleProvider(base_url="http://my-server:9000/v1")
        self.assertEqual(p.base_url, "http://my-server:9000/v1")

    @patch("providers.openai_compatible.requests.get")
    def test_health_check_ok(self, mock_get):
        mock_get.return_value = MockResponse(status_code=200)
        p = OpenAICompatibleProvider()
        self.assertTrue(p.health_check())
        mock_get.assert_called_once()

    @patch("providers.openai_compatible.requests.get")
    def test_health_check_fail(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        p = OpenAICompatibleProvider()
        self.assertFalse(p.health_check())

    @patch("providers.openai_compatible.requests.get")
    def test_list_models(self, mock_get):
        mock_get.return_value = MockResponse(json_data={
            "data": [
                {"id": "model-a", "metadata": {"parameter_count": "7B", "quantization": "Q4_K_M"}},
                {"id": "model-b", "metadata": {"parameter_count": "13B"}},
            ]
        })
        p = OpenAICompatibleProvider()
        models = p.list_models()
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0].id, "model-a")
        self.assertEqual(models[0].parameters, "7B")
        self.assertEqual(models[0].quantization, "Q4_K_M")

    def test_run_prompt(self):
        """Test run_prompt with mocked chat completion."""
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="Hello!"))]
        mock_completion.usage = MagicMock(prompt_tokens=5, completion_tokens=3)
        self.mock_client.chat.completions.create.return_value = mock_completion

        p = OpenAICompatibleProvider()
        result = p.run_prompt(RunRequest(prompt="Say hello", model="test"))

        self.assertEqual(result.response, "Hello!")
        self.assertEqual(result.provider, "openai-compatible")
        self.assertEqual(result.prompt_tokens, 5)
        self.assertEqual(result.completion_tokens, 3)
        self.assertEqual(result.total_tokens, 8)

    def test_chat_completion_streaming(self):
        """Test streaming chat completion."""
        chunks = []
        for text in ["Hel", "lo", "!"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content=text))]
            chunks.append(chunk)

        self.mock_client.chat.completions.create.return_value = iter(chunks)

        p = OpenAICompatibleProvider()
        text, metrics = p.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            stream=True,
        )

        self.assertEqual(text, "Hello!")
        self.assertEqual(metrics.completion_tokens, 3)
        self.assertGreater(metrics.tokens_per_second, 0)


# ── Open WebUI ─────────────────────────────────────────────────

class TestOpenWebUIClient(unittest.TestCase):
    def setUp(self):
        patcher = patch("providers.openwebui.OpenAI")
        self.mock_openai = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_openai.return_value = MagicMock()

    def test_defaults(self):
        c = OpenWebUIClient()
        self.assertEqual(c.name, "open-webui")
        self.assertEqual(c.default_port, 3000)

    @patch("providers.openwebui.requests.get")
    def test_list_models(self, mock_get):
        mock_get.return_value = MockResponse(json_data={
            "data": [
                {"id": "qwen2.5:7b", "meta": {"name": "Qwen 2.5", "size": "7B"}},
            ]
        })
        c = OpenWebUIClient()
        models = c.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].name, "Qwen 2.5")


# ── Jan ────────────────────────────────────────────────────────

class TestJanClient(unittest.TestCase):
    def setUp(self):
        patcher = patch("providers.jan.OpenAI")
        self.mock_openai = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_openai.return_value = MagicMock()

    def test_defaults(self):
        c = JanClient()
        self.assertEqual(c.name, "jan")
        self.assertEqual(c.default_port, 1337)

    @patch("providers.jan.requests.get")
    def test_list_models(self, mock_get):
        mock_get.return_value = MockResponse(json_data={
            "data": [
                {"id": "llama3.2", "metadata": {"parameters": "3.2B", "size_bytes": 2000000000}},
            ]
        })
        c = JanClient()
        models = c.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].parameters, "3.2B")


# ── llama.cpp ────────────────────────────────────────────────────

class TestLlamaCppClient(unittest.TestCase):
    def setUp(self):
        patcher = patch("providers.llamacpp.OpenAI")
        self.mock_openai = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_openai.return_value = MagicMock()

    def test_defaults(self):
        c = LlamaCppClient()
        self.assertEqual(c.name, "llama.cpp")
        self.assertEqual(c.default_port, 8080)

    @patch("providers.llamacpp.requests.get")
    def test_list_models_empty_fallback(self, mock_get):
        """llama.cpp returns empty list when only one model is loaded — fallback to model_name."""
        mock_get.return_value = MockResponse(json_data={"data": []})
        c = LlamaCppClient(model_name="my-model.gguf")
        models = c.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "my-model.gguf")

    @patch("providers.llamacpp.requests.get")
    def test_health_check_fallback(self, mock_get):
        """llama.cpp falls back to /health when /models fails."""
        mock_get.side_effect = [
            Exception("Connection refused"),  # /models fails
            MockResponse(status_code=200),   # /health succeeds
        ]
        c = LlamaCppClient()
        self.assertTrue(c.health_check())


# ── vLLM ───────────────────────────────────────────────────────

class TestVLLMClient(unittest.TestCase):
    def setUp(self):
        patcher = patch("providers.vllm.OpenAI")
        self.mock_openai = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_openai.return_value = MagicMock()

    def test_defaults(self):
        c = VLLMClient()
        self.assertEqual(c.name, "vllm")
        self.assertEqual(c.default_port, 8000)

    @patch("providers.vllm.requests.get")
    def test_list_models_empty_fallback(self, mock_get):
        """vLLM returns empty list for single-model serving — fallback to model_name."""
        mock_get.return_value = MockResponse(json_data={"data": []})
        c = VLLMClient(model_name="meta-llama/Llama-3.2-1B")
        models = c.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "meta-llama/Llama-3.2-1B")

    @patch("providers.vllm.requests.get")
    def test_health_check_fallback(self, mock_get):
        """vLLM falls back to /health when /models fails."""
        mock_get.side_effect = [
            Exception("Connection refused"),  # /models fails
            MockResponse(status_code=200),   # /health succeeds
        ]
        c = VLLMClient()
        self.assertTrue(c.health_check())


if __name__ == "__main__":
    unittest.main()
