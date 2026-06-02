# ModelLens Roadmap

## Vision

Become the standard observability layer for local LLMs.
See [VISION.md](VISION.md) for the full philosophy.

---

## V1 — Replace ad-hoc benchmarking

Status: **Complete**

- [x] LM Studio provider
- [x] Ollama provider
- [x] Unified `modellens` CLI (`run`, `info`, `leaderboard`, `models`)
- [x] Unified benchmark harness (MMLU-Pro, GSM8K, HumanEval, etc.)
- [x] DevBench v2 (TypeScript/NestJS/React, statistical rigor)
- [x] Benchmark dashboard (Astro + React)
- [x] Prompt packs (React, NestJS, debugging, agentic)
- [x] Prompt generation (paraphrasing, variable substitution, contextual mutation)
- [x] Hardware detection (CPU, GPU, RAM, OS, architecture)
- [x] Cloudflare Pages deployment
- [x] Community leaderboard

---

## V2 — Local model observability platform

Status: **Planned**

- [ ] Execution trace capture (prompt, response, token stream, latency, errors)
- [ ] Trace replay with playback controls (play, pause, speed, step)
- [ ] Side-by-side model comparison (token stream, latency diff, memory diff)
- [ ] Snapshot system (save/share execution state via URL)
- [ ] Workload evaluation (real projects: React, NestJS, Rust, Python)

---

## V3 — Local AI observability platform

Status: **Future**

- [ ] Regression detection between model versions
- [ ] Skill system (extensible benchmark logic)
- [ ] WASM sandbox for skills
- [ ] MCP server integration
- [ ] Provider expansion (Open WebUI, Jan, llama.cpp, vLLM)

---

## Supported Providers

| Phase | Providers |
|-------|-----------|
| **Phase 1** ✅ | LM Studio, Ollama |
| **Phase 2** | Open WebUI, Jan, llama.cpp, vLLM |
| **Phase 3** | LocalAI, KoboldCPP, Text Generation WebUI |

---

## Success Criteria

### V1
- Benchmark LM Studio models ✅
- Benchmark Ollama models ✅
- Publish Cloudflare Pages report ✅
- Prompt packs ✅
- Leaderboard ✅

### V2
- Trace capture
- Replay
- Side-by-side comparison
- Snapshots

### V3
- Skills
- WASM sandbox
- MCP server
- Workload evaluation
- Regression detection
