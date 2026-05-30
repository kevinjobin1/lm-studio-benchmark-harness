#!/usr/bin/env python3
"""
LM Studio DevBench v2 - Public Benchmark for Local Small AI Models
Focused on TypeScript/NestJS/React with statistical rigor and execution-grounded scoring
"""

import json
import time
import psutil
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from openai import OpenAI
import matplotlib.pyplot as plt
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

from scoring import (
    ComprehensiveEvaluator,
    ScoreComponents,
    EvaluationResult,
    StatisticalScore,
    FailureType,
    DeveloperRealismScorer,
    TokenizationAwareMetrics
)
from prompt_generator import (
    PromptGenerator,
    GeneratedPrompt,
    PromptCategory
)


@dataclass
class BenchmarkResult:
    """Result from a single benchmark run with statistical rigor."""
    model: str
    category: str
    prompt: str
    responses: List[str]  # Multiple runs for variance
    evaluation: EvaluationResult
    ttft_mean: float
    ttft_std: float
    tokens_per_second_mean: float
    tokens_per_second_std: float
    normalized_tps_mean: float  # Tokenization-aware
    steady_state_speed: float
    tail_latency: float
    ram_usage_mb: float
    developer_score: float  # Developer realism score
    metadata: Dict[str, Any] = field(default_factory=dict)


class LMStudioModelDetector:
    """Auto-detect models installed in LM Studio."""
    
    def __init__(self, lm_studio_path: str = "~/Library/Application Support/LM Studio"):
        self.lm_studio_path = Path(lm_studio_path).expanduser()
    
    def detect_models(self) -> List[Dict[str, str]]:
        """Detect installed LM Studio models with metadata."""
        models = []
        
        try:
            models_dir = self.lm_studio_path / "Models"
            if models_dir.exists():
                for model_path in models_dir.iterdir():
                    if model_path.is_dir():
                        config_file = model_path / "model_config.json"
                        if config_file.exists():
                            with open(config_file) as f:
                                config = json.load(f)
                                models.append({
                                    "name": config.get("model_name", model_path.name),
                                    "path": str(model_path),
                                    "size": config.get("size", "unknown"),
                                    "quantization": config.get("quantization", "unknown"),
                                    "parameters": config.get("parameters", "unknown")
                                })
                        else:
                            models.append({
                                "name": model_path.name,
                                "path": str(model_path),
                                "size": "unknown",
                                "quantization": "unknown",
                                "parameters": "unknown"
                            })
        except Exception as e:
            print(f"Could not auto-detect models: {e}")
        
        return models


