#!/usr/bin/env python3
"""
Unified Results Schema for Model Lens

Provides a portable, comparable, and versioned output format for all benchmark runs.
Compatible with the static dashboard and CI pipeline.
"""

import json
import time
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime


# ── Agentic Score (importable without skills dep) ────────────────

@dataclass
class AgenticScoreData:
    """Agentic/tool-use evaluation scores for a benchmark result.

    Mirrors skills.types.AgenticScore but with no skills dependency —
    so results_schema can be used independently.
    """
    overall_agentic_score: float = 0.0
    validity_score: float = 0.0
    json_valid: bool = False
    schema_valid: bool = False
    planning_score: float = 0.0
    correct_sequence: bool = False
    unnecessary_steps: int = 0
    skill_correctness_score: float = 0.0
    correct_tool_choices: int = 0
    total_tool_choices: int = 0
    constraint_adherence_score: float = 0.0
    skills_in_allowlist: int = 0
    skills_outside_allowlist: int = 0
    hallucinated_skills: List[str] = field(default_factory=list)
    tool_selection_accuracy: float = 0.0
    hallucination_rate: float = 0.0
    schema_validity_score: float = 0.0
    planning_efficiency: float = 0.0


@dataclass
class HardwareInfo:
    """Hardware and system information."""
    platform: str = ""
    processor: str = ""
    memory_gb: int = 0
    architecture: str = ""


@dataclass
class MetricScores:
    """Core evaluation metrics for a model."""
    coding_score: float = 0.0
    reasoning_score: float = 0.0
    instruction_score: float = 0.0
    frontend_score: float = 0.0
    math_score: float = 0.0
    debugging_score: float = 0.0
    overall_score: float = 0.0


@dataclass
class PerformanceMetrics:
    """Performance and latency metrics."""
    tokens_per_sec: float = 0.0
    normalized_tps: float = 0.0
    ttft_ms: float = 0.0
    total_latency_ms: float = 0.0
    memory_pressure_mb: float = 0.0


@dataclass
class RunStats:
    """Statistical summary of multiple runs."""
    mean: float = 0.0
    std: float = 0.0
    min: float = 0.0
    max: float = 0.0
    median: float = 0.0
    runs: int = 1
    confidence_95: Optional[Tuple[float, float]] = None
    coefficient_of_variation: float = 0.0


@dataclass
class FailureBreakdown:
    """Failure taxonomy breakdown."""
    hallucinated_api: int = 0
    wrong_async_usage: int = 0
    incorrect_json_schema: int = 0
    syntax_error: int = 0
    logic_error: int = 0
    type_error: int = 0
    missing_import: int = 0
    stale_closure: int = 0
    race_condition: int = 0
    incorrect_di: int = 0
    oververbose: int = 0
    missed_constraint: int = 0
    other: int = 0
    # Agentic-specific failure categories
    hallucinated_tool: int = 0
    wrong_action_sequence: int = 0
    invalid_action_json: int = 0

    @property
    def total_failures(self) -> int:
        return sum(asdict(self).values())


