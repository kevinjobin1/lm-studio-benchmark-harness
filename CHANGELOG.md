# Changelog

## Unreleased

### Added
- Unified `modellens` CLI with `run`, `info`, and `leaderboard` commands
- Ollama provider adapter (`packages/providers/ollama.py`)
- `ProviderAdapter` base class with shared dataclasses (`packages/providers/base.py`)
- Model name validation against live provider listing
- Provider auto-detection (LM Studio → Ollama fallback)
- Dashboard provider display in connection badge

### Changed
- Restructured codebase to monorepo (`apps/` + `packages/`)
- Renamed `benchmark/` → `packages/core/`, `benchmarks/` → `packages/benchmarks/`
- Moved `integrations/` + `adapters/` → `packages/providers/`
- Moved `dashboard/` → `apps/dashboard/`
- Moved `APICallMetrics` from `core/benchmark.py` to `providers/base.py`
- Reorganized documentation: split README into README + VISION + ARCHITECTURE + CONTRIBUTING + CHANGELOG

### Removed
- `bench_apple_silicon.py` (v1, superseded by v2)
- `x_thread_generator.py` (unused)
- `dashboard-cleanup-spec.md` (completed)
- Old `results/` subdirectories (stale data)

### Fixed
- Stale closure bug in `BenchmarkStatusBadge.tsx` (model always null in `[]`-dep effect)
- Cross-package dependency: Ollama no longer imports from `core`
- Ollama `health_check` now falls back to `/api/tags` for older versions

## 0.1.0

Initial release — LM Studio benchmark harness with:
- 11 general benchmarks (MMLU-Pro, GSM8K, HumanEval, etc.)
- DevBench v2 (TypeScript/NestJS/React with statistical rigor)
- Astro + React dashboard
- Prompt packs (React, NestJS, debugging, agentic)
- LM Studio provider adapter
- GitHub Pages deployment (GitHub Actions)
