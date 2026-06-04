"""Tests for the modellens CLI commands using Click's CliRunner."""

import unittest
from click.testing import CliRunner

from apps.cli.modellens import cli


class TestModellensCLI(unittest.TestCase):
    """Smoke tests for the modellens CLI commands."""

    def setUp(self):
        self.runner = CliRunner()

    # ── Top-level group ──────────────────────────────────────────

    def test_cli_help(self):
        result = self.runner.invoke(cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("model lens", result.output.lower())
        self.assertIn("observe. compare. understand.", result.output.lower())

    def test_cli_version(self):
        result = self.runner.invoke(cli, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("0.1.0", result.output)

    # ── Run command ────────────────────────────────────────────

    def test_run_help(self):
        result = self.runner.invoke(cli, ["run", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("run benchmarks", result.output.lower())
        self.assertIn("--quick", result.output)
        self.assertIn("--framework", result.output)

    def test_run_quick_dryrun(self):
        """Quick mode without a live provider should exit cleanly."""
        result = self.runner.invoke(cli, ["run", "--quick", "--ci", "--provider", "lm-studio"])
        # We expect a non-zero exit because LM Studio isn't running, but the
        # command should at least parse and start executing.
        self.assertIn("lm-studio", result.output.lower())

    # ── Info command ───────────────────────────────────────────

    def test_info_help(self):
        result = self.runner.invoke(cli, ["info", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("system info", result.output.lower())
        self.assertIn("--provider", result.output)
        self.assertIn("--api-base", result.output)

    def test_info_runs(self):
        result = self.runner.invoke(cli, ["info"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("model lens", result.output.lower())

    def test_info_with_provider(self):
        """Info with --provider should show that provider's section."""
        result = self.runner.invoke(cli, ["info", "--provider", "vllm"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("vllm", result.output.lower())

    def test_info_json(self):
        """Info --json should output valid JSON."""
        result = self.runner.invoke(cli, ["info", "--json", "--provider", "lm-studio"])
        self.assertEqual(result.exit_code, 0)
        import json

        data = json.loads(result.output)
        self.assertIn("provider", data)
        self.assertIn("hardware", data)
        self.assertIn("models", data)

    # ── Models command ─────────────────────────────────────────

    def test_models_help(self):
        result = self.runner.invoke(cli, ["models", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list available models", result.output.lower())

    def test_models_json_unreachable(self):
        """Models --json should report unreachable provider gracefully."""
        result = self.runner.invoke(cli, ["models", "--json", "--provider", "lm-studio"])
        self.assertEqual(result.exit_code, 0)
        # When provider is unreachable it prints a message but doesn't crash
        self.assertIn("lm-studio", result.output.lower())

    def test_models_json_format(self):
        """Models --json should return valid structured JSON with model data."""
        from unittest.mock import patch, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "qwen3.5-9b-coder",
                    "object": "model",
                    "metadata": {
                        "parameter_count": "9B",
                        "quantization": "Q4_K_M",
                        "model_size": 5318567520,
                    },
                },
                {
                    "id": "llama3.2-3b",
                    "object": "model",
                    "metadata": {
                        "parameter_count": "3B",
                        "quantization": "Q4_0",
                        "model_size": 1987654321,
                    },
                },
            ]
        }

        with patch("requests.get", return_value=mock_response):
            result = self.runner.invoke(cli, ["models", "--json", "--provider", "vllm"])

        self.assertEqual(result.exit_code, 0, msg=result.output)

        import json

        data = json.loads(result.output)

        # Top-level structure
        self.assertEqual(data["provider"], "vllm")
        self.assertEqual(data["count"], 2)
        self.assertIsInstance(data["models"], list)
        self.assertEqual(len(data["models"]), 2)

        # Per-model fields
        first = data["models"][0]
        self.assertEqual(first["id"], "qwen3.5-9b-coder")
        self.assertEqual(first["name"], "qwen3.5-9b-coder")
        self.assertEqual(first["provider"], "vllm")
        self.assertEqual(first["parameters"], "9B")
        self.assertEqual(first["quantization"], "Q4_K_M")
        self.assertEqual(first["size_bytes"], 5318567520)

        second = data["models"][1]
        self.assertEqual(second["id"], "llama3.2-3b")
        self.assertEqual(second["name"], "llama3.2-3b")
        self.assertEqual(second["provider"], "vllm")
        self.assertEqual(second["parameters"], "3B")
        self.assertEqual(second["quantization"], "Q4_0")
        self.assertEqual(second["size_bytes"], 1987654321)

    # ── Health command ─────────────────────────────────────────

    def test_health_help(self):
        result = self.runner.invoke(cli, ["health", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("health", result.output.lower())
        self.assertIn("--provider", result.output)
        self.assertIn("--json", result.output)

    def test_health_unreachable_provider(self):
        """Health check on unreachable provider should exit with error."""
        result = self.runner.invoke(
            cli, ["health", "--provider", "lm-studio", "--api-base", "http://127.0.0.1:65432/v1"]
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("unreachable", result.output.lower())

    def test_health_json_unreachable(self):
        """Health --json on unreachable provider should still output JSON."""
        result = self.runner.invoke(
            cli,
            ["health", "--provider", "vllm", "--api-base", "http://127.0.0.1:65432/v1", "--json"],
        )
        self.assertEqual(result.exit_code, 0)
        import json

        data = json.loads(result.output)
        self.assertEqual(data["provider"], "vllm")
        self.assertFalse(data["reachable"])
        self.assertIn("error", data)

    # ── Leaderboard command ──────────────────────────────────

    def test_leaderboard_help(self):
        result = self.runner.invoke(cli, ["leaderboard", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("leaderboard", result.output.lower())

    def test_leaderboard_no_results(self):
        """Leaderboard on empty dir should report no results gracefully."""
        result = self.runner.invoke(cli, ["leaderboard", "/tmp/nonexistent_model_lens_results"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("no results", result.output.lower())

    # ── Workload command ─────────────────────────────────────

    def test_workload_help(self):
        result = self.runner.invoke(cli, ["workload", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("workload", result.output.lower())

    def test_workload_list_projects(self):
        result = self.runner.invoke(cli, ["workload", "list-projects"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("nestjs-api", result.output)
        self.assertIn("react-app", result.output)

    def test_workload_run_help(self):
        result = self.runner.invoke(cli, ["workload", "run", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--model", result.output)

    # ── Publish command ────────────────────────────────────────

    def test_publish_help(self):
        result = self.runner.invoke(cli, ["publish", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("publish", result.output.lower())


if __name__ == "__main__":
    unittest.main()
