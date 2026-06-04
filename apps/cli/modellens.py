#!/usr/bin/env python3
"""
Model Lens — Observe. Compare. Understand.

Unified CLI for local AI model benchmarking and observability.
Commands are organized in apps/cli/commands/ for maintainability.

Usage:
    modellens run --quick
    modellens info
    modellens models
    modellens leaderboard results/
    modellens workload run --model qwen3.5-9b
"""

import os
import sys

# Ensure the project root is discoverable when the script is run directly
# (e.g. python apps/cli/modellens.py) instead of via the installed console
# script entry point (pip install -e .). This makes both packages/
# (core, benchmarks, etc.) and apps/ (apps.cli.*) importable.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
_PACKAGES_DIR = os.path.join(_PROJECT_ROOT, "packages")
if _PACKAGES_DIR not in sys.path:
    sys.path.insert(0, _PACKAGES_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import click

from apps.cli.commands.run import run
from apps.cli.commands.info import info
from apps.cli.commands.models import models
from apps.cli.commands.health import health
from apps.cli.commands.publish import publish
from apps.cli.commands.leaderboard import leaderboard
from apps.cli.commands.workload import workload
from apps.cli.commands.migrate import migrate
from apps.cli.commands.auth import auth
from apps.cli.commands.sse import sse
from apps.cli.commands.trace import trace
from apps.cli.commands.skill import skill
from apps.cli.commands.mcp import mcp
from apps.cli.commands.cache import cache as cache_command
from apps.cli.commands.otel import otel
from apps.cli.commands.regression import regression


@click.group()
@click.version_option(version="0.1.0", prog_name="modellens")
def cli():
    """
    🔬 Model Lens — Observe. Compare. Understand.

    A local-first observability and evaluation platform for local AI models.
    """
    pass


# Register commands
cli.add_command(run)
cli.add_command(info)
cli.add_command(models)
cli.add_command(health)
cli.add_command(publish)
cli.add_command(leaderboard)
cli.add_command(workload)
cli.add_command(migrate)
cli.add_command(auth)
cli.add_command(sse)
cli.add_command(trace)
cli.add_command(skill)
cli.add_command(mcp)
cli.add_command(cache_command)
cli.add_command(otel)
cli.add_command(regression)


def main():
    cli()


if __name__ == "__main__":
    main()
