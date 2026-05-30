#!/usr/bin/env python3
"""
X Thread Generator - Auto-write viral-quality benchmark threads
Generates engaging Twitter/X threads from benchmark results
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Tweet:
    """Single tweet in a thread."""
    content: str
    image: Optional[str] = None


class XThreadGenerator:
    """Generate X threads from benchmark results."""
    
    def __init__(self, results_dir: str = "devbench_results"):
        self.results_dir = Path(results_dir)
    
    def load_results(self) -> Dict:
        """Load benchmark results from JSON."""
        results_file = self.results_dir / "results.json"
        if results_file.exists():
            with open(results_file) as f:
                return json.load(f)
        return {}
    
    def generate_thread(self, results_data: Dict) -> List[Tweet]:
        """Generate a viral-quality X thread from results."""
        tweets = []
        
        # Tweet 1: Hook
        tweets.append(Tweet(
            content=self._generate_hook(results_data),
            image="radar_chart.png"
        ))
        
        # Tweet 2: Context
        tweets.append(Tweet(content=self._generate_context(results_data)))
        
        # Tweet 3: Leaderboard
        tweets.append(Tweet(content=self._generate_leaderboard(results_data)))
        
        # Tweet 4: Key insight
        tweets.append(Tweet(content=self._generate_key_insight(results_data)))
        
        # Tweet 5: Failure analysis
        tweets.append(Tweet(content=self._generate_failure_analysis(results_data)))
        
        # Tweet 6: Methodology
        tweets.append(Tweet(content=self._generate_methodology()))
        
        # Tweet 7: Call to action
        tweets.append(Tweet(content=self._generate_cta(results_data)))
        
        return tweets
    
    def _generate_hook(self, results_data: Dict) -> str:
        """Generate the hook tweet."""
        if not results_data:
            return "🍎 Just benchmarked local LLMs on MacBook Pro M3 (18GB)\n\nThe results surprised me..."
        
        # Find winner
        winner = results_data.get("overall_winner", "Unknown")
        best_score = results_data.get("best_developer_score", 0)
        
        hooks = [
            f"🍎 I benchmarked {len(results_data.get('models', []))} local LLMs on my M3 MacBook (18GB)\n\nThe winner for actual dev work? {winner}\n\nHere's why 👇",
            f"🚀 Local LLMs on Apple Silicon are getting GOOD\n\nI tested {len(results_data.get('models', []))} models for TypeScript/NestJS/React work\n\n{winner} won by a mile\n\nThread 🧵",
            f"💻 Which local LLM is best for TypeScript dev?\n\nI benchmarked {len(results_data.get('models', []))} models on M3 MacBook Pro\n\nThe answer isn't what you'd expect\n\n🧵",
            f"🔬 Rigorous benchmark: 5 runs per prompt, execution-grounded scoring\n\n{len(results_data.get('models', []))} local LLMs tested for real dev work\n\n{winner} takes the crown\n\nDetails 👇"
        ]
        
        return hooks[0]  # Return first hook
    
    def _generate_context(self, results_data: Dict) -> str:
        """Generate context tweet."""
        return """Why this matters:

Most benchmarks test "model knowledge" on academic tasks (GSM8K, MMLU)

I tested "model usability" for actual dev work:
• TypeScript/NestJS/React
• Real debugging scenarios
• Quality-per-token/sec (not just quality)

