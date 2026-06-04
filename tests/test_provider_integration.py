"""Integration tests for provider clients against a real mock HTTP server.

Uses Python's built-in http.server module (no external dependencies).
Each provider client connects to a locally spun-up mock server to verify
its HTTP layer (health_check, list_models) works end-to-end.
"""

import json
import threading
import time
import unittest
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from click.testing import CliRunner

from providers.base import Model
from providers.openai_compatible import OpenAICompatibleProvider
from providers.openwebui import OpenWebUIClient
from providers.jan import JanClient
from providers.llamacpp import LlamaCppClient
from providers.vllm import VLLMClient
from providers.ollama import OllamaClient
from apps.cli.modellens import cli
from apps.cli.commands.utils import (
    _list_provider_models,
    _list_models_detailed,
    validate_provider_connection,
)


# ── Mock HTTP Server ────────────────────────────────────────────


class MockOpenAIHandler(BaseHTTPRequestHandler):
    """Request handler that serves OpenAI-compatible responses."""

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/v1/models", "/api/v1/models", "/models"):
            self._send_json(
                {
                    "data": [
                        {
                            "id": "mock-model-1",
                            "metadata": {
                                "parameter_count": "7B",
                                "quantization": "Q4_K_M",
                                "model_size": 4000000000,
                            },
                        },
                        {
                            "id": "mock-model-2",
                            "metadata": {
                                "parameter_count": "13B",
                            },
                        },
                    ]
                }
            )
        elif self.path == "/health":
            self._send_json({"status": "ok"})
        elif self.path == "/api/tags":
            # Ollama native endpoint
            self._send_json(
                {
                    "models": [
                        {
                            "name": "llama3.2:latest",
                            "details": {
                                "quantization_level": "Q4_0",
                                "family": "llama",
                                "format": "gguf",
                            },
                            "size": 2000000000,
                        }
                    ]
                }
            )
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/v1/chat/completions":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            req = json.loads(body)
            model = req.get("model", "default")
            stream = req.get("stream", False)

            if stream:
                # SSE streaming response
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                chunks = [
                    {
                        "id": "chatcmpl-mock",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": model,
                        "choices": [
                            {"index": 0, "delta": {"content": "Hello"}, "finish_reason": None}
                        ],
                    },
                    {
                        "id": "chatcmpl-mock",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": model,
                        "choices": [
                            {"index": 0, "delta": {"content": " world"}, "finish_reason": None}
                        ],
                    },
                    {
                        "id": "chatcmpl-mock",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": model,
                        "choices": [{"index": 0, "delta": {"content": "!"}, "finish_reason": None}],
                    },
                    {
                        "id": "chatcmpl-mock",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": model,
                        "choices": [
                            {"index": 0, "delta": {"content": None}, "finish_reason": "stop"}
                        ],
                    },
                ]
                for chunk in chunks:
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            else:
                self._send_json(
                    {
                        "id": "chatcmpl-mock",
                        "object": "chat.completion",
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": "Hello from mock server!",
                                },
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 5,
                            "total_tokens": 15,
                        },
                    }
                )
        else:
            self.send_response(404)
            self.end_headers()


