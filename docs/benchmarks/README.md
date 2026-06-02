# Benchmark Methodology

Model Lens evaluates local AI models across 11 standard benchmarks, plus DevBench — a developer-realistic evaluation harness for TypeScript, NestJS, and React.

---

## Scoring system

### Score components

Each benchmark response is evaluated on five weighted components:

| Component | Weight | Description |
|-----------|--------|-------------|
| **Correctness** | 40% | Is the answer actually right? |
| **Instruction compliance** | 20% | Does it follow formatting constraints? |
| **Reasoning quality** | 20% | Is the reasoning structured and thoughtful? |
| **Code executability** | 15% | Does generated code actually run? |
| **Type safety** | 5% | Does TypeScript code pass `tsc --noEmit`? |

### Statistical rigor

Every prompt is run **5 times** to capture variance. Results include:

- **Mean ± std** — Average score with standard deviation
- **95% confidence intervals** — Using Student's t-distribution (scipy) or normal approximation (fallback)
- **Outlier detection** — IQR and z-score methods
- **Reliability threshold** — Coefficient of variation < 0.1 for "reliable" scores

### Failure taxonomy

Failures are classified using a 13-type taxonomy (see `scoring.py`):

| Failure type | Example |
|-------------|---------|
| `hallucinated_api` | Made-up library functions |
| `wrong_async_usage` | `async` without `await` |
| `incorrect_json_schema` | JSON doesn't match expected shape |
| `syntax_error` | Code that won't parse |
| `type_error` | TypeScript type mismatch |
| `stale_closure` | `useEffect` with `[]` capturing stale values |
| `race_condition` | Missing `Promise.all` in parallel async ops |
| `missing_import` | Unimported symbol |
| `incorrect_di` | NestJS `@Injectable()` without constructor |
| `oververbose_output` | Response too long |
| `missed_constraint` | Failed formatting requirement |
| `logic_error` | Code runs but produces wrong result |
| `other` | Unclassified |

---

## Benchmark categories

### Knowledge & reasoning

| Benchmark | Description | Metric |
|-----------|-------------|--------|
| **MMLU-Pro** | 12,000+ multiple-choice across 57 subjects | Accuracy (%) |
| **GSM8K** | Grade-school math word problems | Numerical match (±tolerance) |
| **AIME** | Competition-level mathematics | Numerical match (±tolerance) |
| **IFEval** | Instruction-following constraints | Constraint adherence (%) |

### Code generation

| Benchmark | Description | Metric |
|-----------|-------------|--------|
| **HumanEval** | 164 Python programming problems | Pass@k |
| **SWE-bench Lite** | Real GitHub issues (simplified) | Patch correctness |
| **BFCL** | Function-calling accuracy | Tool choice accuracy |
| **Coding** | TypeScript/NestJS/React code tasks | Multi-component score |

### Performance

| Benchmark | Description | Metric |
|-----------|-------------|--------|
| **Speed/Latency** | Tokens/sec, TTFT, throughput | ms, tokens/sec |
| **Memory** | RAM/VRAM usage during inference | MB (mean/peak) |
| **Needle-in-Haystack** | Long-context retrieval | Accuracy vs. position |

### Quality

| Benchmark | Description | Metric |
|-----------|-------------|--------|
| **Creativity** | Open-ended generation quality | Multi-dimensional score |

---

## DevBench v2

A separate evaluation harness focused on **real developer workloads**:

- **TypeScript execution** — Code is compiled with `tsc --noEmit` and executed with `ts-node`
- **ESLint validation** — Code quality via linting rules
- **Developer realism score** — Weighted: correctness (40%) + debugging ability (30%) + instruction following (20%) + latency (10%)
- **Tokenization-aware metrics** — Normalized by output length to account for verbosity bias
- **Steady-state speed** — Ignores warmup tokens for accurate throughput measurement

### DevBench prompt categories

| Category | Focus |
|----------|-------|
| **Code** | Implementing features, fixing bugs |
| **Frontend** | React/Next.js component work |
| **Reasoning** | Architecture decisions, tradeoffs |
| **Math** | Numerical computation, data analysis |
| **Instruction** | Schema compliance, format constraints |

---

## Execution-grounded scoring

For code tasks, scoring is grounded in actual execution:

1. **Extract** code block from model response
2. **Compile** with `tsc --noEmit` (type safety check)
3. **Execute** with `ts-node` (runtime correctness)
4. **Lint** with ESLint (code quality)
5. **Detect** failure patterns (stale closures, race conditions, DI issues)

All tooling (`ts-node`, `tsc`, `eslint`) is optional — scoring degrades gracefully if unavailable.

---

## Evaluator plugins

The evaluator system is pluggable (see `evaluators.py`). Built-in evaluators:

| Evaluator | Purpose |
|-----------|---------|
| `JSONSchemaEvaluator` | Validate JSON against schema |
| `RegexConstraintEvaluator` | Check formatting patterns, forbidden patterns, counts |
| `KeywordMatchEvaluator` | Verify key concepts are present |
| `NumericalAnswerEvaluator` | Compare numerical answers with tolerance |
| `CodeExecutionEvaluator` | Execute TypeScript and verify output |
| `CompositeEvaluator` | Combine multiple evaluators with weights |

Use `EvaluatorFactory` to create evaluators by type or from config.