@dataclass
class BenchmarkResult:
    """Unified benchmark result for a single model run."""
    # Identity
    run_id: str = ""
    model: str = ""
    model_metadata: Dict[str, str] = field(default_factory=dict)
    hardware: HardwareInfo = field(default_factory=HardwareInfo)

    # Timing
    timestamp: str = ""
    git_sha: str = ""
    git_branch: str = ""

    # Scores
    metrics: MetricScores = field(default_factory=MetricScores)
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)

    # Stats
    stats: RunStats = field(default_factory=RunStats)

    # Details
    failures: FailureBreakdown = field(default_factory=FailureBreakdown)
    category_scores: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Config snapshot
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    prompt_version: str = ""
    packs_used: List[str] = field(default_factory=list)
    seed: Optional[int] = None

    # Agentic evaluation (optional)
    agentic_score: Optional[AgenticScoreData] = None
    agentic_mode: bool = False

    # V2 Trace capture (optional)
    trace_id: Optional[str] = None
    trace_file: Optional[str] = None  # Path to trace JSON file

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            "run_id": self.run_id,
            "model": self.model,
            "model_metadata": self.model_metadata,
            "hardware": asdict(self.hardware),
            "timestamp": self.timestamp,
            "git_sha": self.git_sha,
            "git_branch": self.git_branch,
            "metrics": asdict(self.metrics),
            "performance": asdict(self.performance),
            "stats": {
                "mean": self.stats.mean,
                "std": self.stats.std,
                "min": self.stats.min,
                "max": self.stats.max,
                "median": self.stats.median,
                "runs": self.stats.runs,
                "confidence_95": self.stats.confidence_95,
                "coefficient_of_variation": self.stats.coefficient_of_variation,
            },
            "failures": asdict(self.failures),
            "category_scores": self.category_scores,
            "config_snapshot": self.config_snapshot,
            "prompt_version": self.prompt_version,
            "packs_used": self.packs_used,
            "seed": self.seed,
            "agentic_score": asdict(self.agentic_score) if self.agentic_score else None,
            "agentic_mode": self.agentic_mode,
            "trace_id": self.trace_id,
            "trace_file": self.trace_file,
        }
        return d

    def to_json(self, path: Optional[Path] = None, indent: int = 2) -> str:
        """Serialize to JSON. If path provided, write to file."""
        json_str = json.dumps(self.to_dict(), indent=indent, default=str, ensure_ascii=False)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_str)
        return json_str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkResult":
        """Deserialize from dictionary."""
        result = cls(
            run_id=data.get("run_id", ""),
            model=data.get("model", ""),
            model_metadata=data.get("model_metadata", {}),
            timestamp=data.get("timestamp", ""),
            git_sha=data.get("git_sha", ""),
            git_branch=data.get("git_branch", ""),
            prompt_version=data.get("prompt_version", ""),
            packs_used=data.get("packs_used", []),
            seed=data.get("seed"),
        )

        hw = data.get("hardware", {})
        result.hardware = HardwareInfo(
            platform=hw.get("platform", ""),
            processor=hw.get("processor", ""),
            memory_gb=hw.get("memory_gb", 0),
            architecture=hw.get("architecture", ""),
        )

        m = data.get("metrics", {})
        result.metrics = MetricScores(
            coding_score=m.get("coding_score", 0),
            reasoning_score=m.get("reasoning_score", 0),
            instruction_score=m.get("instruction_score", 0),
            frontend_score=m.get("frontend_score", 0),
            math_score=m.get("math_score", 0),
            debugging_score=m.get("debugging_score", 0),
            overall_score=m.get("overall_score", 0),
        )

        p = data.get("performance", {})
        result.performance = PerformanceMetrics(
            tokens_per_sec=p.get("tokens_per_sec", 0),
            normalized_tps=p.get("normalized_tps", 0),
            ttft_ms=p.get("ttft_ms", 0),
            total_latency_ms=p.get("total_latency_ms", 0),
            memory_pressure_mb=p.get("memory_pressure_mb", 0),
        )

        s = data.get("stats", {})
        result.stats = RunStats(
            mean=s.get("mean", 0),
            std=s.get("std", 0),
            min=s.get("min", 0),
            max=s.get("max", 0),
            median=s.get("median", 0),
            runs=s.get("runs", 1),
            confidence_95=tuple(s["confidence_95"]) if s.get("confidence_95") else None,
            coefficient_of_variation=s.get("coefficient_of_variation", 0),
        )

        f = data.get("failures", {})
        result.failures = FailureBreakdown(**{k: f.get(k, 0) for k in asdict(FailureBreakdown()).keys()})

        result.category_scores = data.get("category_scores", {})
        result.config_snapshot = data.get("config_snapshot", {})

        # Agentic score (optional) — filter to only known fields
        agentic_data = data.get("agentic_score")
        if agentic_data:
            known_fields = {f.name for f in fields(AgenticScoreData)}
            filtered = {k: v for k, v in agentic_data.items() if k in known_fields}
            result.agentic_score = AgenticScoreData(**filtered)
        result.agentic_mode = data.get("agentic_mode", False)

        # V2 Trace data (optional)
        result.trace_id = data.get("trace_id")
        result.trace_file = data.get("trace_file")

        return result


