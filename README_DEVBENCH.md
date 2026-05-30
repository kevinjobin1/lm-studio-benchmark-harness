# LM Studio DevBench v2

**Public benchmark for local small AI models on Apple Silicon**

A rigorous, execution-grounded benchmark suite focused on TypeScript/NestJS/React development workflows. Built for developers who care about **quality-per-token/sec** rather than just raw quality.

## 🎯 What Makes This Different

Most benchmarks evaluate "model knowledge" on academic tasks. DevBench evaluates "model usability in real dev workflows" with:

- **Statistical rigor**: 5 runs per prompt, variance reported
- **Execution-grounded scoring**: TypeScript execution with ts-node, tsc, eslint
- **Separated metrics**: Correctness, instruction compliance, reasoning quality, code executability, type safety
- **Tokenization-aware**: Normalized tokens/sec accounting for verbosity bias
- **Real-world debugging**: Race conditions, DI bugs, stale closures, Prisma relation issues
- **Developer realism score**: Weighted formula for practical utility

## 📊 Key Metric: Quality-Per-Token/Sec

```
QPS = Quality Score × Tokens Per Second
```

This answers the question your audience cares about:

> "Which model gives the best answers while still feeling instant on an 18GB MacBook?"

## 🏗️ Architecture

```
scoring.py              # Comprehensive evaluation system
  ├─ Statistical variance (mean ± std)
  ├─ Separated scoring components
  ├─ Execution-grounded scoring (ts-node, tsc, eslint)
  ├─ Tokenization-aware metrics
  ├─ Failure taxonomy
  └─ Developer realism score

prompt_generator.py     # Auto-generated diverse prompts
  ├─ Real-world debugging scenarios
  ├─ TypeScript/NestJS/React patterns
  ├─ Architecture reasoning
  ├─ Developer-focused math
  └─ Instruction following constraints

bench_apple_silicon_v2.py  # Main benchmark runner
  ├─ Auto-detect LM Studio models
  ├─ Parallel execution
  ├─ Statistical variance tracking
  └─ Comprehensive reporting
```

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Auto-detect and benchmark all LM Studio models
python bench_apple_silicon_v2.py

# Benchmark specific models
python bench_apple_silicon_v2.py --models "Qwopus3.5-9B-Coder" "Gemma-4-E4B"

# Custom configuration
python bench_apple_silicon_v2.py \
  --num-runs 5 \
  --num-prompts 20 \
  --parallel \
  --output-dir my_results
```

## 📋 Benchmark Categories

| Category | Weight | Focus |
|----------|--------|-------|
| Code | 40% | NestJS, React Query, Prisma, TypeScript patterns |
| Frontend | 20% | React, Three.js, Tailwind, Framer Motion |
| Reasoning | 15% | Architecture planning, system design |
| Math | 15% | Developer-focused math problems |
| Instruction Following | 5% | JSON output, formatting constraints |
| Debugging | 5% | Race conditions, DI bugs, stale closures |

## 🔬 Statistical Rigor

**Multiple-Run Variance**: Each prompt runs 5 times with temperature=0.2

```
Score: 0.82 ± 0.06 (n=5)
```

This is **VERY important for X credibility** - local models have high stochastic variance even at low temperatures.

## 📏 Scoring Components

### Separated Metrics

- **Correctness**: Actual correctness of the answer
- **Instruction Compliance**: Following formatting constraints
- **Reasoning Quality**: Quality of reasoning/explanation
- **Code Executability**: Whether code actually runs (ts-node)
- **Type Safety**: TypeScript type correctness (tsc)

### Developer Realism Score

```
DeveloperScore = 
  correctness × 0.4 +
  debugging ability × 0.3 +
  instruction following × 0.2 +
  latency score × 0.1
```

## 🐛 Failure Taxonomy

Detailed classification of error patterns:

- `hallucinated_api` - Using non-existent APIs
- `wrong_async_usage` - Missing await/async
- `incorrect_json_schema` - JSON structure mismatch
- `oververbose_output` - Excessively verbose responses
- `missed_constraint` - Not following formatting rules
- `syntax_error` - Code syntax issues
- `logic_error` - Logical bugs
- `type_error` - TypeScript type errors
- `missing_import` - Forgetting imports
- `incorrect_di` - Dependency injection issues
- `stale_closure` - React stale closure bugs
- `race_condition` - Async race conditions

## 📊 Output

Generates in `devbench_results/`:

1. **results.md** - X-ready markdown with:
   - Leaderboard table with all metrics
   - Awards (Best Coder, Best Debugger, Fastest, Best Dev Experience)
   - Failure analysis
   - Methodology explanation

2. **results.csv** - Raw data for further analysis

3. **radar_chart.png** - Visual comparison of model capabilities

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

## 🔧 Execution-Grounded Scoring

For TypeScript/NestJS tasks:

- **ts-node**: Actually execute the code
- **tsc**: Check type safety with strict mode
- **eslint**: Lint for best practices

This separates "real benchmarks" from "Twitter benchmarks".

## 📈 Tokenization-Aware Metrics

**Normalized Tokens/Sec**: Accounts for verbosity bias

```
Longer outputs naturally have lower tokens/sec due to context growth
Normalized TPS = TPS × log10(100) / log10(output_length)
```

This prevents verbose models from being unfairly penalized.

## 🏆 Awards

The leaderboard includes:

- **Best Coder**: Highest code category score
- **Best Debugger**: Highest debugging category score
- **Fastest**: Highest normalized tokens/sec
- **Best Developer Experience**: Highest developer realism score
- **Overall Winner**: Best developer realism score

## 🎯 For Your X Thread

The markdown report is formatted specifically for X/Twitter with:

- Clear leaderboard table
- Award highlights
- Failure analysis insights
- Methodology context
- The key question answered

Post the markdown with the radar chart for maximum impact.

## 🔬 Hardware Target

Optimized for:
- MacBook Pro M3
- 18GB unified memory
- 7B-9B models
- Q4_K_M quantizations
- Fast A/B comparisons

## 🆚 Comparison to Other Benchmarks

| System | Similarity | Key Difference |
|--------|------------|----------------|
| lm-eval-harness | Low | Too academic-heavy |
| OpenCompass | Medium | Not developer-focused |
| OpenBench | Medium-High | Generic tasks |
| LocalArena | HIGH | Closest, but less rigorous |
| **DevBench** | - | **Developer-focused + statistical rigor** |

## 🚧 Roadmap

- [ ] X thread generator (auto-write your post)
- [ ] Regression tracking over time
- [ ] Public leaderboard website
- [ ] Model metadata tracking (quantization, size)
- [ ] Community prompt contributions
- [ ] CI/CD integration

## 📝 Contributing

This is designed as a public benchmark project. To contribute:

1. Add debugging scenarios to `prompt_generator.py`
2. Improve scoring logic in `scoring.py`
3. Add new categories or patterns
4. Submit results for your models

## 📄 License

MIT License - Open source for the community

## 🙏 Acknowledgments

Inspired by:
- OpenBench (provider-agnostic evaluation)
- LocalArena (local model benchmarking)
- The engineering review that highlighted statistical rigor gaps

## 📞 Contact

For questions, issues, or to contribute results, open an issue on GitHub.

---

**Built for developers who care about practical model performance, not just academic scores.**