class AppleSiliconBenchmarkV2:
    """Benchmark runner v2 with statistical rigor and execution-grounded scoring."""
    
    def __init__(self, 
                 api_base: str = "http://localhost:1234/v1", 
                 api_key: str = "lm-studio",
                 num_runs: int = 5):
        self.client = OpenAI(base_url=api_base, api_key=api_key)
        self.prompt_generator = PromptGenerator()
        self.evaluator = ComprehensiveEvaluator(num_runs=num_runs)
        self.developer_scorer = DeveloperRealismScorer()
        self.token_metrics = TokenizationAwareMetrics()
        self.results: List[BenchmarkResult] = []
        self.num_runs = num_runs
    
    def run_single_completion(self, model_name: str, prompt: str) -> tuple:
        """Run a single completion and return (response, token_times, ttft, total_time)."""
        start_time = time.time()
        first_token_time = None
        response_text = ""
        token_times = []
        
        try:
            stream = self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # Slight temperature for variance testing
                max_tokens=1000,
                stream=True
            )
            
            last_token_time = start_time
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    current_time = time.time()
                    if first_token_time is None:
                        first_token_time = current_time
                    
                    token_times.append(current_time - last_token_time)
                    last_token_time = current_time
                    response_text += chunk.choices[0].delta.content
            
            total_time = time.time() - start_time
            ttft = first_token_time - start_time if first_token_time else total_time
            
            return response_text, token_times, ttft, total_time
            
        except Exception as e:
            print(f"Error in completion: {e}")
            return "", [], 0, 0
    
    def run_benchmark_with_variance(self, 
                                   model_name: str, 
                                   prompt_data: GeneratedPrompt) -> BenchmarkResult:
        """Run benchmark with multiple runs for statistical variance."""
        prompt = prompt_data.prompt
        category = prompt_data.category.value
        
        # Start memory monitoring
        process = psutil.Process()
        start_ram = process.memory_info().rss / 1024 / 1024
        
        # Run multiple times for variance
        responses = []
        ttfts = []
        total_times = []
        token_times_list = []
        
        print(f"   Running {self.num_runs} iterations for variance...")
        
        for i in range(self.num_runs):
            response, token_times, ttft, total_time = self.run_single_completion(model_name, prompt)
            responses.append(response)
            ttfts.append(ttft)
            total_times.append(total_time)
            token_times_list.append(token_times)
            print(f"     Run {i+1}/{self.num_runs}: {len(response)} chars, {ttft:.3f}s TTFT")
        
        # End memory monitoring
        end_ram = process.memory_info().rss / 1024 / 1024
        ram_usage = end_ram - start_ram
        
        # Calculate statistical metrics
        ttft_mean = statistics.mean(ttfts)
        ttft_std = statistics.stdev(ttfts) if len(ttfts) > 1 else 0.0
        
        # Calculate tokens/sec for each run
        tps_values = []
        for response, total_time in zip(responses, total_times):
            if total_time > 0:
                # Approximate token count (rough estimate: 4 chars per token)
                token_count = len(response) / 4
                tps = token_count / total_time
                tps_values.append(tps)
        
        tokens_per_second_mean = statistics.mean(tps_values) if tps_values else 0.0
        tokens_per_second_std = statistics.stdev(tps_values) if len(tps_values) > 1 else 0.0
        
        # Tokenization-aware normalization
        avg_response_length = statistics.mean([len(r) for r in responses]) if responses else 0
        normalized_tps_mean = self.token_metrics.normalize_tokens_per_second(
            tokens_per_second_mean, avg_response_length
        )
        
        # Steady-state speed and tail latency
        all_token_times = []
        for token_times in token_times_list:
            all_token_times.extend(token_times)
        
        if all_token_times:
            steady_state_speed, tail_latency = self.token_metrics.compute_steady_state_speed(all_token_times)
        else:
            steady_state_speed, tail_latency = 0.0, 0.0
        
        # Evaluate with variance
        evaluation = self.evaluator.evaluate_with_variance(
            responses,
            {
                "category": category,
                "expected_keywords": prompt_data.expected_keywords,
                "constraints": prompt_data.constraints,
                "expected_answer": prompt_data.expected_answer,
                "json_schema": prompt_data.json_schema
            },
            category
        )
        
        # Calculate developer realism score
        latency_score = 1.0 / (1.0 + ttft_mean)  # Lower TTFT = higher score
        verbosity_penalty = min(0.2, max(0.0, (avg_response_length - 500) / 2000))  # Penalize very verbose responses
        developer_score = self.developer_scorer.compute_developer_score(
            evaluation.score_components,
            latency_score,
            verbosity_penalty
        )
        
        return BenchmarkResult(
            model=model_name,
            category=category,
            prompt=prompt,
            responses=responses,
            evaluation=evaluation,
            ttft_mean=ttft_mean,
            ttft_std=ttft_std,
            tokens_per_second_mean=tokens_per_second_mean,
            tokens_per_second_std=tokens_per_second_std,
            normalized_tps_mean=normalized_tps_mean,
            steady_state_speed=steady_state_speed,
            tail_latency=tail_latency,
            ram_usage_mb=ram_usage,
            developer_score=developer_score,
            metadata={
                "difficulty": prompt_data.difficulty,
                "num_runs": self.num_runs,
                "avg_response_length": avg_response_length
            }
        )
    
    def benchmark_model(self, 
                       model_name: str, 
                       prompts: Optional[List[GeneratedPrompt]] = None,
                       parallel: bool = True) -> List[BenchmarkResult]:
        """Benchmark a single model against all prompts."""
        if prompts is None:
            prompts = self.prompt_generator.generate_default_batch(total_prompts=20)
        
        print(f"\n🚀 Benchmarking {model_name}")
        print(f"   Running {len(prompts)} benchmarks with {self.num_runs} iterations each...")
        print(f"   Total runs: {len(prompts) * self.num_runs}\n")
        
        model_results = []
        
        if parallel:
            # Parallel execution
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_prompt = {
                    executor.submit(self.run_benchmark_with_variance, model_name, prompt): prompt
                    for prompt in prompts
                }
                
                for i, future in enumerate(as_completed(future_to_prompt)):
                    prompt = future_to_prompt[future]
                    try:
                        result = future.result()
                        model_results.append(result)
                        print(f"   [{i+1}/{len(prompts)}] {result.category}: "
                              f"QPS={result.evaluation.statistical_score.mean:.2f}±{result.evaluation.statistical_score.std:.2f}, "
                              f"DevScore={result.developer_score:.2f}")
                    except Exception as e:
                        print(f"   Error on prompt {i+1}: {e}")
        else:
            # Sequential execution
            for i, prompt in enumerate(prompts):
                print(f"   [{i+1}/{len(prompts)}] {prompt.category.value}: {prompt.prompt[:50]}...")
                result = self.run_benchmark_with_variance(model_name, prompt)
                model_results.append(result)
                print(f"      QPS: {result.evaluation.statistical_score.mean:.2f}±{result.evaluation.statistical_score.std:.2f}")
                print(f"      DevScore: {result.developer_score:.2f}")
                print(f"      Failures: {[f.value for f in result.evaluation.failures]}")
        
        self.results.extend(model_results)
        return model_results


