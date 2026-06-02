# Changelog

## Unreleased

### Added
- Unified `modellens` CLI with `run`, `info`, `leaderboard`, `models`, and `publish` commands
- Ollama provider adapter (`packages/providers/ollama.py`)
- `ProviderAdapter` base class with shared dataclasses (`packages/providers/base.py`)
- Hardware detection (`packages/core/hardware.py`) — CPU, GPU, RAM, OS, architecture, Apple Silicon
- `modellens models` subcommand — list available models with parameters, quantization, size
- `modellens publish` subcommand — publish results as community leaderboard JSON
- Community leaderboard — dashboard loads published results alongside local benchmarks
- Cloudflare Pages deployment — static Astro dashboard with wrangler config
- Prompt generation — paraphrasing, variable substitution, and contextual mutation (`apps/cli/prompt_generator.py`)
- Model name validation against live provider listing
- Provider auto-detection (LM Studio → Ollama fallback)
- Dashboard provider + hardware display in connection badge
- Unit tests for `OllamaClient.health_check()` and `list_models()` (`tests/`)
- Unit tests for `_resolve_provider()`, `_list_models_detailed()`, and `_fmt_size()` (`tests/`)
- Dashboard API endpoints: `GET /api/status`, `GET /api/run-benchmark/active`, `POST /api/run-benchmark`, `GET /api/run-benchmark/logs`, `POST /api/run-benchmark/kill` (`apps/dashboard/src/pages/api/`)
- `@astrojs/node` adapter with `output: "server"` for live API routes
- `LM_STUDIO_URL` environment variable for configurable LM Studio endpoint
- `.env.example` documenting dashboard environment variables
- Dashboard README — API docs, Run Benchmark workflow, build/deploy guide
- Dashboard section in main README with API endpoints table
- `GET /api/health` endpoint — server monitoring with uptime, start time, version (`apps/dashboard/src/pages/api/health.ts`)
- `/api/health` documented in both dashboard and main READMEs
- Regression test suite for `_detect_failures` (`tests/test_scoring.py`, 46 tests)
- Substring-protection tests for prompt generator (`tests/test_prompt_generator.py`, +20 tests)
- `_whole_word_pattern()` helper in `prompt_generator.py` — consolidates `\b` / `(?<!\w)(?!\w)` boundary logic

### Changed
- Restructured codebase to monorepo (`apps/` + `packages/`)
- Renamed `benchmark/` → `packages/core/`, `benchmarks/` → `packages/benchmarks/`
- Moved `integrations/` + `adapters/` → `packages/providers/`
- Moved `dashboard/` → `apps/dashboard/`
- Moved `APICallMetrics` from `core/benchmark.py` to `providers/base.py`
- Reorganized documentation: split README into README + VISION + ARCHITECTURE + CONTRIBUTING + CHANGELOG
- Dashboard `output: "static"` → `"server"` with `@astrojs/node` standalone adapter
- `astro.config.mjs` — added adapter config, removed stale Vite SSR comment
- `package.json` scripts — `deploy` runs Node server, `cf-build` kept for static fallback

### Removed
- `bench_apple_silicon.py` (v1, superseded by v2)
- `x_thread_generator.py` (unused)
- `dashboard-cleanup-spec.md` (completed)
- Old `results/` subdirectories (stale data)

### Fixed
- Stale closure bug in `BenchmarkStatusBadge.tsx` (model always null in `[]`-dep effect)
- Cross-package dependency: Ollama no longer imports from `core`
- Ollama `health_check` now falls back to `/api/tags` for older versions
- Substring false positives in `scoring.py._detect_failures` — all 5 detection checks now use `\b` word-boundary matching:
  - Hallucinated API check: `"useState" in code` → `\buseState\b` (was matching inside `useStateful`)
  - Stale closure check: `"useEffect" in code` → `\buseEffect\b` (was matching inside `useEffectful`)
  - Async/await check: `"async" in code` → `\basync\b` (was matching inside `asynchronous`)
  - DI constructor check: `"constructor" in code` → `\bconstructor\b` (was matching inside `ConstructorProvider`)
  - No-markdown underscore check: `"_" in response` → `(?<!\w)_\w+_(?!\w)` (was matching snake_case like `my_variable`)
- Substring false positives in `swe_bench.py._evaluate_response_quality` — all 8 keyword checks (`file`, `fix`, `change`, `test`, etc.) now use `\b` boundaries with plural handling
- Substring false positive in `if_eval.py` — `'dog' in x.lower()` → `\bdogs?\b` (was matching inside `dogmatic`)
- Hook-chain corruption bug in `prompt_generator.py.mutate_context()` — `.replace()` → `re.sub()` with whole-word matching prevents `"@typedef"` corruption
- Framework name corruption in `mutate_context()` Step 2 — `.replace(name, swap)` → `re.sub(\bname\b, swap)` prevents `"Nesting"` → `"Express.jsing"`

## 0.1.0

Initial release — LM Studio benchmark harness with:
- 11 general benchmarks (MMLU-Pro, GSM8K, HumanEval, etc.)
- DevBench v2 (TypeScript/NestJS/React with statistical rigor)
- Astro + React dashboard
- Prompt packs (React, NestJS, debugging, agentic)
- LM Studio provider adapter
- GitHub Pages deployment (GitHub Actions) → removed in favor of Cloudflare Pages
