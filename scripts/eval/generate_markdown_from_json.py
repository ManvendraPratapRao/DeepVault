"""
One-off script to generate a markdown report from an existing summary.json.
Useful if the evaluation run finished before the markdown report feature was added.
"""
import json
import sys
from pathlib import Path

from scripts.eval.report import generate_markdown_report

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/eval/generate_markdown_from_json.py <run_id>")
        sys.exit(1)
        
    run_id = sys.argv[1]
    json_path = Path(f"data/eval_runs/{run_id}/summary.json")
    
    if not json_path.exists():
        print(f"Error: {json_path} does not exist.")
        sys.exit(1)
        
    with open(json_path, encoding="utf-8") as f:
        results = json.load(f)
        
    generate_markdown_report(run_id, results)
    print(f"Successfully generated Markdown report for {run_id}")
