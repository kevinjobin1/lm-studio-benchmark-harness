#!/usr/bin/env python3
"""
Apple Silicon LLM Benchmark for LM Studio
Focused on TypeScript/NestJS/React stack with quality-per-token/sec metrics
"""

import json
import time
import psutil
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from openai import OpenAI
import matplotlib.pyplot as plt
import numpy as np


@dataclass
class BenchmarkResult:
    """Result from a single benchmark run."""
    model: str
    category: str
    prompt: str
    response: str
    ttft: float  # Time to first token in seconds
    total_time: float  # Total generation time
    tokens_per_second: float
    quality_score: float  # 0-1
    ram_usage_mb: float
    quality_per_token_sec: float  # quality_score * tokens_per_second


class LMStudioModelDetector:
    """Auto-detect models installed in LM Studio."""
    
    def __init__(self, lm_studio_path: str = "~/Library/Application Support/LM Studio"):
        self.lm_studio_path = Path(lm_studio_path).expanduser()
    
    def detect_models(self) -> List[Dict[str, str]]:
        """Detect installed LM Studio models."""
        models = []
        
        try:
            # Try to get models from LM Studio's models directory
            models_dir = self.lm_studio_path / "Models"
            if models_dir.exists():
                for model_path in models_dir.iterdir():
                    if model_path.is_dir():
                        # Look for model config files
                        config_file = model_path / "model_config.json"
                        if config_file.exists():
                            with open(config_file) as f:
                                config = json.load(f)
                                models.append({
                                    "name": config.get("model_name", model_path.name),
                                    "path": str(model_path),
                                    "size": config.get("size", "unknown"),
                                    "quantization": config.get("quantization", "unknown")
                                })
                        else:
                            # Fallback to directory name
                            models.append({
                                "name": model_path.name,
                                "path": str(model_path),
                                "size": "unknown",
                                "quantization": "unknown"
                            })
        except Exception as e:
            print(f"Could not auto-detect models: {e}")
            print("Please specify models manually with --models flag")
        
        return models


