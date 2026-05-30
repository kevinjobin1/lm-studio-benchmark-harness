#!/usr/bin/env python3
"""
Run Manifest Generator for Reproducibility
Creates run_manifest.json for OSS credibility
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import hashlib


@dataclass
class RunManifest:
    """Run manifest for reproducibility."""
    models: List[str]
    timestamp: str
    git_sha: str
    git_branch: str
    prompt_version: str
    config_version: str
    temperature: float
    max_tokens: int
    runs_per_prompt: int
    total_prompts: int
    total_runs: int
    hardware: Dict[str, Any]
    evaluation_config: Dict[str, Any]
    prompt_config: Dict[str, Any]
    checksum: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class RunManifestGenerator:
    """Generate run manifests for benchmark runs."""
    
    def __init__(self):
        self.git_sha = self._get_git_sha()
        self.git_branch = self._get_git_branch()
    
    def _get_git_sha(self) -> str:
        """Get current git SHA."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except:
            return "unknown"
    
    def _get_git_branch(self) -> str:
        """Get current git branch."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except:
            return "unknown"
    
    def _get_hardware_info(self) -> Dict[str, Any]:
        """Get hardware information."""
        import platform
        import psutil
        
        return {
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "python_version": platform.python_version()
        }
    
    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate checksum of manifest data."""
        # Exclude checksum field itself
        data_copy = data.copy()
        data_copy.pop("checksum", None)
        
        # Create deterministic string representation
        sorted_str = json.dumps(data_copy, sort_keys=True)
        return hashlib.sha256(sorted_str.encode()).hexdigest()[:16]
    
    def generate(self,
                models: List[str],
                config: Dict[str, Any],
                prompt_config: Dict[str, Any],
                evaluation_config: Dict[str, Any]) -> RunManifest:
        """Generate run manifest."""
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Calculate total runs
        total_prompts = prompt_config.get("total_count", 20)
        runs_per_prompt = evaluation_config.get("runs_per_prompt", 5)
        total_runs = total_prompts * runs_per_prompt * len(models)
        
        # Build manifest
        manifest_data = {
            "models": models,
            "timestamp": timestamp,
            "git_sha": self.git_sha,
            "git_branch": self.git_branch,
            "prompt_version": "v2.0",
            "config_version": config.get("version", "2.0.0"),
            "temperature": config.get("generation", {}).get("temperature", 0.2),
            "max_tokens": config.get("generation", {}).get("max_tokens", 1000),
            "runs_per_prompt": runs_per_prompt,
            "total_prompts": total_prompts,
            "total_runs": total_runs,
            "hardware": self._get_hardware_info(),
            "evaluation_config": evaluation_config,
            "prompt_config": prompt_config,
            "checksum": ""  # Will be calculated
        }
        
        # Calculate checksum
        checksum = self._calculate_checksum(manifest_data)
        manifest_data["checksum"] = checksum
        
        return RunManifest(**manifest_data)
    
    def save(self, manifest: RunManifest, output_dir: str = "devbench_results") -> str:
        """Save manifest to file."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        manifest_file = output_path / "run_manifest.json"
        with open(manifest_file, 'w') as f:
            f.write(manifest.to_json())
        
        return str(manifest_file)
    
    def load(self, manifest_path: str = "devbench_results/run_manifest.json") -> Optional[RunManifest]:
        """Load manifest from file."""
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            return None
        
        with open(manifest_path) as f:
            data = json.load(f)
        
        return RunManifest(**data)
    
    def verify(self, manifest: RunManifest) -> bool:
        """Verify manifest checksum."""
        data = manifest.to_dict()
        calculated_checksum = self._calculate_checksum(data)
        return calculated_checksum == manifest.checksum


def create_manifest(models: List[str],
                   config: Dict[str, Any],
                   prompt_config: Dict[str, Any],
                   evaluation_config: Dict[str, Any],
                   output_dir: str = "devbench_results") -> str:
    """Convenience function to create and save manifest."""
    generator = RunManifestGenerator()
    manifest = generator.generate(models, config, prompt_config, evaluation_config)
    return generator.save(manifest, output_dir)


if __name__ == "__main__":
    # Test manifest generation
    generator = RunManifestGenerator()
    
    test_config = {
        "version": "2.0.0",
        "generation": {"temperature": 0.2, "max_tokens": 1000}
    }
    
    test_prompt_config = {
        "total_count": 20,
        "generator": "auto"
    }
    
    test_eval_config = {
        "runs_per_prompt": 5,
        "parallel_execution": True
    }
    
    manifest = generator.generate(
        models=["test-model"],
        config=test_config,
        prompt_config=test_prompt_config,
        evaluation_config=test_eval_config
    )
    
    print("Generated manifest:")
    print(manifest.to_json())
    
    # Verify checksum
    is_valid = generator.verify(manifest)
    print(f"\nChecksum valid: {is_valid}")