class ResultsCollector:
    """Collect and serialize benchmark results in the unified schema."""

    def __init__(self, output_dir: str = "results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[BenchmarkResult] = []

    @staticmethod
    def gather_system_info() -> HardwareInfo:
        """Gather hardware and system information."""
        info = HardwareInfo()

        try:
            info.platform = platform.platform()
            info.processor = platform.processor()
            info.architecture = platform.machine()

            # Try to get memory info
            try:
                import psutil
                info.memory_gb = int(psutil.virtual_memory().total / (1024 ** 3))
            except ImportError:
                info.memory_gb = 0
        except Exception:
            pass

        return info

    @staticmethod
    def gather_git_info() -> Tuple[str, str]:
        """Gather git SHA and branch info."""
        sha, branch = "", ""

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                sha = result.stdout.strip()
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
        except Exception:
            pass

        return sha, branch

    def create_result(self,
                      model: str,
                      metrics: MetricScores,
                      performance: PerformanceMetrics,
                      stats: RunStats,
                      failures: Optional[FailureBreakdown] = None,
                      model_metadata: Optional[Dict[str, str]] = None,
                      config_snapshot: Optional[Dict[str, Any]] = None,
                      packs_used: Optional[List[str]] = None,
                      seed: Optional[int] = None,
                      prompt_version: str = "v1") -> BenchmarkResult:
        """Create a new BenchmarkResult with system info auto-populated."""
        hardware = self.gather_system_info()
        git_sha, git_branch = self.gather_git_info()
        timestamp = datetime.now().isoformat()
        run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{model}"

        return BenchmarkResult(
            run_id=run_id,
            model=model,
            model_metadata=model_metadata or {},
            hardware=hardware,
            timestamp=timestamp,
            git_sha=git_sha,
            git_branch=git_branch,
            metrics=metrics,
            performance=performance,
            stats=stats,
            failures=failures or FailureBreakdown(),
            config_snapshot=config_snapshot or {},
            prompt_version=prompt_version,
            packs_used=packs_used or [],
            seed=seed,
        )

    def add_result(self, result: BenchmarkResult):
        """Add a result to the collection."""
        self.results.append(result)

    def save_all(self) -> Dict[str, str]:
        """Save all results to JSON files."""
        paths = {}

        # Save individual results
        for result in self.results:
            file_path = self.output_dir / f"{result.run_id}.json"
            result.to_json(file_path)
            paths[result.run_id] = str(file_path)

        # Save aggregated results
        aggregated = self._aggregate()
        agg_path = self.output_dir / "results.json"
        with open(agg_path, 'w') as f:
            json.dump(aggregated, f, indent=2, default=str)
        paths["aggregated"] = str(agg_path)

        # Save latest pointer
        latest_path = self.output_dir / "latest.json"
        with open(latest_path, 'w') as f:
            json.dump({"latest_run": aggregated["runs"][-1]["run_id"] if aggregated["runs"] else None}, f)
        paths["latest"] = str(latest_path)

        return paths

    def _aggregate(self) -> Dict[str, Any]:
        """Aggregate all results into a summary."""
        return {
            "version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "total_models": len(set(r.model for r in self.results)),
            "total_runs": len(self.results),
            "runs": [r.to_dict() for r in self.results],
        }

    def load_all(self) -> List[BenchmarkResult]:
        """Load all individual result files from the output directory."""
        results = []
        for json_file in sorted(self.output_dir.glob("*.json")):
            if json_file.name in ("results.json", "latest.json"):
                continue
            try:
                with open(json_file) as f:
                    data = json.load(f)
                results.append(BenchmarkResult.from_dict(data))
            except Exception:
                continue
        return results


def merge_results(results: List[BenchmarkResult]) -> Dict[str, Any]:
    """Merge multiple results for leaderboard display."""
    # Group by model
    by_model: Dict[str, List[BenchmarkResult]] = {}
    for r in results:
        by_model.setdefault(r.model, []).append(r)

    models = []
    for model, model_results in by_model.items():
        best = max(model_results, key=lambda r: r.metrics.overall_score)
        models.append({
            "model": model,
            "metadata": best.model_metadata,
            "best_run_id": best.run_id,
            "metrics": asdict(best.metrics),
            "performance": asdict(best.performance),
            "stats": {
                "mean": best.stats.mean,
                "std": best.stats.std,
                "runs": best.stats.runs,
            },
            "total_failures": best.failures.total_failures,
        })

    # Sort by overall score
    models.sort(key=lambda m: m["metrics"]["overall_score"], reverse=True)

    return {
        "leaderboard": models,
        "generated_at": datetime.now().isoformat(),
    }