class TypeScriptBenchmarkPrompts:
    """Benchmark prompts focused on TypeScript/NestJS/React stack."""
    
    CODE_PROMPTS = [
        {
            "category": "code",
            "prompt": "Implement a NestJS AuthGuard that validates JWT tokens and checks if the user has the 'admin' role. Include proper error handling and type definitions.",
            "expected_keywords": ["AuthGuard", "JwtService", "CanActivate", "admin", "role"]
        },
        {
            "category": "code",
            "prompt": "Create a React Query hook for fetching user data with caching, retry logic, and proper TypeScript types. Include loading and error states.",
            "expected_keywords": ["useQuery", "QueryClient", "cacheTime", "retry", "loading", "error"]
        },
        {
            "category": "code",
            "prompt": "Write a Prisma migration to add a 'posts' table with columns: id (UUID), title (string), content (text), authorId (foreign key to users), createdAt and updatedAt timestamps.",
            "expected_keywords": ["createTable", "uuid", "string", "text", "foreignKey", "timestamp"]
        },
        {
            "category": "code",
            "prompt": "Fix this TypeScript type error: 'Type 'string' is not assignable to type 'number'. The error occurs in a function that should accept either a string ID or a numeric ID.",
            "expected_keywords": ["union", "type", "string", "number", "typeof", "interface"]
        },
        {
            "category": "code",
            "prompt": "Implement a TypeScript generic repository pattern for NestJS with CRUD operations, pagination, and filtering support.",
            "expected_keywords": ["Repository", "Generic", "T", "extends", "find", "create", "update", "delete"]
        }
    ]
    
    FRONTEND_PROMPTS = [
        {
            "category": "frontend",
            "prompt": "Build an Awwwards-style hero section with a large typography headline, subtle parallax effect, and smooth scroll-triggered animations using Framer Motion.",
            "expected_keywords": ["framer-motion", "useScroll", "useTransform", "parallax", "animate", "transition"]
        },
        {
            "category": "frontend",
            "prompt": "Create a Three.js scene with a rotating icosahedron, ambient lighting, and mouse interaction that changes the object's color on hover.",
            "expected_keywords": ["Three", "Scene", "Mesh", "IcosahedronGeometry", "Raycaster", "hover"]
        },
        {
            "category": "frontend",
            "prompt": "Generate a modern landing page using Tailwind CSS with a hero section, features grid, testimonials carousel, and call-to-action with gradient backgrounds.",
            "expected_keywords": ["Tailwind", "gradient", "grid", "carousel", "hero", "features"]
        },
        {
            "category": "frontend",
            "prompt": "Implement a React component with a custom hook that manages complex form state with validation, debounced input, and auto-save functionality.",
            "expected_keywords": ["useState", "useEffect", "useCallback", "debounce", "validation", "auto-save"]
        }
    ]
    
    REASONING_PROMPTS = [
        {
            "category": "reasoning",
            "prompt": "Plan the architecture for a real-time collaborative document editor. Consider: conflict resolution, operational transformation vs CRDTs, scalability, and offline support. Provide a step-by-step implementation plan.",
            "expected_keywords": ["CRDT", "operational transformation", "WebSocket", "conflict", "scalability", "offline"]
        },
        {
            "category": "reasoning",
            "prompt": "Design a microservices architecture for an e-commerce platform. Break down into: user service, product service, order service, payment service. Define API contracts, data flow, and communication patterns.",
            "expected_keywords": ["microservices", "API", "REST", "gRPC", "event-driven", "message queue"]
        },
        {
            "category": "reasoning",
            "prompt": "Analyze the trade-offs between using PostgreSQL vs MongoDB for a social media application. Consider: data structure, query patterns, scaling, consistency, and development velocity.",
            "expected_keywords": ["PostgreSQL", "MongoDB", "relational", "document", "ACID", "scaling", "consistency"]
        }
    ]
    
    MATH_PROMPTS = [
        {
            "category": "math",
            "prompt": "A developer has 42 unit tests. 15% are integration tests, the rest are unit tests. If 8 new integration tests are added, what percentage of the total tests are now integration tests?",
            "expected_answer": 0.37  # (6.3 + 8) / (42 + 8) = 14.3 / 50 = 0.286, let me recalc: 15% of 42 = 6.3, +8 = 14.3, total = 50, 14.3/50 = 0.286
        },
        {
            "category": "math",
            "prompt": "A React app renders 120 components on initial load. Each component makes 2 API calls. If API calls are batched in groups of 10, how many batch requests are made?",
            "expected_answer": 24  # 120 * 2 = 240 calls, /10 = 24 batches
        },
        {
            "category": "math",
            "prompt": "A database has 1,000,000 records. A query takes 0.5 seconds per 10,000 records. How long will it take to query all records with a single query?",
            "expected_answer": 50  # 1,000,000 / 10,000 * 0.5 = 50 seconds
        }
    ]
    
    INSTRUCTION_FOLLOWING_PROMPTS = [
        {
            "category": "instruction",
            "prompt": "Output valid JSON only with this structure: {\"framework\": \"string\", \"version\": \"number\", \"features\": [\"string\"]}. Describe React.",
            "check": lambda x: self._is_valid_json(x)
        },
        {
            "category": "instruction",
            "prompt": "List exactly 3 benefits of using TypeScript. Use bullet points. No markdown formatting.",
            "check": lambda x: x.count("•") == 3 and "**" not in x and "```" not in x
        },
        {
            "category": "instruction",
            "prompt": "Explain what NestJS is in exactly one sentence. No markdown, no bullet points.",
            "check": lambda x: x.count(".") == 1 and "**" not in x and "```" not in x and "\n" not in x
        }
    ]
    
    @staticmethod
    def _is_valid_json(text: str) -> bool:
        try:
            json.loads(text)
            return True
        except:
            return False
    
    def get_all_prompts(self) -> List[Dict]:
        """Get all benchmark prompts."""
        return (
            self.CODE_PROMPTS +
            self.FRONTEND_PROMPTS +
            self.REASONING_PROMPTS +
            self.MATH_PROMPTS +
            self.INSTRUCTION_FOLLOWING_PROMPTS
        )


