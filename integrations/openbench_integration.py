"""
OpenBench integration for standardized benchmark evaluation.
"""

import subprocess
import json
import os
from typing import Dict, List, Any, Optional
from pathlib import Path


class OpenBenchRunner:
    """Runner for OpenBench benchmarks."""
    
    def __init__(self, base_url: str, model_name: str):
        self.base_url = base_url
        self.model_name = model_name
        self.check_openbench_installed()
        
    def check_openbench_installed(self):
        """Check if OpenBench is installed via uv."""
        try:
            result = subprocess.run(
                ["uv", "run", "openbench", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.installed = True
                self.use_uv = True
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Try direct openbench command
        try:
            result = subprocess.run(
                ["openbench", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.installed = True
                self.use_uv = False
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        self.installed = False
        self.use_uv = False
    
    def install_openbench(self):
        """Install OpenBench using uv."""
        print("Installing OpenBench using uv...")
        try:
            subprocess.run(
                ["uv", "pip", "install", "openbench"],
                check=True,
                timeout=300
            )
            self.installed = True
            self.use_uv = True
            print("OpenBench installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install OpenBench: {e}")
            raise
    
    def list_benchmarks(self) -> List[str]:
        """List available OpenBench benchmarks."""
        if not self.installed:
            raise RuntimeError("OpenBench is not installed")
        
        cmd = ["uv", "run", "openbench", "list"] if self.use_uv else ["openbench", "list"]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Parse output to extract benchmark names
                benchmarks = []
                for line in result.stdout.split('\n'):
                    if line.strip() and not line.startswith(' '):
                        benchmarks.append(line.strip())
                return benchmarks
            else:
                raise RuntimeError(f"Failed to list benchmarks: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout while listing benchmarks")
    
    def run_benchmark(
        self,
        benchmark: str,
        limit: Optional[int] = None,
        debug: bool = False
    ) -> Dict[str, Any]:
        """Run a single OpenBench benchmark."""
        if not self.installed:
            raise RuntimeError("OpenBench is not installed")
        
        # Build command
        cmd = ["uv", "run", "openbench", "eval"] if self.use_uv else ["openbench", "eval"]
        cmd.append(benchmark)
        cmd.extend(["--model", f"openai/{self.model_name}"])
        
        if limit:
            cmd.extend(["--limit", str(limit)])
        
        if debug:
            cmd.append("--debug")
        
        # Set API endpoint environment variable
        env = os.environ.copy()
        env["OPENAI_API_BASE"] = self.base_url
        env["OPENAI_API_KEY"] = "lm-studio"  # Default key for LM Studio
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                env=env
            )
            
            if result.returncode == 0:
                # Try to parse JSON output
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {
                        "raw_output": result.stdout,
                        "success": True
                    }
            else:
                return {
                    "error": result.stderr,
                    "success": False
                }
        except subprocess.TimeoutExpired:
            return {
                "error": "Benchmark execution timed out",
                "success": False
            }
    
    def run_benchmarks(
        self,
        benchmarks: List[str],
        limit: Optional[int] = None,
        debug: bool = False
    ) -> Dict[str, Any]:
        """Run multiple OpenBench benchmarks."""
        results = {}
        
        for benchmark in benchmarks:
            print(f"Running OpenBench benchmark: {benchmark}")
            try:
                result = self.run_benchmark(benchmark, limit, debug)
                results[benchmark] = result
            except Exception as e:
                results[benchmark] = {
                    "error": str(e),
                    "success": False
                }
        
        return results


# Mapping of our benchmark names to OpenBench benchmark names
OPENBENCH_TASK_MAPPING = {
    "mmlu_pro": "mmlu",
    "gsm8k": "gsm8k",
    "aime": "aime",
    "humaneval": "humaneval",
    # Note: OpenBench may have different task names, this is a basic mapping
    # Users should check `openbench list` for actual available benchmarks
}


def run_openbench_benchmarks(
    base_url: str,
    model_name: str,
    benchmark_names: List[str],
    limit: Optional[int] = None,
    install_if_missing: bool = False
) -> Dict[str, Any]:
    """Run OpenBench benchmarks for specified benchmark names."""
    
    runner = OpenBenchRunner(base_url, model_name)
    
    if not runner.installed and install_if_missing:
        runner.install_openbench()
    
    if not runner.installed:
        return {
            "error": "OpenBench is not installed. Run with --install-openbench or install manually using: uv pip install openbench",
            "success": False
        }
    
    # Map our benchmark names to OpenBench task names
    openbench_tasks = []
    custom_benchmarks = []
    
    for benchmark in benchmark_names:
        if benchmark in OPENBENCH_TASK_MAPPING:
            openbench_tasks.append(OPENBENCH_TASK_MAPPING[benchmark])
        else:
            custom_benchmarks.append(benchmark)
    
    results = {
        "openbench": {},
        "custom": custom_benchmarks
    }
    
    if openbench_tasks:
        try:
            eval_results = runner.run_benchmarks(
                benchmarks=openbench_tasks,
                limit=limit
            )
            results["openbench"] = eval_results
        except Exception as e:
            results["openbench"]["error"] = str(e)
    
    return results
