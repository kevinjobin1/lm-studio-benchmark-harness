# Apple Silicon LLM Benchmark for LM Studio

A specialized benchmark suite for TypeScript/NestJS/React developers on Apple Silicon, focused on **quality-per-token/sec** rather than absolute quality.

## Why This Exists

Your audience on X cares more about:
> "Which model gives the best answers while still feeling instant on an 18GB MacBook?"

than about GPQA scores.

## Features

- **Auto-detects** LM Studio models
- **TypeScript/NestJS/React focused** prompts (not generic coding tasks)
- **Quality-per-token/sec** metric (quality × speed)
- **TTFT** (Time to First Token) tracking
- **RAM usage** monitoring
- **X-ready** markdown reports with radar charts

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Auto-detect and benchmark all LM Studio models
python bench_apple_silicon.py

# Benchmark specific models
python bench_apple_silicon.py --models "Qwopus3.5-9B-Coder" "Gemma-4-E4B" "LFM2.5-8B-A1B"

# Quick mode (5 prompts for testing)
python bench_apple_silicon.py --quick

# Custom API endpoint
python bench_apple_silicon.py --api-base http://localhost:1234/v1
```

## Benchmark Categories

| Category | Weight | Focus |
|----------|--------|-------|
| Code | 40% | NestJS, React Query, Prisma, TypeScript |
| Frontend | 20% | React, Three.js, Tailwind, Framer Motion |
| Reasoning | 15% | Architecture planning, system design |
| Math | 15% | Practical developer math problems |
| Instruction Following | 10% | JSON output, formatting constraints |

## Sample Prompts

**Code:**
- "Implement a NestJS AuthGuard that validates JWT tokens and checks if the user has the 'admin' role."
- "Create a React Query hook for fetching user data with caching and retry logic."
- "Write a Prisma migration to add a 'posts' table with UUID primary key."

**Frontend:**
- "Build an Awwwards-style hero section with parallax effect using Framer Motion."
- "Create a Three.js scene with rotating icosahedron and mouse interaction."
- "Generate a modern landing page using Tailwind CSS with gradient backgrounds."

**Reasoning:**
- "Plan the architecture for a real-time collaborative document editor with conflict resolution."
- "Design a microservices architecture for an e-commerce platform with API contracts."

## Output

Generates three files in `apple_silicon_results/`:

1. **results.md** - X-ready markdown report with:
   - Summary table with all metrics
   - Awards (Best Coder, Fastest, Best Value, Overall Winner)
   - Methodology explanation

2. **results.csv** - Raw data for further analysis

3. **radar_chart.png** - Visual comparison of model capabilities

## Metrics Explained

- **Quality Score**: 0-1 based on expected keywords/answers
- **Tokens/sec**: Generation speed
- **TTFT**: Time to first token (latency)
- **QPS (Quality-per-token/sec)**: Quality × Speed - the key metric!

## Example Output

```
| Model | Code | Frontend | Reasoning | Math | IF | tok/s | TTFT | QPS |
|-------|------|----------|-----------|------|----|-------|------|-----|
| Qwopus3.5-9B-Coder | 0.85 | 0.72 | 0.68 | 0.75 | 0.90 | 45.2 | 0.3s | 38.4 |
| Gemma-4-E4B | 0.78 | 0.80 | 0.72 | 0.70 | 0.95 | 52.1 | 0.2s | 49.5 |
| LFM2.5-8B-A1B | 0.82 | 0.75 | 0.85 | 0.78 | 0.88 | 38.7 | 0.4s | 33.1 |

🏆 Awards:
- Best Coder: Qwopus3.5-9B-Coder (85%)
- Fastest: Gemma-4-E4B (52.1 tok/s)
- Best Value: Gemma-4-E4B (49.5 QPS)
- Overall Winner: Gemma-4-E4B
```

## For Your X Thread

The markdown report is formatted specifically for X/Twitter with:
- Clear summary table
- Award highlights
- Methodology context
- The key question answered: "Which model gives the best answers while still feeling instant on an 18GB MacBook?"

Post the markdown with the radar chart image for maximum impact.

## Hardware Target

Optimized for:
- MacBook Pro M3
- 18GB unified memory
- 7B-9B models
- Q4_K_M quantizations
- Fast A/B comparisons

## Alternative Tools

If you want system-level benchmarking (power draw, thermal state):
- **asiai**: `brew install asiai` (Apple Silicon native)
- **apple-silicon-llm-bench**: GitHub repo for systematic backend benchmarking

This script complements those by focusing on **your actual workflow** (TypeScript/NestJS/React) rather than generic tasks.