class AppleSiliconBenchmark:
    """Benchmark runner optimized for Apple Silicon LM Studio models."""
    
    def __init__(self, api_base: str = "http://localhost:1234/v1", api_key: str = "lm-studio"):
        self.client = OpenAI(base_url=api_base, api_key=api_key)
        self.prompts = TypeScriptBenchmarkPrompts()
        self.results: List[BenchmarkResult] = []
    
    def run_benchmark(self, model_name: str, prompt_data: Dict) -> BenchmarkResult:
        """Run a single benchmark."""
        prompt = prompt_data["prompt"]
        category = prompt_data["category"]
        
        # Start memory monitoring
        process = psutil.Process()
        start_ram = process.memory_info().rss / 1024 / 1024
        
        # Make API call with streaming for accurate TTFT
        start_time = time.time()
        first_token_time = None
        response_text = ""
        token_count = 0
        
        try:
            stream = self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1000,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    if first_token_time is None:
                        first_token_time = time.time()
                    response_text += chunk.choices[0].delta.content
                    token_count += 1
            
            total_time = time.time() - start_time
            ttft = first_token_time - start_time if first_token_time else total_time
            tokens_per_second = token_count / total_time if total_time > 0 else 0
            
        except Exception as e:
            print(f"Error benchmarking {model_name}: {e}")
            return BenchmarkResult(
                model=model_name,
                category=category,
                prompt=prompt,
                response="",
                ttft=0,
                total_time=0,
                tokens_per_second=0,
                quality_score=0,
                ram_usage_mb=0,
                quality_per_token_sec=0
            )
        
        # End memory monitoring
        end_ram = process.memory_info().rss / 1024 / 1024
        ram_usage = end_ram - start_ram
        
        # Calculate quality score
        quality_score = self._calculate_quality(response_text, prompt_data)
        
        # Calculate quality-per-token/sec
        quality_per_token_sec = quality_score * tokens_per_second
        
        return BenchmarkResult(
            model=model_name,
            category=category,
            prompt=prompt,
            response=response_text,
            ttft=ttft,
            total_time=total_time,
            tokens_per_second=tokens_per_second,
            quality_score=quality_score,
            ram_usage_mb=ram_usage,
            quality_per_token_sec=quality_per_token_sec
        )
    
    def _calculate_quality(self, response: str, prompt_data: Dict) -> float:
        """Calculate quality score based on expected keywords or checks."""
        category = prompt_data["category"]
        
        if category == "instruction":
            # Use the check function
            check_func = prompt_data.get("check")
            if check_func:
                return 1.0 if check_func(response) else 0.0
            return 0.5
        
        if category == "math":
            # Check if answer is close to expected
            expected = prompt_data.get("expected_answer")
            if expected is not None:
                # Try to extract number from response
                import re
                numbers = re.findall(r'-?\d+\.?\d*', response)
                if numbers:
                    predicted = float(numbers[-1])
                    return 1.0 if abs(predicted - expected) < 0.1 else 0.0
            return 0.5
        
        # For code, frontend, reasoning: check for expected keywords
        expected_keywords = prompt_data.get("expected_keywords", [])
        if expected_keywords:
            response_lower = response.lower()
            matches = sum(1 for kw in expected_keywords if kw.lower() in response_lower)
            return matches / len(expected_keywords)
        
        return 0.5  # Default middle score
    
    def benchmark_model(self, model_name: str, prompts: Optional[List[Dict]] = None) -> List[BenchmarkResult]:
        """Benchmark a single model against all prompts."""
        if prompts is None:
            prompts = self.prompts.get_all_prompts()
        
        print(f"\n🚀 Benchmarking {model_name}")
        print(f"   Running {len(prompts)} benchmarks...\n")
        
        model_results = []
        for i, prompt_data in enumerate(prompts):
            print(f"   [{i+1}/{len(prompts)}] {prompt_data['category']}: {prompt_data['prompt'][:50]}...")
            result = self.run_benchmark(model_name, prompt_data)
            model_results.append(result)
            print(f"      Quality: {result.quality_score:.2f} | Speed: {result.tokens_per_second:.1f} tok/s | QPS: {result.quality_per_token_sec:.2f}")
        
        self.results.extend(model_results)
        return model_results


