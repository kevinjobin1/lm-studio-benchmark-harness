# LM Studio Benchmark Harness

A single-command comprehensive benchmark suite for evaluating LM Studio's OpenAI-compatible API across dimensions that matter on X/Twitter.

## Features

- **Multiple Frameworks**: Custom benchmarks, LM Eval (EleutherAI), OpenBench (Groq)
- **Comparison Mode**: Side-by-side comparison of all frameworks
- **General Reasoning**: MMLU-Pro subset
- **Math**: GSM8K + AIME subset
- **Coding**: HumanEval
- **Coding Agent**: SWE-bench Lite subset
- **Instruction Following**: IFEval
- **Long Context**: Needle-in-Haystack
- **Tool Use**: BFCL subset
- **Speed**: Tokens/sec
- **Latency**: TTFT (Time to First Token)
- **Memory**: RAM/VRAM usage
- **Creativity**: Arena-style subjective prompts

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: Install OpenBench (for OpenBench framework)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv
source .venv/bin/activate
uv pip install openbench
```

## Usage

### Custom Framework (Default)
```bash
# Run all benchmarks
python benchmark.py --api-base http://localhost:1234/v1 --model-name your-model

# Run specific benchmarks
python benchmark.py --api-base http://localhost:1234/v1 --model-name your-model --benchmarks mmlu-pro humaneval

# Quick mode (fewer samples)
python benchmark.py --api-base http://localhost:1234/v1 --model-name your-model --quick

# Custom sample count
python benchmark.py --api-base http://localhost:1234/v1 --model-name your-model --samples 50
```

### LM Eval Framework
```bash
# Run industry-standard LM Eval benchmarks
python benchmark.py --framework lm-eval --api-base http://localhost:1234/v1 --model-name your-model

# Run specific LM Eval tasks
python benchmark.py --framework lm-eval --api-base http://localhost:1234/v1 --model-name your-model --benchmarks mmlu-pro gsm8k
```

### OpenBench Framework
```bash
# Run OpenBench benchmarks (requires OpenBench installation)
python benchmark.py --framework openbench --api-base http://localhost:1234/v1 --model-name your-model

# Auto-install OpenBench if missing
python benchmark.py --framework openbench --api-base http://localhost:1234/v1 --model-name your-model --install-openbench
```

### Comparison Mode
```bash
# Run all three frameworks and compare side-by-side
python benchmark.py --framework compare --api-base http://localhost:1234/v1 --model-name your-model

# Compare specific benchmarks
python benchmark.py --framework compare --api-base http://localhost:1234/v1 --model-name your-model --benchmarks mmlu-pro humaneval
```

## Configuration

Edit `config.yaml` to customize:
- API endpoint
- Model parameters
- Benchmark settings
- Output formats

## Output

Results are saved to `results/timestamp/`:
- `summary.json` - Structured results (custom framework)
- `report.html` - Visual report (custom framework)
- `metrics.csv` - Raw metrics (custom framework)
- `lm_eval_results.json` - LM Eval results
- `openbench_results.json` - OpenBench results
- `comparison_results.json` - Comparison mode results
- `comparison_report.html` - Side-by-side comparison report

## Framework Comparison

| Feature | Custom | LM Eval | OpenBench |
|---------|--------|---------|-----------|
| Standardized datasets | ❌ Sample data | ✅ Full datasets | ✅ Full datasets |
| Industry recognition | ❌ Custom | ✅ HF Leaderboard | ✅ Growing adoption |
| Benchmark count | 11 custom | 50+ standard | 95+ standard |
| Performance metrics | ✅ TTFT, tokens/sec | ❌ | ❌ |
| Memory monitoring | ✅ RAM/VRAM | ❌ | ❌ |
| Creativity eval | ✅ Arena-style | ❌ | ❌ |
| API support | LM Studio | Multiple providers | 30+ providers |
| Comparison mode | ✅ | ✅ | ✅ |

## Recommendations

- **Use LM Eval** for standardized, comparable results against the HF Open LLM Leaderboard
- **Use OpenBench** for maximum benchmark coverage and provider flexibility
- **Use Custom** for performance metrics (speed, latency, memory) and creativity evaluation
- **Use Comparison Mode** to validate results across frameworks