class ReportGeneratorV2:
    """Generate comprehensive reports for public leaderboard."""
    
    def __init__(self, output_dir: str = "devbench_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_markdown_report(self, results: List[BenchmarkResult]) -> str:
        """Generate comprehensive markdown report."""
        # Group results by model
        by_model: Dict[str, List[BenchmarkResult]] = {}
        for result in results:
            if result.model not in by_model:
                by_model[result.model] = []
            by_model[result.model].append(result)
        
        # Calculate aggregate metrics per model
        model_stats = {}
        for model, model_results in by_model.items():
            # Category averages
            categories = ["code", "frontend", "reasoning", "math", "instruction", "debugging"]
            category_scores = {}
            
            for cat in categories:
                cat_results = [r for r in model_results if r.category == cat]
                if cat_results:
                    avg_score = statistics.mean([r.evaluation.overall_score for r in cat_results])
                    category_scores[cat] = avg_score
                else:
                    category_scores[cat] = 0.0
            
            # Performance metrics
            avg_tps = statistics.mean([r.tokens_per_second_mean for r in model_results])
            avg_ttft = statistics.mean([r.ttft_mean for r in model_results])
            avg_dev_score = statistics.mean([r.developer_score for r in model_results])
            avg_normalized_tps = statistics.mean([r.normalized_tps_mean for r in model_results])
            
            # Failure aggregation
            all_failures = []
            for r in model_results:
                all_failures.extend(r.evaluation.failures)
            
            failure_counts = {}
            for failure in all_failures:
                failure_counts[failure.value] = failure_counts.get(failure.value, 0) + 1
            
            model_stats[model] = {
                **category_scores,
                "tokens_per_second": avg_tps,
                "normalized_tps": avg_normalized_tps,
                "ttft": avg_ttft,
                "developer_score": avg_dev_score,
                "failure_counts": failure_counts
            }
        
        # Generate markdown
        md = "# 🍎 LM Studio DevBench Results\n\n"
        md += "Public benchmark for local small AI models on Apple Silicon\n\n"
        md += "**Hardware**: MacBook Pro M3, 18GB unified memory\n"
        md += "**Focus**: TypeScript/NestJS/React development workflow\n"
        md += "**Metric**: Quality-per-token/sec with statistical rigor (n=5 runs per prompt)\n\n"
        
        # Summary table
        md += "## 📊 Leaderboard\n\n"
        md += "| Model | Code | Frontend | Reasoning | Math | IF | Debug | DevScore | tok/s | TTFT | NormTPS |\n"
        md += "|-------|------|----------|-----------|------|----|-------|----------|-------|------|--------|\n"
        
        for model, stats in sorted(model_stats.items(), key=lambda x: x[1]["developer_score"], reverse=True):
            md += f"| {model} | {stats['code']:.2%} | {stats['frontend']:.2%} | {stats['reasoning']:.2%} | {stats['math']:.2%} | {stats['instruction']:.2%} | {stats['debugging']:.2%} | {stats['developer_score']:.2f} | {stats['tokens_per_second']:.1f} | {stats['ttft']:.3f}s | {stats['normalized_tps']:.1f} |\n"
        
        # Awards
        md += "\n## 🏆 Awards\n\n"
        
        best_coder = max(model_stats.items(), key=lambda x: x[1]["code"])
        md += f"**Best Coder**: {best_coder[0]} ({best_coder[1]['code']:.2%})\n\n"
        
        best_debugger = max(model_stats.items(), key=lambda x: x[1]["debugging"])
        md += f"**Best Debugger**: {best_debugger[0]} ({best_debugger[1]['debugging']:.2%})\n\n"
        
        fastest = max(model_stats.items(), key=lambda x: x[1]["normalized_tps"])
        md += f"**Fastest**: {fastest[0]} ({fastest[1]['normalized_tps']:.1f} norm-tok/s)\n\n"
        
        best_dev = max(model_stats.items(), key=lambda x: x[1]["developer_score"])
        md += f"**Best Developer Experience**: {best_dev[0]} ({best_dev[1]['developer_score']:.2f})\n\n"
        
        overall_winner = best_dev[0]
        md += f"**🥇 Overall Winner**: {overall_winner}\n\n"
        
        # Failure analysis
        md += "## 🔍 Failure Analysis\n\n"
        md += "Common failure patterns across models:\n\n"
        
        all_failures_combined = {}
        for model, stats in model_stats.items():
            for failure, count in stats["failure_counts"].items():
                all_failures_combined[failure] = all_failures_combined.get(failure, 0) + count
        
        for failure, count in sorted(all_failures_combined.items(), key=lambda x: x[1], reverse=True):
            md += f"- **{failure}**: {count} occurrences\n"
        
        # Methodology
        md += "\n## 📋 Methodology\n\n"
        md += "- **Statistical Rigor**: 5 runs per prompt, mean ± std reported\n"
        md += "- **Execution-Grounded Scoring**: TypeScript execution with ts-node, tsc, eslint\n"
        md += "- **Separated Metrics**: Correctness, instruction compliance, reasoning quality, code executability, type safety\n"
        md += "- **Tokenization-Aware**: Normalized tokens/sec accounting for verbosity bias\n"
        md += "- **Developer Realism Score**: Weighted formula for practical utility\n"
        md += "- **Failure Taxonomy**: Detailed classification of error patterns\n"
        md += "- **Categories**: Code (40%), Frontend (20%), Reasoning (15%), Math (15%), Instruction (5%), Debugging (5%)\n\n"
        
        md += "**Key Question Answered**: Which model gives the best answers while still feeling instant on an 18GB MacBook?\n"
        
        # Save markdown
        md_file = self.output_dir / "results.md"
        with open(md_file, 'w') as f:
            f.write(md)
        
        return str(md_file)
    
    def generate_json(self, results: List[BenchmarkResult], model_metadata: Dict[str, Dict]) -> str:
        """Generate JSON for X thread generator and further analysis."""
        # Group results by model
        by_model: Dict[str, List[BenchmarkResult]] = {}
        for result in results:
            if result.model not in by_model:
                by_model[result.model] = []
            by_model[result.model].append(result)
        
        # Calculate aggregate metrics per model
        model_stats = {}
        for model, model_results in by_model.items():
            categories = ["code", "frontend", "reasoning", "math", "instruction", "debugging"]
            category_scores = {}
            
            for cat in categories:
                cat_results = [r for r in model_results if r.category == cat]
                if cat_results:
                    avg_score = statistics.mean([r.evaluation.overall_score for r in cat_results])
                    category_scores[cat] = avg_score
                else:
                    category_scores[cat] = 0.0
            
            avg_tps = statistics.mean([r.tokens_per_second_mean for r in model_results])
            avg_ttft = statistics.mean([r.ttft_mean for r in model_results])
            avg_dev_score = statistics.mean([r.developer_score for r in model_results])
            avg_normalized_tps = statistics.mean([r.normalized_tps_mean for r in model_results])
            
            # Failure aggregation
            all_failures = []
            for r in model_results:
                all_failures.extend(r.evaluation.failures)
            
            failure_counts = {}
            for failure in all_failures:
                failure_counts[failure.value] = failure_counts.get(failure.value, 0) + 1
            
            model_stats[model] = {
                **category_scores,
                "tokens_per_second": avg_tps,
                "normalized_tps": avg_normalized_tps,
                "ttft": avg_ttft,
                "developer_score": avg_dev_score,
                "failure_counts": failure_counts,
                "metadata": model_metadata.get(model, {})
            }
        
        # Find overall winner
        overall_winner = max(model_stats.items(), key=lambda x: x[1]["developer_score"])
        best_developer_score = overall_winner[1]["developer_score"]
        
        # Build JSON structure
        json_data = {
            "overall_winner": overall_winner[0],
            "best_developer_score": best_developer_score,
            "models": list(model_stats.keys()),
            "model_stats": model_stats,
            "failure_analysis": self._aggregate_failures(model_stats),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        json_file = self.output_dir / "results.json"
        with open(json_file, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        return str(json_file)
    
    def _aggregate_failures(self, model_stats: Dict) -> Dict:
        """Aggregate failures across all models."""
        all_failures = {}
        for model, stats in model_stats.items():
            for failure, count in stats["failure_counts"].items():
                all_failures[failure] = all_failures.get(failure, 0) + count
        return all_failures
    
    def generate_csv(self, results: List[BenchmarkResult]) -> str:
        """Generate CSV for data analysis."""
        import csv
        
        csv_file = self.output_dir / "results.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "model", "category", "overall_score", "score_std", "correctness",
                "instruction_compliance", "reasoning_quality", "code_executability",
                "type_safety", "developer_score", "tokens_per_second", "normalized_tps",
                "ttft", "steady_state_speed", "tail_latency", "ram_usage_mb",
                "failures", "num_runs"
            ])
            
            for result in results:
                writer.writerow([
                    result.model,
                    result.category,
                    result.evaluation.overall_score,
                    result.evaluation.statistical_score.std,
                    result.evaluation.score_components.correctness,
                    result.evaluation.score_components.instruction_compliance,
                    result.evaluation.score_components.reasoning_quality,
                    result.evaluation.score_components.code_executability,
                    result.evaluation.score_components.type_safety,
                    result.developer_score,
                    result.tokens_per_second_mean,
                    result.normalized_tps_mean,
                    result.ttft_mean,
                    result.steady_state_speed,
                    result.tail_latency,
                    result.ram_usage_mb,
                    ",".join([f.value for f in result.evaluation.failures]),
                    result.metadata.get("num_runs", 1)
                ])
        
        return str(csv_file)
    
    def generate_radar_chart(self, results: List[BenchmarkResult]) -> str:
        """Generate radar chart for model comparison."""
        # Group by model
        by_model: Dict[str, List[BenchmarkResult]] = {}
        for result in results:
            if result.model not in by_model:
                by_model[result.model] = []
            by_model[result.model].append(result)
        
        # Calculate category averages per model
        categories = ["code", "frontend", "reasoning", "math", "instruction", "debugging"]
        model_data = {}
        
        for model, model_results in by_model.items():
            scores = []
            for cat in categories:
                cat_results = [r for r in model_results if r.category == cat]
                if cat_results:
                    avg_score = statistics.mean([r.evaluation.overall_score for r in cat_results])
                    scores.append(avg_score)
                else:
                    scores.append(0)
            model_data[model] = scores
        
        # Create radar chart
        fig, ax = plt.subplots(figsize=(12, 10), subplot_kw=dict(projection='polar'))
        
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]
        
        colors = plt.cm.Set3(np.linspace(0, 1, len(model_data)))
        
        for (model, scores), color in zip(model_data.items(), colors):
            scores += scores[:1]
            ax.plot(angles, scores, 'o-', linewidth=2, label=model, color=color)
            ax.fill(angles, scores, alpha=0.15, color=color)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([c.title() for c in categories])
        ax.set_ylim(0, 1)
        ax.set_title('Model Capability Radar Chart\n(with Statistical Rigor)', size=16, pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        ax.grid(True)
        
        chart_file = self.output_dir / "radar_chart.png"
        plt.savefig(chart_file, dpi=150, bbox_inches='tight')
        plt.close()
        
        return str(chart_file)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="LM Studio DevBench v2 - Public Benchmark for Local Small AI Models")
    parser.add_argument("--api-base", default="http://localhost:1234/v1", help="LM Studio API base URL")
    parser.add_argument("--models", nargs="+", help="Specific models to benchmark (default: auto-detect)")
    parser.add_argument("--output-dir", default="devbench_results", help="Output directory")
    parser.add_argument("--num-runs", type=int, default=5, help="Number of runs per prompt for variance")
    parser.add_argument("--num-prompts", type=int, default=20, help="Total number of prompts")
    parser.add_argument("--parallel", action="store_true", default=True, help="Enable parallel execution")
    parser.add_argument("--sequential", action="store_true", help="Disable parallel execution")
    
    args = parser.parse_args()
    
    # Detect models if not specified
    model_metadata = {}
    if not args.models:
        print("🔍 Detecting LM Studio models...")
        detector = LMStudioModelDetector()
        models = detector.detect_models()
        if not models:
            print("No models detected. Please specify models manually with --models")
            return
        args.models = [m["name"] for m in models]
        # Store metadata
        for m in models:
            model_metadata[m["name"]] = {
                "size": m.get("size", "unknown"),
                "quantization": m.get("quantization", "unknown"),
                "parameters": m.get("parameters", "unknown"),
                "path": m.get("path", "unknown")
            }
        print(f"Found {len(args.models)} models: {', '.join(args.models)}")
    else:
        # Create placeholder metadata for manually specified models
        for model in args.models:
            model_metadata[model] = {
                "size": "unknown",
                "quantization": "unknown",
                "parameters": "unknown",
                "path": "manual"
            }
    
    # Initialize benchmark
    benchmark = AppleSiliconBenchmarkV2(
        api_base=args.api_base,
        num_runs=args.num_runs
    )
    
    # Generate prompts
    print(f"\n📝 Generating {args.num_prompts} diverse prompts...")
    prompts = benchmark.prompt_generator.generate_default_batch(total_prompts=args.num_prompts)
    print(f"Generated {len(prompts)} prompts across categories:")
    from collections import Counter
    cat_counts = Counter([p.category.value for p in prompts])
    for cat, count in cat_counts.items():
        print(f"  {cat}: {count}")
    
    # Run benchmarks for each model
    parallel = args.parallel and not args.sequential
    for model in args.models:
        benchmark.benchmark_model(model, prompts, parallel=parallel)
    
    # Generate reports
    print("\n📊 Generating reports...")
    report_gen = ReportGeneratorV2(args.output_dir)
    
    md_file = report_gen.generate_markdown_report(benchmark.results)
    print(f"✓ Markdown report: {md_file}")
    
    csv_file = report_gen.generate_csv(benchmark.results)
    print(f"✓ CSV data: {csv_file}")
    
    json_file = report_gen.generate_json(benchmark.results, model_metadata)
    print(f"✓ JSON data: {json_file}")
    
    chart_file = report_gen.generate_radar_chart(benchmark.results)
    print(f"✓ Radar chart: {chart_file}")
    
    print(f"\n✅ Benchmark complete! Results saved to {args.output_dir}/")
    print(f"📝 Post {md_file} on X with the radar chart!")
    print(f"🔬 Statistical rigor: {args.num_runs} runs per prompt, variance reported")
    print(f"📊 Model metadata tracked: {len(model_metadata)} models")


if __name__ == "__main__":
    main()