class ReportGenerator:
    """Generate markdown reports and charts for X."""
    
    def __init__(self, output_dir: str = "apple_silicon_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_markdown_report(self, results: List[BenchmarkResult]) -> str:
        """Generate markdown report ready for X."""
        # Group results by model
        by_model: Dict[str, List[BenchmarkResult]] = {}
        for result in results:
            if result.model not in by_model:
                by_model[result.model] = []
            by_model[result.model].append(result)
        
        # Calculate aggregate metrics per model
        model_stats = {}
        for model, model_results in by_model.items():
            code_results = [r for r in model_results if r.category == "code"]
            frontend_results = [r for r in model_results if r.category == "frontend"]
            reasoning_results = [r for r in model_results if r.category == "reasoning"]
            math_results = [r for r in model_results if r.category == "math"]
            instruction_results = [r for r in model_results if r.category == "instruction"]
            
            avg_speed = sum(r.tokens_per_second for r in model_results) / len(model_results)
            avg_ttft = sum(r.ttft for r in model_results) / len(model_results)
            avg_qps = sum(r.quality_per_token_sec for r in model_results) / len(model_results)
            
            model_stats[model] = {
                "code": sum(r.quality_score for r in code_results) / len(code_results) if code_results else 0,
                "frontend": sum(r.quality_score for r in frontend_results) / len(frontend_results) if frontend_results else 0,
                "reasoning": sum(r.quality_score for r in reasoning_results) / len(reasoning_results) if reasoning_results else 0,
                "math": sum(r.quality_score for r in math_results) / len(math_results) if math_results else 0,
                "instruction": sum(r.quality_score for r in instruction_results) / len(instruction_results) if instruction_results else 0,
                "tokens_per_second": avg_speed,
                "ttft": avg_ttft,
                "quality_per_token_sec": avg_qps
            }
        
        # Generate markdown
        md = "# 🍎 Apple Silicon LLM Benchmark Results\n\n"
        md += "Benchmarking TypeScript/NestJS/React performance on M3 MacBook Pro (18GB)\n\n"
        md += f"**Metric of focus: Quality-per-token/sec** (not just raw quality)\n\n"
        
        # Summary table
        md += "## 📊 Summary\n\n"
        md += "| Model | Code | Frontend | Reasoning | Math | IF | tok/s | TTFT | QPS |\n"
        md += "|-------|------|----------|-----------|------|----|-------|------|-----|\n"
        
        for model, stats in sorted(model_stats.items(), key=lambda x: x[1]["quality_per_token_sec"], reverse=True):
            md += f"| {model} | {stats['code']:.2%} | {stats['frontend']:.2%} | {stats['reasoning']:.2%} | {stats['math']:.2%} | {stats['instruction']:.2%} | {stats['tokens_per_second']:.1f} | {stats['ttft']:.2f}s | {stats['quality_per_token_sec']:.2f} |\n"
        
        # Awards
        md += "\n## 🏆 Awards\n\n"
        
        best_coder = max(model_stats.items(), key=lambda x: x[1]["code"])
        md += f"**Best Coder**: {best_coder[0]} ({best_coder[1]['code']:.2%})\n\n"
        
        fastest = max(model_stats.items(), key=lambda x: x[1]["tokens_per_second"])
        md += f"**Fastest**: {fastest[0]} ({fastest[1]['tokens_per_second']:.1f} tok/s)\n\n"
        
        best_value = max(model_stats.items(), key=lambda x: x[1]["quality_per_token_sec"])
        md += f"**Best Value** (Quality/Speed): {best_value[0]} ({best_value[1]['quality_per_token_sec']:.2f} QPS)\n\n"
        
        overall_winner = best_value[0]
        md += f"**Overall Winner**: {overall_winner}\n\n"
        
        # Methodology
        md += "## 📋 Methodology\n\n"
        md += "- **Hardware**: MacBook Pro M3, 18GB unified memory\n"
        md += "- **Models**: Auto-detected from LM Studio\n"
        md += "- **Prompts**: TypeScript/NestJS/React focused (not generic coding tasks)\n"
        md += "- **Metrics**: Quality score × tokens/sec = Quality-per-token/sec\n"
        md += "- **Categories**: Code (40%), Frontend (20%), Reasoning (15%), Math (15%), Instruction Following (10%)\n\n"
        
        md += "The question this answers: **Which model gives the best answers while still feeling instant on an 18GB MacBook?**\n"
        
        # Save markdown
        md_file = self.output_dir / "results.md"
        with open(md_file, 'w') as f:
            f.write(md)
        
        return str(md_file)
    
    def generate_csv(self, results: List[BenchmarkResult]) -> str:
        """Generate CSV for data analysis."""
        import csv
        
        csv_file = self.output_dir / "results.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["model", "category", "quality_score", "tokens_per_second", "ttft", "quality_per_token_sec", "ram_usage_mb"])
            
            for result in results:
                writer.writerow([
                    result.model,
                    result.category,
                    result.quality_score,
                    result.tokens_per_second,
                    result.ttft,
                    result.quality_per_token_sec,
                    result.ram_usage_mb
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
        categories = ["code", "frontend", "reasoning", "math", "instruction"]
        model_data = {}
        
        for model, model_results in by_model.items():
            scores = []
            for cat in categories:
                cat_results = [r for r in model_results if r.category == cat]
                if cat_results:
                    avg_score = sum(r.quality_score for r in cat_results) / len(cat_results)
                    scores.append(avg_score)
                else:
                    scores.append(0)
            model_data[model] = scores
        
        # Create radar chart
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
        
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]  # Complete the circle
        
        colors = plt.cm.Set3(np.linspace(0, 1, len(model_data)))
        
        for (model, scores), color in zip(model_data.items(), colors):
            scores += scores[:1]  # Complete the circle
            ax.plot(angles, scores, 'o-', linewidth=2, label=model, color=color)
            ax.fill(angles, scores, alpha=0.25, color=color)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([c.title() for c in categories])
        ax.set_ylim(0, 1)
        ax.set_title('Model Capability Radar Chart', size=16, pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        ax.grid(True)
        
        chart_file = self.output_dir / "radar_chart.png"
        plt.savefig(chart_file, dpi=150, bbox_inches='tight')
        plt.close()
        
        return str(chart_file)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Apple Silicon LLM Benchmark for LM Studio")
    parser.add_argument("--api-base", default="http://localhost:1234/v1", help="LM Studio API base URL")
    parser.add_argument("--models", nargs="+", help="Specific models to benchmark (default: auto-detect)")
    parser.add_argument("--output-dir", default="apple_silicon_results", help="Output directory")
    parser.add_argument("--quick", action="store_true", help="Quick mode with fewer prompts")
    
    args = parser.parse_args()
    
    # Detect models if not specified
    if not args.models:
        print("🔍 Detecting LM Studio models...")
        detector = LMStudioModelDetector()
        models = detector.detect_models()
        if not models:
            print("No models detected. Please specify models manually with --models")
            return
        args.models = [m["name"] for m in models]
        print(f"Found {len(args.models)} models: {', '.join(args.models)}")
    
    # Initialize benchmark
    benchmark = AppleSiliconBenchmark(api_base=args.api_base)
    
    # Get prompts (subset for quick mode)
    prompts = benchmark.prompts.get_all_prompts()
    if args.quick:
        prompts = prompts[:5]  # Just 5 prompts for quick testing
    
    # Run benchmarks for each model
    for model in args.models:
        benchmark.benchmark_model(model, prompts)
    
    # Generate reports
    print("\n📊 Generating reports...")
    report_gen = ReportGenerator(args.output_dir)
    
    md_file = report_gen.generate_markdown_report(benchmark.results)
    print(f"✓ Markdown report: {md_file}")
    
    csv_file = report_gen.generate_csv(benchmark.results)
    print(f"✓ CSV data: {csv_file}")
    
    chart_file = report_gen.generate_radar_chart(benchmark.results)
    print(f"✓ Radar chart: {chart_file}")
    
    print(f"\n✅ Benchmark complete! Results saved to {args.output_dir}/")
    print(f"📝 Post {md_file} on X with the radar chart!")


if __name__ == "__main__":
    main()