class HealthOnlyHandler(BaseHTTPRequestHandler):
    """Handler that only serves /health, returning 404 everywhere else."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()


def start_mock_server(port: int = 0) -> int:
    """Start the mock HTTP server on an available port. Returns (actual_port, server)."""
    server = HTTPServer(("127.0.0.1", port), MockOpenAIHandler)
    if port == 0:
        port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)  # Give the server time to start
    return port, server


def start_health_only_server():
    """Start a server that only serves /health. Returns (server, port)."""
    srv = HTTPServer(("127.0.0.1", 0), HealthOnlyHandler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.1)
    return srv, port


# ── Integration Tests ───────────────────────────────────────────


class TestProviderIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port, cls.server = start_mock_server()
        cls.base_url = f"http://127.0.0.1:{cls.port}/v1"
        cls.api_v1_base_url = f"http://127.0.0.1:{cls.port}/api/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    # ── Base class ──────────────────────────────────────────────

    def test_openai_compatible_health_check(self):
        p = OpenAICompatibleProvider(base_url=self.base_url)
        self.assertTrue(p.health_check())

    def test_openai_compatible_list_models(self):
        p = OpenAICompatibleProvider(base_url=self.base_url)
        models = p.list_models()
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0].id, "mock-model-1")
        self.assertEqual(models[0].parameters, "7B")
        self.assertEqual(models[0].quantization, "Q4_K_M")
        self.assertEqual(models[0].size_bytes, 4000000000)

    def test_openai_compatible_chat_completion(self):
        """Test chat_completion talks to the real mock server."""
        p = OpenAICompatibleProvider(base_url=self.base_url, model_name="mock-model")
        text, metrics = p.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            stream=False,
        )
        self.assertEqual(text, "Hello from mock server!")
        self.assertEqual(metrics.prompt_tokens, 10)
        self.assertEqual(metrics.completion_tokens, 5)
        self.assertEqual(metrics.total_tokens, 15)
        self.assertGreater(metrics.tokens_per_second, 0)

    def test_openai_compatible_chat_completion_streaming(self):
        """Test streaming chat_completion against the mock SSE server."""
        p = OpenAICompatibleProvider(base_url=self.base_url, model_name="mock-model")
        text, metrics = p.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            stream=True,
        )
        self.assertEqual(text, "Hello world!")
        self.assertEqual(metrics.completion_tokens, 3)
        self.assertGreater(metrics.tokens_per_second, 0)

    def test_openai_compatible_run_prompt(self):
        """Test run_prompt end-to-end against the mock server."""
        from providers.base import RunRequest

        p = OpenAICompatibleProvider(base_url=self.base_url, model_name="mock-model")
        result = p.run_prompt(RunRequest(prompt="Say hello", model="mock-model"))
        self.assertEqual(result.response, "Hello from mock server!")
        self.assertEqual(result.provider, "openai-compatible")
        self.assertEqual(result.prompt_tokens, 10)
        self.assertEqual(result.completion_tokens, 5)

    # ── Open WebUI ──────────────────────────────────────────────

    def test_openwebui_list_models(self):
        c = OpenWebUIClient(base_url=self.api_v1_base_url)
        models = c.list_models()
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0].id, "mock-model-1")

    # ── Jan ─────────────────────────────────────────────────────

    def test_jan_list_models(self):
        c = JanClient(base_url=self.base_url)
        models = c.list_models()
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0].id, "mock-model-1")
        self.assertEqual(models[0].parameters, "7B")

    # ── llama.cpp ───────────────────────────────────────────────

    def test_llamacpp_list_models(self):
        c = LlamaCppClient(base_url=self.base_url)
        models = c.list_models()
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0].id, "mock-model-1")

    def test_llamacpp_health_check_fallback(self):
        """When /models returns 404, llama.cpp should fall back to /health."""
        srv, port = start_health_only_server()
        try:
            c = LlamaCppClient(base_url=f"http://127.0.0.1:{port}/v1")
            self.assertTrue(c.health_check())
        finally:
            srv.shutdown()

    # ── vLLM ────────────────────────────────────────────────────

    def test_vllm_list_models(self):
        c = VLLMClient(base_url=self.base_url)
        models = c.list_models()
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0].id, "mock-model-1")

    def test_vllm_health_check_fallback(self):
        """When /models returns 404, vLLM should fall back to /health."""
        srv, port = start_health_only_server()
        try:
            c = VLLMClient(base_url=f"http://127.0.0.1:{port}/v1")
            self.assertTrue(c.health_check())
        finally:
            srv.shutdown()

    # ── Ollama ──────────────────────────────────────────────────

    def test_ollama_list_models(self):
        c = OllamaClient(base_url=f"http://127.0.0.1:{self.port}")
        models = c.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "llama3.2:latest")
        self.assertEqual(models[0].name, "llama3.2")
        self.assertEqual(models[0].parameters, "latest")
        self.assertEqual(models[0].quantization, "Q4_0")

    def test_ollama_health_check(self):
        c = OllamaClient(base_url=f"http://127.0.0.1:{self.port}")
        self.assertTrue(c.health_check())

    def test_ollama_chat_completion(self):
        """OllamaClient has its own chat_completion — test it against the mock server."""
        c = OllamaClient(base_url=f"http://127.0.0.1:{self.port}", model_name="mock-model")
        text, metrics = c.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            stream=False,
        )
        self.assertEqual(text, "Hello from mock server!")
        self.assertEqual(metrics.prompt_tokens, 10)
        self.assertEqual(metrics.completion_tokens, 5)

    def test_ollama_chat_completion_streaming(self):
        c = OllamaClient(base_url=f"http://127.0.0.1:{self.port}", model_name="mock-model")
        text, metrics = c.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            stream=True,
        )
        self.assertEqual(text, "Hello world!")
        self.assertEqual(metrics.completion_tokens, 3)
        self.assertGreater(metrics.tokens_per_second, 0)

    def test_ollama_run_prompt(self):
        from providers.base import RunRequest

        c = OllamaClient(base_url=f"http://127.0.0.1:{self.port}", model_name="mock-model")
        result = c.run_prompt(RunRequest(prompt="Say hello", model="mock-model"))
        self.assertEqual(result.response, "Hello from mock server!")
        self.assertEqual(result.provider, "ollama")
        self.assertEqual(result.prompt_tokens, 10)
        self.assertEqual(result.completion_tokens, 5)

    def test_offline_health_check(self):
        """health_check should return False when the server is offline."""
        c = OpenAICompatibleProvider(base_url="http://127.0.0.1:65432/v1")
        self.assertFalse(c.health_check())


class TestHealthCLIIntegration(unittest.TestCase):
    """Integration tests for the `modellens health` CLI command against a mock server."""

    @classmethod
    def setUpClass(cls):
        cls.port, cls.server = start_mock_server()
        cls.base_url = f"http://127.0.0.1:{cls.port}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_health_reachable_vllm(self):
        """health against reachable vLLM server shows healthy + model count."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "health",
                "--provider",
                "vllm",
                "--api-base",
                self.base_url,
            ],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("healthy", result.output.lower())
        self.assertIn("2 available", result.output)

    def test_health_reachable_json(self):
        """health --json against reachable server returns structured JSON."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "health",
                "--provider",
                "vllm",
                "--api-base",
                self.base_url,
                "--json",
            ],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        data = json.loads(result.output)
        self.assertEqual(data["provider"], "vllm")
        self.assertTrue(data["reachable"])
        self.assertEqual(data["status_code"], 200)
        self.assertEqual(data["models_detected"], 2)
        self.assertIsNone(data["error"])

    def test_health_llamacpp_fallback(self):
        """llama.cpp health falls back to /health when /models is unavailable."""
        srv, port = start_health_only_server()

        try:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "health",
                    "--provider",
                    "llama.cpp",
                    "--api-base",
                    f"http://127.0.0.1:{port}/v1",
                ],
            )
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("healthy", result.output.lower())
        finally:
            srv.shutdown()

    def test_health_llamacpp_fallback_json(self):
        """llama.cpp health --json with /health fallback returns correct JSON."""
        srv, port = start_health_only_server()

        try:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "health",
                    "--provider",
                    "llama.cpp",
                    "--api-base",
                    f"http://127.0.0.1:{port}/v1",
                    "--json",
                ],
            )
            self.assertEqual(result.exit_code, 0, msg=result.output)

            data = json.loads(result.output)
            self.assertEqual(data["provider"], "llama.cpp")
            self.assertTrue(data["reachable"])
            self.assertEqual(data["status_code"], 200)
            self.assertEqual(data["models_detected"], 0)
            self.assertIsNone(data["error"])
        finally:
            srv.shutdown()


class TestProviderUtilsIntegration(unittest.TestCase):
    """Integration tests for CLI utility functions against a mock server."""

    @classmethod
    def setUpClass(cls):
        cls.port, cls.server = start_mock_server()
        cls.base_url = f"http://127.0.0.1:{cls.port}/v1"
        cls.ollama_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_list_provider_models_openai_compatible(self):
        models = _list_provider_models("jan", self.base_url, "")
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0], "mock-model-1")
        self.assertEqual(models[1], "mock-model-2")

    def test_list_provider_models_ollama(self):
        models = _list_provider_models("ollama", self.ollama_url, "")
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0], "llama3.2:latest")

    def test_list_models_detailed_openai_compatible(self):
        models = _list_models_detailed("vllm", self.base_url, "")
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]["id"], "mock-model-1")
        self.assertEqual(models[0]["parameters"], "7B")
        self.assertEqual(models[0]["quantization"], "Q4_K_M")
        self.assertEqual(models[0]["size_bytes"], 4000000000)

    def test_list_models_detailed_ollama(self):
        models = _list_models_detailed("ollama", self.ollama_url, "")
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["id"], "llama3.2:latest")
        self.assertEqual(models[0]["name"], "llama3.2")
        self.assertEqual(models[0]["parameters"], "latest")
        self.assertEqual(models[0]["quantization"], "Q4_0")

    def test_validate_provider_connection_ok(self):
        self.assertTrue(validate_provider_connection("jan", self.base_url))

    def test_validate_provider_connection_fail(self):
        import io, sys

        # Point to a non-existent port; suppress printed error output
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            with self.assertRaises(SystemExit):
                validate_provider_connection("jan", "http://127.0.0.1:65432/v1")
        finally:
            sys.stdout = old_stdout


if __name__ == "__main__":
    unittest.main(verbosity=2)
