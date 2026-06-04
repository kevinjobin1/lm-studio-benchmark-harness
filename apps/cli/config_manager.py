#!/usr/bin/env python3
"""
Unified Configuration Manager for Model Lens.

Handles loading, merging, and validating config.yaml for both the
general benchmark suite and DevBench v2.  The old config.json
(DevBench-only flat JSON) is deprecated but can still be loaded
with a deprecation warning.

Usage::

    from apps.cli.config_manager import ConfigManager

    mgr = ConfigManager("apps/cli/config.yaml")
    cfg = mgr.load()                         # UnifiedConfig dataclass
    print(cfg.general.samples_per_benchmark)
    print(cfg.devbench.evaluation.runs_per_prompt)
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema
import yaml

# ── Dataclasses ──────────────────────────────────────────────────────


@dataclass
class GeneralBenchmarksConfig:
    """Per-benchmark enable/disable flags."""

    mmlu_pro: Dict[str, Any] = field(default_factory=dict)
    gsm8k: Dict[str, Any] = field(default_factory=dict)
    aime: Dict[str, Any] = field(default_factory=dict)
    humaneval: Dict[str, Any] = field(default_factory=dict)
    swe_bench_lite: Dict[str, Any] = field(default_factory=dict)
    ifeval: Dict[str, Any] = field(default_factory=dict)
    needle_in_haystack: Dict[str, Any] = field(default_factory=dict)
    bfcl: Dict[str, Any] = field(default_factory=dict)
    speed_latency: Dict[str, Any] = field(default_factory=dict)
    memory: Dict[str, Any] = field(default_factory=dict)
    creativity: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneralConfig:
    """General benchmark suite configuration."""

    samples_per_benchmark: int = 100
    quick_mode_samples: int = 10
    benchmarks: GeneralBenchmarksConfig = field(default_factory=GeneralBenchmarksConfig)


@dataclass
class DevBenchEndpointConfig:
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "lm-studio"
    timeout: int = 30


@dataclass
class DevBenchGenerationConfig:
    temperature: float = 0.2
    max_tokens: int = 1000
    top_p: float = 0.9
    stream: bool = True


@dataclass
class DevBenchEvaluationConfig:
    runs_per_prompt: int = 5
    parallel_execution: bool = True
    max_workers: int = 3
    execution_grounded: Dict[str, Any] = field(default_factory=dict)
    statistical: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DevBenchOutputConfig:
    directory: str = "devbench_results"
    formats: List[str] = field(default_factory=lambda: ["json", "csv", "markdown"])
    charts: List[str] = field(default_factory=lambda: ["radar", "leaderboard"])


@dataclass
class DevBenchConfig:
    """DevBench v2 configuration (mirrors the ``devbench:`` YAML section)."""

    description: str = "DevBench v2"
    models: Dict[str, Any] = field(default_factory=dict)
    endpoint: DevBenchEndpointConfig = field(default_factory=DevBenchEndpointConfig)
    generation: DevBenchGenerationConfig = field(default_factory=DevBenchGenerationConfig)
    prompts: Dict[str, Any] = field(default_factory=dict)
    evaluation: DevBenchEvaluationConfig = field(default_factory=DevBenchEvaluationConfig)
    metrics: Dict[str, Any] = field(default_factory=dict)
    output: DevBenchOutputConfig = field(default_factory=DevBenchOutputConfig)
    hardware: Dict[str, Any] = field(default_factory=dict)
    reproducibility: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedConfig:
    """Top-level unified configuration."""

    version: str = "2.0.0"
    api: Dict[str, Any] = field(default_factory=dict)
    model: Dict[str, Any] = field(default_factory=dict)
    general: GeneralConfig = field(default_factory=GeneralConfig)
    devbench: DevBenchConfig = field(default_factory=DevBenchConfig)
    output: Dict[str, Any] = field(default_factory=dict)
    # Raw data for accessing non-validated extras
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)


# ── Config Manager ───────────────────────────────────────────────────


class ConfigManager:
    """Load, validate, and provide typed access to unified config."""

    _SCHEMA_FILENAME = "config_schema.json"

    def __init__(self, config_path: str = "apps/cli/config.yaml"):
        self.config_path = Path(config_path)
        self._schema_path = self._resolve_schema()
        self._config: Optional[UnifiedConfig] = None

    # ── Public API ────────────────────────────────────────────────

    def load(self) -> UnifiedConfig:
        """Load and validate config, returning a typed UnifiedConfig."""
        if self._config is not None:
            return self._config

        raw = self._load_raw()

        # Validate against schema
        if self._schema_path is not None and self._schema_path.exists():
            self._validate(raw)

        self._config = self._build_config(raw)
        return self._config

    def get_general_config(self) -> GeneralConfig:
        """Return the ``general:`` section."""
        return self.load().general

    def get_devbench_config(self) -> DevBenchConfig:
        """Return the ``devbench:`` section."""
        return self.load().devbench

    def get_api_config(self) -> Dict[str, Any]:
        """Return the shared ``api:`` section."""
        return self.load().api

    def get_output_config(self) -> Dict[str, Any]:
        """Return the shared ``output:`` section."""
        return self.load().output

    # ── Internal ───────────────────────────────────────────────────

    def _resolve_schema(self) -> Path:
        """Locate config_schema.json relative to config file or CWD."""
        # Try alongside the config file first
        sibling = self.config_path.parent / self._SCHEMA_FILENAME
        if sibling.exists():
            return sibling
        # Fall back to CWD
        return Path(self._SCHEMA_FILENAME)

    def _load_raw(self) -> Dict[str, Any]:
        """Load raw config data — YAML preferred, JSON with deprecation."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        if self.config_path.suffix in (".yaml", ".yml"):
            with open(self.config_path) as f:
                return yaml.safe_load(f) or {}

        # Legacy JSON path (deprecated)
        if self.config_path.suffix == ".json":
            print(
                f"[config_manager] DEPRECATED: {self.config_path} is a legacy JSON config. "
                f"Migrate to config.yaml — the unified YAML format includes both "
                f"'general:' and 'devbench:' sections.",
                file=sys.stderr,
            )
            with open(self.config_path) as f:
                return json.load(f)

        raise ValueError(f"Unsupported config format: {self.config_path.suffix}")

    def _validate(self, raw: Dict[str, Any]) -> None:
        """Validate raw config against the unified JSON Schema."""
        try:
            with open(self._schema_path) as f:
                schema = json.load(f)
            jsonschema.validate(instance=raw, schema=schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Configuration validation failed: {e.message}") from e
        except FileNotFoundError:
            print(
                f"[config_manager] Warning: schema file not found at {self._schema_path} — "
                f"skipping validation.",
                file=sys.stderr,
            )

    def _build_config(self, raw: Dict[str, Any]) -> UnifiedConfig:
        """Construct typed UnifiedConfig from raw dict."""
        # General section
        gen_raw = raw.get("general", {})
        benchmarks_raw = gen_raw.get("benchmarks", {})
        general = GeneralConfig(
            samples_per_benchmark=gen_raw.get("samples_per_benchmark", 100),
            quick_mode_samples=gen_raw.get("quick_mode_samples", 10),
            benchmarks=GeneralBenchmarksConfig(
                mmlu_pro=benchmarks_raw.get("mmlu_pro", {}),
                gsm8k=benchmarks_raw.get("gsm8k", {}),
                aime=benchmarks_raw.get("aime", {}),
                humaneval=benchmarks_raw.get("humaneval", {}),
                swe_bench_lite=benchmarks_raw.get("swe_bench_lite", {}),
                ifeval=benchmarks_raw.get("ifeval", {}),
                needle_in_haystack=benchmarks_raw.get("needle_in_haystack", {}),
                bfcl=benchmarks_raw.get("bfcl", {}),
                speed_latency=benchmarks_raw.get("speed_latency", {}),
                memory=benchmarks_raw.get("memory", {}),
                creativity=benchmarks_raw.get("creativity", {}),
            ),
        )

        # DevBench section
        db_raw = raw.get("devbench", {})
        db_endpoint = db_raw.get("endpoint", {})
        db_generation = db_raw.get("generation", {})
        db_evaluation = db_raw.get("evaluation", {})
        db_output = db_raw.get("output", {})

        devbench = DevBenchConfig(
            description=db_raw.get("description", "DevBench v2"),
            models=db_raw.get("models", {}),
            endpoint=DevBenchEndpointConfig(
                base_url=db_endpoint.get("base_url", "http://localhost:1234/v1"),
                api_key=db_endpoint.get("api_key", "lm-studio"),
                timeout=db_endpoint.get("timeout", 30),
            ),
            generation=DevBenchGenerationConfig(
                temperature=db_generation.get("temperature", 0.2),
                max_tokens=db_generation.get("max_tokens", 1000),
                top_p=db_generation.get("top_p", 0.9),
                stream=db_generation.get("stream", True),
            ),
            prompts=db_raw.get("prompts", {}),
            evaluation=DevBenchEvaluationConfig(
                runs_per_prompt=db_evaluation.get("runs_per_prompt", 5),
                parallel_execution=db_evaluation.get("parallel_execution", True),
                max_workers=db_evaluation.get("max_workers", 3),
                execution_grounded=db_evaluation.get("execution_grounded", {}),
                statistical=db_evaluation.get("statistical", {}),
            ),
            metrics=db_raw.get("metrics", {}),
            output=DevBenchOutputConfig(
                directory=db_output.get("directory", "devbench_results"),
                formats=db_output.get("formats", ["json", "csv", "markdown"]),
                charts=db_output.get("charts", ["radar", "leaderboard"]),
            ),
            hardware=db_raw.get("hardware", {}),
            reproducibility=db_raw.get("reproducibility", {}),
        )

        return UnifiedConfig(
            version=raw.get("version", "2.0.0"),
            api=raw.get("api", {}),
            model=raw.get("model", {}),
            general=general,
            devbench=devbench,
            output=raw.get("output", {}),
            _raw=raw,
        )


# ── Convenience ──────────────────────────────────────────────────────


def load_config(config_path: str = "apps/cli/config.yaml") -> UnifiedConfig:
    """Load and validate the unified config from a YAML file.

    Args:
        config_path: Path to config.yaml (or deprecated config.json).

    Returns:
        A validated ``UnifiedConfig`` dataclass.
    """
    return ConfigManager(config_path).load()


# ── Quick smoke test ─────────────────────────────────────────────────

if __name__ == "__main__":
    mgr = ConfigManager("apps/cli/config.yaml")
    try:
        config = mgr.load()
        print(f"✓ Loaded unified config v{config.version}")
        print(f"  General benchmarks: {config.general.samples_per_benchmark} samples")
        print(f"  DevBench: {config.devbench.description}")
        print(f"  DevBench runs/prompt: {config.devbench.evaluation.runs_per_prompt}")
        print(f"  Output dir: {config.output.get('directory', 'results')}")
    except FileNotFoundError:
        print("✗ config.yaml not found — skipping self-test")
    except ValueError as e:
        print(f"✗ Validation error: {e}")
