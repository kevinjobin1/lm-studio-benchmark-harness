#!/usr/bin/env python3
"""
Configuration Manager for LM Studio DevBench
Handles canonical config schema, validation, and loading
"""

import json
import jsonschema
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class BenchmarkConfig:
    """Benchmark configuration dataclass."""

    version: str
    benchmark_name: str
    description: str
    models: Dict[str, Any]
    endpoint: Dict[str, Any]
    generation: Dict[str, Any]
    prompts: Dict[str, Any]
    evaluation: Dict[str, Any]
    metrics: Dict[str, Any]
    output: Dict[str, Any]
    hardware: Dict[str, Any]
    reproducibility: Dict[str, Any]


class ConfigManager:
    """Manage benchmark configuration with validation."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.schema_path = Path("config_schema.json")
        self.config: Optional[BenchmarkConfig] = None

    def load(self) -> BenchmarkConfig:
        """Load and validate configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path) as f:
            config_data = json.load(f)

        # Validate against schema
        if self.schema_path.exists():
            self._validate(config_data)

        self.config = BenchmarkConfig(**config_data)
        return self.config

    def _validate(self, config_data: Dict[str, Any]) -> None:
        """Validate config against schema."""
        if not self.schema_path.exists():
            print("Warning: No schema file found, skipping validation")
            return

        with open(self.schema_path) as f:
            schema = json.load(f)

        try:
            jsonschema.validate(instance=config_data, schema=schema)
            print("✓ Configuration validated successfully")
        except jsonschema.ValidationError as e:
            raise ValueError(f"Configuration validation failed: {e.message}")

    def save(self, config: BenchmarkConfig) -> None:
        """Save configuration to file."""
        config_dict = {
            "version": config.version,
            "benchmark_name": config.benchmark_name,
            "description": config.description,
            "models": config.models,
            "endpoint": config.endpoint,
            "generation": config.generation,
            "prompts": config.prompts,
            "evaluation": config.evaluation,
            "metrics": config.metrics,
            "output": config.output,
            "hardware": config.hardware,
            "reproducibility": config.reproducibility,
        }

        with open(self.config_path, "w") as f:
            json.dump(config_dict, f, indent=2)

        print(f"✓ Configuration saved to {self.config_path}")

    def get_endpoint_config(self) -> Dict[str, Any]:
        """Get endpoint configuration."""
        if not self.config:
            self.load()
        return self.config.endpoint

    def get_generation_config(self) -> Dict[str, Any]:
        """Get generation configuration."""
        if not self.config:
            self.load()
        return self.config.generation

    def get_evaluation_config(self) -> Dict[str, Any]:
        """Get evaluation configuration."""
        if not self.config:
            self.load()
        return self.config.evaluation

    def get_prompt_config(self) -> Dict[str, Any]:
        """Get prompt configuration."""
        if not self.config:
            self.load()
        return self.config.prompts


def load_config(config_path: str = "config.json") -> BenchmarkConfig:
    """Convenience function to load configuration."""
    manager = ConfigManager(config_path)
    return manager.load()


if __name__ == "__main__":
    # Test config loading
    manager = ConfigManager()
    config = manager.load()
    print(f"Loaded config: {config.benchmark_name} v{config.version}")
