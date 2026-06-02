"""
Workload Evaluation Framework (V2).

Evaluates models on real-world project codebases — React, NestJS, Rust, Python.
Generates realistic coding tasks from project files, runs models against them,
and scores outputs on practical developer utility.
"""

from .project_loader import ProjectLoader, ProjectFile, Project
from .task_generator import (
    TaskGenerator, WorkloadTask, TaskDifficulty, TaskType
)
from .workload_runner import WorkloadRunner, WorkloadResult
from .workload_scorer import WorkloadScorer, WorkloadScore

__all__ = [
    "ProjectLoader", "ProjectFile", "Project",
    "TaskGenerator", "WorkloadTask", "TaskDifficulty", "TaskType",
    "WorkloadRunner", "WorkloadResult",
    "WorkloadScorer", "WorkloadScore",
]
