# LM Studio DevBench v1

**A rigorous, execution-grounded benchmark for local small AI models on Apple Silicon**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Apple Silicon](https://img.shields.io/badge/platform-Apple%20Silicon-lightgrey.svg)](https://www.apple.com/macos/)

---

## 🎯 What This Is

**LM Studio DevBench** is a public benchmark framework specifically designed for evaluating local small AI models (7B-9B) on Apple Silicon hardware. Unlike academic benchmarks that test "model knowledge," DevBench evaluates **"model usability in real development workflows"** for TypeScript/NestJS/React developers.

### Key Differentiator

We measure **quality-per-token/sec**, not just raw quality. This answers the question your audience actually cares about:

> "Which model gives the best answers while still feeling instant on an 18GB MacBook?"

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/kevinjobin1/lm-studio-benchmark-harness.git
cd lm-studio-benchmark-harness

# Install dependencies
pip install -r requirements.txt

# Optional: Install scipy for confidence intervals
pip install scipy
```

### Configuration

Edit `config.json` to customize your benchmark:

```json
{
  "models": {
    "auto_detect": true,
    "specific_models": []
  },
  "endpoint": {
    "base_url": "http://localhost:1234/v1"
  },
  "evaluation": {
    "runs_per_prompt": 5,
    "parallel_execution": true
  }
}
```

### Running Benchmarks

```bash
# Auto-detect and benchmark all LM Studio models
python bench_apple_silicon_v2.py

# Benchmark specific models
python bench_apple_silicon_v2.py --models "Qwen2.5-7B" "Gemma-2-9B"

# Custom configuration
python bench_apple_silicon_v2.py \
  --config custom_config.json \
  --num-runs 5 \
  --num-prompts 20
```

### Generate X Thread

```bash
python x_thread_generator.py
```

---

## 📊 What Makes This Different

### Statistical Rigor

- **5 runs per prompt** with variance reported (mean ± std, 95% CI)
- Outlier detection (IQR and z-score methods)
- Confidence intervals using t-distribution

### Execution-Grounded Scoring

- **ts-node**: Actually execute TypeScript code
- **tsc**: Check type safety with strict mode
- **eslint**: Lint for best practices

This separates "real benchmarks" from "Twitter benchmarks."

### Separated Metrics

We don't mix everything into one score:

- **Correctness**: Actual answer accuracy
- **Instruction Compliance**: Following formatting constraints
- **Reasoning Quality**: Quality of explanation
- **Code Executability**: Whether code runs
- **Type Safety**: TypeScript correctness

### Tokenization-Aware Metrics

Normalized tokens/sec accounts for verbosity bias:

```
Normalized TPS = TPS × log10(100) / log10(output_length)
```

### Failure Taxonomy

Detailed classification of error patterns:
- Hallucinated APIs
- Wrong async usage
- Incorrect JSON schema
- Stale closures
- Race conditions
- Type errors

### Real-World Debugging

Not generic coding problems - actual bugs you'd encounter:
- Async race conditions in cache layers
- NestJS dependency injection failures
- React stale closure bugs
- Prisma relation mismatches

---

## 📋 Benchmark Categories

| Category | Weight | Focus |
|----------|--------|-------|
| Code | 40% | NestJS, React Query, Prisma, TypeScript patterns |
| Frontend | 20% | React, Three.js, Tailwind, Framer Motion |
| Reasoning | 15% | Architecture planning, system design |
| Math | 15% | Developer-focused math problems |
| Instruction Following | 5% | JSON output, formatting constraints |
| Debugging | 5% | Race conditions, DI bugs, stale closures |

---

## 🏗️ Architecture

```
lm-studio-benchmark-harness/
├── config.json              # Canonical configuration
├── config_schema.json       # JSON schema validation
├── config_manager.py        # Configuration management
├── run_manifest.py          # Reproducibility manifests
├── scoring.py               # Comprehensive evaluation system
├── evaluators.py            # Pluggable evaluator interfaces
├── prompt_generator.py      # Parameterized prompt generation
├── apple_silicon_monitor.py # Hardware monitoring
├── bench_apple_silicon_v2.py # Main benchmark runner
├── x_thread_generator.py    # X thread generation
├── leaderboard.html         # Public leaderboard
└── requirements.txt         # Python dependencies
```

---

## 📊 Output

Running the benchmark generates:

### `devbench_results/`
- `results.md` - X-ready markdown report
- `results.json` - Machine-readable data
- `results.csv` - Raw data for analysis
- `radar_chart.png` - Visual comparison
- `run_manifest.json` - Reproducibility manifest
- `x_thread.txt` - Auto-generated X thread

### Leaderboard

Open `leaderboard.html` to view the public leaderboard with:
- Model rankings
- Performance metrics
- Model metadata (quantization, size)
- Auto-refresh every 5 minutes

---

## 🔬 Methodology

### Reproducibility

Every run generates a `run_manifest.json` with:
- Git SHA and branch
- Configuration version
- Prompt version
- Hardware specs
- Checksum for verification

This makes results **credible on X** and comparable across users.

### Statistical Significance

- 5 runs per prompt (configurable)
- 95% confidence intervals
- Coefficient of variation for reliability
- Outlier detection and removal

### Hardware Tracking

For Apple Silicon:
- Memory pressure detection
- Swap usage monitoring
- Thermal state tracking
- Speed decay detection

---

## 🎓 Example Real-World Debugging Prompts

### Race Condition
```typescript
// Cache layer with race condition
class CacheService {
  private cache = new Map<string, any>();
  
  async get(key: string): Promise<any> {
    if (this.cache.has(key)) {
      return this.cache.get(key);
    }
    const value = await this.fetchFromDB(key);
    this.cache.set(key, value);
    return value;
  }
}
```

**Issue**: Race condition when multiple concurrent requests for same key

### Stale Closure
```typescript
function Counter() {
  const [count, setCount] = useState(0);
  
  useEffect(() => {
    const interval = setInterval(() => {
      console.log(count); // Always logs 0
    }, 1000);
    return () => clearInterval(interval);
  }, []);
}
```

**Issue**: Stale closure - count never updates in interval

---

## 🏆 Awards

The leaderboard includes:

- **Best Coder**: Highest code category score
- **Best Debugger**: Highest debugging category score
- **Fastest**: Highest normalized tokens/sec
- **Best Developer Experience**: Highest developer realism score
- **Overall Winner**: Best developer realism score

---

## 🔧 Configuration

### Canonical Config Schema

All benchmarks use `config.json` as the single source of truth:

```json
{
  "version": "2.0.0",
  "models": {
    "auto_detect": true
  },
  "endpoint": {
    "base_url": "http://localhost:1234/v1"
  },
  "generation": {
    "temperature": 0.2,
    "max_tokens": 1000
  },
  "evaluation": {
    "runs_per_prompt": 5,
    "parallel_execution": true
  }
}
```

### Environment Variables

```bash
export LM_STUDIO_API_BASE="http://localhost:1234/v1"
export LM_STUDIO_API_KEY="lm-studio"
```

---

## 🤝 Contributing

We welcome contributions! Areas where you can help:

### Add Debugging Scenarios

Add real-world debugging scenarios to `prompt_generator.py`:

```python
SCENARIOS = {
    "new_bug_type": [
        {
            "code": "...",
            "issue": "...",
            "expected_fix": ["keyword1", "keyword2"]
        }
    ]
}
```

### Add Evaluators

Implement new evaluators in `evaluators.py`:

```python
class CustomEvaluator(Evaluator):
    def evaluate(self, prompt, response, **kwargs):
        # Your evaluation logic
        pass
```

### Add Prompt Categories

Extend the prompt generator with new categories and patterns.

---

## 📈 Comparison to Other Benchmarks

| System | Similarity | Key Difference |
|--------|------------|----------------|
| lm-eval-harness | Low | Too academic-heavy |
| OpenCompass | Medium | Not developer-focused |
| OpenBench | Medium-High | Generic tasks |
| LocalArena | HIGH | Closest, but less rigorous |
| **DevBench** | - | **Developer-focused + statistical rigor** |

---

## 🎯 Hardware Target

Optimized for:
- MacBook Pro M3
- 18GB unified memory
- 7B-9B models
- Q4_K_M quantizations
- Fast A/B comparisons

---

## 🚧 Roadmap

- [ ] Plugin system for community prompt packs
- [ ] Multi-backend support (Ollama, MLX)
- [ ] Regression tracking over time
- [ ] CI/CD integration
- [ ] Public leaderboard website
- [ ] Community contribution system

---

## 📄 License

MIT License - Open source for the community

---

## 🙏 Acknowledgments

Inspired by:
- OpenBench (provider-agnostic evaluation)
- LocalArena (local model benchmarking)
- The engineering community that values practical performance over academic scores

---

## 📞 Contact

For questions, issues, or to contribute results:
- Open an issue on GitHub
- Discuss in the community forum
- Share your results on X with #LMStudioDevBench

---

**Built for developers who care about practical model performance, not just academic scores.**