Hardware: MacBook Pro M3, 18GB unified memory"""
    
    def _generate_leaderboard(self, results_data: Dict) -> str:
        """Generate leaderboard tweet."""
        models = results_data.get("model_stats", {})
        
        if not models:
            return "No results to display"
        
        # Sort by developer score
        sorted_models = sorted(models.items(), key=lambda x: x[1].get("developer_score", 0), reverse=True)
        
        tweet = "📊 LEADERBOARD\n\n"
        tweet += "Model | DevScore | tok/s\n"
        tweet += "-" * 30 + "\n"
        
        for model, stats in sorted_models[:5]:  # Top 5
            dev_score = stats.get("developer_score", 0)
            tps = stats.get("tokens_per_second", 0)
            tweet += f"{model[:20]} | {dev_score:.2f} | {tps:.1f}\n"
        
        return tweet
    
    def _generate_key_insight(self, results_data: Dict) -> str:
        """Generate key insight tweet."""
        models = results_data.get("model_stats", {})
        
        if not models:
            return "No insights available"
        
        # Find interesting patterns
        insights = []
        
        # Fastest vs best quality
        fastest = max(models.items(), key=lambda x: x[1].get("normalized_tps", 0))
        best_quality = max(models.items(), key=lambda x: x[1].get("developer_score", 0))
        
        if fastest[0] != best_quality[0]:
            insights.append(f"Fastest ({fastest[0]}) ≠ Best Quality ({best_quality[0]})")
        
        # Debugging performance
        best_debugger = max(models.items(), key=lambda x: x[1].get("debugging", 0))
        insights.append(f"Best at debugging: {best_debugger[0]}")
        
        # Code performance
        best_coder = max(models.items(), key=lambda x: x[1].get("code", 0))
        insights.append(f"Best coder: {best_coder[0]}")
        
        tweet = "🔑 KEY INSIGHTS\n\n"
        for insight in insights:
            tweet += f"• {insight}\n"
        
        return tweet
    
    def _generate_failure_analysis(self, results_data: Dict) -> str:
        """Generate failure analysis tweet."""
        failures = results_data.get("failure_analysis", {})
        
        if not failures:
            return "No failure data"
        
        tweet = "🐛 COMMON FAILURES\n\n"
        
        # Top 3 failures
        sorted_failures = sorted(failures.items(), key=lambda x: x[1], reverse=True)[:3]
        for failure, count in sorted_failures:
            tweet += f"• {failure}: {count}x\n"
        
        tweet += "\nThese patterns show where models struggle in real dev work"
        
        return tweet
    
    def _generate_methodology(self) -> str:
        """Generate methodology tweet."""
        return """📋 METHODOLOGY

• 5 runs per prompt (statistical rigor)
• Execution-grounded scoring (ts-node, tsc, eslint)
• Separated metrics (correctness, compliance, reasoning)
• Tokenization-aware (normalized tok/s)
• Real debugging scenarios (race conditions, DI bugs)

Not just keyword matching - actual code execution"""
    
    def _generate_cta(self, results_data: Dict) -> str:
        """Generate call to action tweet."""
        return """🚀 Want to benchmark your models?

The full benchmark is open source:
github.com/kevinjobin1/lm-studio-benchmark-harness

It auto-detects LM Studio models and generates X-ready reports

Built for developers who care about practical performance, not academic scores

🧵 End"""
    
    def format_for_posting(self, tweets: List[Tweet]) -> str:
        """Format tweets for easy copying."""
        output = "X THREAD - Copy and paste each tweet:\n\n"
        
        for i, tweet in enumerate(tweets, 1):
            output += f"--- Tweet {i}/{len(tweets)} ---\n"
            output += tweet.content + "\n"
            if tweet.image:
                output += f"[Attach: {tweet.image}]\n"
            output += "\n"
        
        return output
    
    def save_thread(self, tweets: List[Tweet], filename: str = "x_thread.txt"):
        """Save thread to file."""
        thread_file = self.results_dir / filename
        with open(thread_file, 'w') as f:
            f.write(self.format_for_posting(tweets))
        
        return str(thread_file)


def main():
    """Generate X thread from latest results."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate X thread from benchmark results")
    parser.add_argument("--results-dir", default="devbench_results", help="Results directory")
    
    args = parser.parse_args()
    
    generator = XThreadGenerator(args.results_dir)
    results_data = generator.load_results()
    
    tweets = generator.generate_thread(results_data)
    
    thread_file = generator.save_thread(tweets)
    print(f"✅ X thread generated: {thread_file}")
    print(f"📝 {len(tweets)} tweets ready to post")


if __name__ == "__main__":
    main()
