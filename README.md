# 🧪 LM Studio Benchmark Harness

[![CI](https://github.com/kevinjobin1/lm-studio-benchmark-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/kevinjobin1/lm-studio-benchmark-harness/actions/workflows/ci.yml)
[![Deploy Dashboard](https://github.com/kevinjobin1/lm-studio-benchmark-harness/actions/workflows/publish.yml/badge.svg)](https://github.com/kevinjobin1/lm-studio-benchmark-harness/actions/workflows/publish.yml)

> A local-first benchmark framework for evaluating LLMs running in LM Studio on Apple Silicon.

Measure what actually matters:
- coding ability (TypeScript / NestJS / React)
- reasoning under constraints
- instruction following
- latency + tokens/sec on real hardware

---

## ⚡ Why this exists

Most LLM benchmarks:
- don't reflect real developer workflows
- ignore latency and UX
- are not reproducible locally
- are not optimized for Apple Silicon

This project fixes that.

It benchmarks models the way developers actually use them:
> building APIs, fixing bugs, and writing production TypeScript.

---

## 🧠 Supported Models

Works with any LM Studio OpenAI-compatible model:
- Qwen / Qwopus coder variants
- Gemma 4 series
- BitCPM / MiniCPM
- LFM MoE models
- Any GGUF / MLX-compatible model exposed via LM Studio

---

## 📊 What gets measured

Each model is evaluated on:

### 🧑‍💻 Coding ability
- NestJS backend tasks
- React / Next.js behavior fixes
- TypeScript correctness
- debugging real-world bugs

### 🧠 Reasoning
- system design tradeoffs
- API architecture decisions
- concurrency reasoning

### 📐 Instruction following
- JSON-only outputs
- strict formatting constraints
- schema compliance

### ⚡ Performance (Apple Silicon optimized)
- tokens/sec
- TTFT (time-to-first-token)
- latency distribution
- run variance

---

## 🚀 Quick Start

### 1. Start LM Studio server
Enable OpenAI-compatible API at `http://localhost:1234/v1`

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run benchmark

```bash
# General benchmark suite (all 11 benchmarks)
python benchmark.py --api-base http://localhost:1234/v1 --model-name your-model

# Apple Silicon DevBench (TypeScript/NestJS/React focused)
python bench_apple_silicon_v2.py

# Quick mode (fewer samples, faster results)
python benchmark.py --api-base http://localhost:1234/v1 --model-name your-model --quick
```

---

## ⚙️ Configuration

```json
{
  "models": ["qwen3.5-9b-coder", "gemma-4-e4b", "lfm2.5-8b-a1b"],
  "temperature": 0.2,
  "runs_per_prompt": 5,
  "prompt_sets": ["coding", "reasoning", "instructions"]
}
```

Edit `config.json` (DevBench) or `config.yaml` (general suite) to customize:
- API endpoint
- Model parameters
- Benchmark categories
- Output formats

---

## 📈 Output

### CLI summary

```
Model           Score   Speed      Stability
--------------------------------------------
Qwen3.5         0.84    72 tok/s   0.91
Gemma 4         0.81    65 tok/s   0.94
LFM2.5 MoE      0.83    58 tok/s   0.97
```

### Generated artifacts
- `results.json` — machine-readable results
- `run_manifest.json` — reproducibility manifest
- `report.md` — markdown report
- `charts/` — radar charts, comparison visualizations

---

## 🔬 Example benchmark tasks

### NestJS backend
> Implement JWT auth guard with refresh token rotation.

### React
> Fix stale closure bug in useEffect.

### Debugging
> Identify race condition in async cache layer.

---

## 🧪 Evaluation method

We use a hybrid scoring system:
- **deterministic validation** (JSON, schema, tests)
- **code correctness checks** (ts-node execution, tsc type checking)
- **multi-run statistical averaging** (mean ± std, 95% confidence intervals)
- **failure taxonomy** (hallucinated APIs, async errors, type errors, stale closures)

---

## 🧠 Philosophy

This benchmark is designed around one principle:

> "How useful is this model to a real developer on a MacBook?"

Not:
- academic benchmarks
- synthetic reasoning puzzles
- memorization-based tests

---

## 🎨 Design System

All dashboard UI follows the **Kinetic Logic** design system — a precision developer-grade visual language optimized for high-density data, tonal layering, and monospace data cells. See **[docs/DESIGN.md](docs/DESIGN.md)** for the complete specification (color palette, typography, spacing, elevation, component patterns).

---

## 🧩 Roadmap

- [ ] Prompt pack system (community-extensible benchmarks)
- [ ] MLX backend support
- [ ] Ollama integration
- [ ] Web dashboard (model comparison, radar charts, failure heatmaps)
- [ ] Community leaderboard
- [x] CI regression tracking (GitHub Actions)

---

## 🤝 Contributing

We welcome:
- new prompt packs (React, backend, DevOps)
- evaluation improvements
- model adapters (Ollama / MLX / vLLM)

---

## ⭐ Why it matters

If you're running local LLMs on Apple Silicon, this gives you:
- real performance comparisons
- real coding ability ranking
- real UX latency data

Not abstract benchmark scores.

---

## 📜 License

MIT

---

**Built for developers who care about practical model performance, not just academic scores.**
