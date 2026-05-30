"""
Reporting and visualization module for benchmark results.
"""

import json
import csv
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path


class ReportGenerator:
    """Generates reports from benchmark results."""
    
    def __init__(self, output_dir: str = "results"):
        self.output_dir = Path(output_dir)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = self.output_dir / self.timestamp
        self.run_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_all(self, summary: Dict[str, Any], results: List) -> Dict[str, str]:
        """Generate all report formats."""
        files = {}
        
        # JSON summary
        json_file = self.run_dir / "summary.json"
        with open(json_file, 'w') as f:
            json.dump(summary, f, indent=2)
        files["json"] = str(json_file)
        
        # CSV metrics
        csv_file = self.run_dir / "metrics.csv"
        self._generate_csv(results, csv_file)
        files["csv"] = str(csv_file)
        
        # HTML report
        html_file = self.run_dir / "report.html"
        self._generate_html(summary, html_file)
        files["html"] = str(html_file)
        
        return files
    
    def generate_comparison_report(self, comparison_results: Dict[str, Any]) -> str:
        """Generate side-by-side comparison report for multiple frameworks."""
        html_file = self.run_dir / "comparison_report.html"
        self._generate_comparison_html(comparison_results, html_file)
        return str(html_file)
    
    def _generate_csv(self, results: List, output_file: Path):
        """Generate CSV with raw metrics."""
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["benchmark", "metric", "score", "timestamp", "metadata"])
            
            for result in results:
                metadata_str = json.dumps(result.metadata)
                writer.writerow([
                    result.benchmark_name,
                    result.metric_name,
                    result.score,
                    result.timestamp,
                    metadata_str
                ])
    
    def _generate_html(self, summary: Dict[str, Any], output_file: Path):
        """Generate HTML report with visualizations."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>LM Studio Benchmark Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header .timestamp {{
            opacity: 0.9;
            margin-top: 10px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .card h3 {{
            margin: 0 0 15px 0;
            color: #333;
            font-size: 1.1em;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }}
        .metric:last-child {{
            border-bottom: none;
        }}
        .metric-name {{
            color: #666;
        }}
        .metric-value {{
            font-weight: bold;
            color: #333;
        }}
        .benchmark-section {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .benchmark-section h2 {{
            margin: 0 0 20px 0;
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .score-bar {{
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .score-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 10px;
            color: white;
            font-weight: bold;
            transition: width 0.5s ease;
        }}
        .good {{ background: linear-gradient(90deg, #10b981, #059669); }}
        .medium {{ background: linear-gradient(90deg, #f59e0b, #d97706); }}
        .poor {{ background: linear-gradient(90deg, #ef4444, #dc2626); }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #666;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 LM Studio Benchmark Report</h1>
        <div class="timestamp">Generated: {summary.get('timestamp', 'N/A')}</div>
        <div class="timestamp">Model: {summary.get('model', 'N/A')}</div>
    </div>
"""
        
        # Generate benchmark sections
        for benchmark_name, benchmark_data in summary.get("benchmarks", {}).items():
            html += f"""
    <div class="benchmark-section">
        <h2>{benchmark_name.replace('_', ' ').title()}</h2>
"""
            
            metrics = benchmark_data.get("metrics", {})
            for metric_name, metric_data in metrics.items():
                score = metric_data.get("mean", 0)
                count = metric_data.get("count", 0)
                
                # Determine color class based on score
                if score >= 0.7:
                    color_class = "good"
                elif score >= 0.4:
                    color_class = "medium"
                else:
                    color_class = "poor"
                
                # Format score based on metric type
                if "tokens" in metric_name or "ttft" in metric_name:
                    score_display = f"{score:.2f}"
                else:
                    score_display = f"{score:.2%}"
                
                html += f"""
        <div class="metric">
            <span class="metric-name">{metric_name.replace('_', ' ').title()}</span>
            <span class="metric-value">{score_display} (n={count})</span>
        </div>
        <div class="score-bar">
            <div class="score-fill {color_class}" style="width: {min(score * 100, 100)}%">
                {score_display}
            </div>
        </div>
"""
            
            html += """
    </div>
"""
        
        html += """
    <div class="footer">
        <p>Generated by LM Studio Benchmark Harness</p>
    </div>
</body>
</html>
"""
        
        with open(output_file, 'w') as f:
            f.write(html)
    
    def _generate_comparison_html(self, comparison_results: Dict[str, Any], output_file: Path):
        """Generate HTML report with side-by-side framework comparison."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Framework Comparison Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header .timestamp {{
            opacity: 0.9;
            margin-top: 10px;
        }}
        .comparison-table {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            overflow-x: auto;
        }}
        .comparison-table h2 {{
            margin: 0 0 20px 0;
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 12px;
            text-align: center;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
        }}
        th:first-child, td:first-child {{
            text-align: left;
            font-weight: 600;
        }}
        .score {{
            font-weight: bold;
            padding: 5px 10px;
            border-radius: 5px;
            display: inline-block;
            min-width: 60px;
        }}
        .score-high {{
            background: #d4edda;
            color: #155724;
        }}
        .score-medium {{
            background: #fff3cd;
            color: #856404;
        }}
        .score-low {{
            background: #f8d7da;
            color: #721c24;
        }}
        .framework-section {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .framework-section h3 {{
            margin: 0 0 15px 0;
            color: #333;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #666;
            padding: 20px;
        }}
        .legend {{
            display: flex;
            gap: 20px;
            margin-top: 15px;
            font-size: 0.9em;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔄 Framework Comparison Report</h1>
        <div class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>
"""
        
        # Generate comparison table
        html += """
    <div class="comparison-table">
        <h2>Side-by-Side Comparison</h2>
        <table>
            <thead>
                <tr>
                    <th>Benchmark</th>
                    <th>LM Eval</th>
                    <th>OpenBench</th>
                    <th>Custom</th>
                    <th>Best</th>
                </tr>
            </thead>
            <tbody>
"""
        
        # Extract benchmark names from comparison results
        all_benchmarks = set()
        for framework in ["lm_eval", "openbench", "custom"]:
            if framework in comparison_results:
                if framework == "custom":
                    if "benchmarks" in comparison_results[framework]:
                        all_benchmarks.update(comparison_results[framework]["benchmarks"].keys())
                else:
                    if "lm_eval" in comparison_results[framework] and "results" in comparison_results[framework]["lm_eval"]:
                        all_benchmarks.update(comparison_results[framework]["lm_eval"]["results"].keys())
        
        # For each benchmark, get scores from each framework
        for benchmark in sorted(all_benchmarks):
            lm_eval_score = self._extract_score(comparison_results, "lm_eval", benchmark)
            openbench_score = self._extract_score(comparison_results, "openbench", benchmark)
            custom_score = self._extract_score(comparison_results, "custom", benchmark)
            
            # Determine best score
            scores = [s for s in [lm_eval_score, openbench_score, custom_score] if s is not None]
            best_score = max(scores) if scores else None
            
            # Format scores with color classes
            lm_eval_class = self._get_score_class(lm_eval_score, best_score)
            openbench_class = self._get_score_class(openbench_score, best_score)
            custom_class = self._get_score_class(custom_score, best_score)
            
            html += f"""
                <tr>
                    <td>{benchmark.replace('_', ' ').title()}</td>
                    <td><span class="score {lm_eval_class}">{lm_eval_score if lm_eval_score is not None else 'N/A'}</span></td>
                    <td><span class="score {openbench_class}">{openbench_score if openbench_score is not None else 'N/A'}</span></td>
                    <td><span class="score {custom_class}">{custom_score if custom_score is not None else 'N/A'}</span></td>
                    <td><span class="score score-high">{best_score if best_score is not None else 'N/A'}</span></td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color" style="background: #d4edda;"></div>
                <span>Best Score</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #fff3cd;"></div>
                <span>Medium Score</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #f8d7da;"></div>
                <span>Low Score</span>
            </div>
        </div>
    </div>
"""
        
        # Add individual framework sections
        for framework_name in ["LM Eval", "OpenBench", "Custom"]:
            framework_key = framework_name.lower().replace(" ", "_")
            if framework_key in comparison_results:
                html += f"""
    <div class="framework-section">
        <h3>{framework_name} Details</h3>
        <pre>{json.dumps(comparison_results[framework_key], indent=2, default=str)[:1000]}</pre>
    </div>
"""
        
        html += """
    <div class="footer">
        <p>Generated by LM Studio Benchmark Harness - Framework Comparison Mode</p>
    </div>
</body>
</html>
"""
        
        with open(output_file, 'w') as f:
            f.write(html)
    
    def _extract_score(self, comparison_results: Dict[str, Any], framework: str, benchmark: str) -> Optional[float]:
        """Extract score from comparison results for a specific framework and benchmark."""
        try:
            if framework == "custom":
                if "custom" in comparison_results and "benchmarks" in comparison_results["custom"]:
                    if benchmark in comparison_results["custom"]["benchmarks"]:
                        metrics = comparison_results["custom"]["benchmarks"][benchmark].get("metrics", {})
                        if metrics:
                            first_metric = list(metrics.values())[0]
                            return first_metric.get("mean", 0)
            else:
                if framework in comparison_results and "lm_eval" in comparison_results[framework]:
                    if "results" in comparison_results[framework]["lm_eval"]:
                        results = comparison_results[framework]["lm_eval"]["results"]
                        # Map benchmark name to task name
                        from integrations import LM_EVAL_TASK_MAPPING, OPENBENCH_TASK_MAPPING
                        mapping = LM_EVAL_TASK_MAPPING if framework == "lm_eval" else OPENBENCH_TASK_MAPPING
                        if benchmark in mapping:
                            task_name = mapping[benchmark]
                            if task_name in results:
                                metrics = results[task_name]
                                if metrics:
                                    first_metric = list(metrics.values())[0]
                                    return float(first_metric) if isinstance(first_metric, (int, float)) else None
        except:
            pass
        return None
    
    def _get_score_class(self, score: Optional[float], best_score: Optional[float]) -> str:
        """Get CSS class for score based on value."""
        if score is None:
            return ""
        if best_score is not None and score == best_score:
            return "score-high"
        if score >= 0.7:
            return "score-high"
        elif score >= 0.4:
            return "score-medium"
        else:
            return "score-low"
