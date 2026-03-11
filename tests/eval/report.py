"""Report generator -- creates a self-contained HTML dashboard from scores.

Usage:
    PYTHONPATH=. python tests/eval/report.py
    -> generates tests/eval/results/report.html
"""

import argparse
import base64
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

RESULTS_DIR = Path(__file__).parent / "results"
TEMPLATES_DIR = Path(__file__).parent / "templates"

DIMENSIONS = [
    ("factual_correctness", "Factual Correctness"),
    ("response_quality", "Response Quality"),
    ("conversation_coherence", "Conversation Coherence"),
    ("error_handling", "Error Handling"),
    ("chart_quality", "Chart Quality"),
]


def score_color_class(avg: float) -> tuple[str, str]:
    """Return CSS class names for score value and fill bar."""
    if avg >= 4.0:
        return "score-excellent", "fill-excellent"
    elif avg >= 3.0:
        return "score-good", "fill-good"
    elif avg >= 2.0:
        return "score-average", "fill-average"
    return "score-poor", "fill-poor"


def load_scores(run_dir: Path | None = None) -> list[dict]:
    """Load scores from run_dir/scores.json."""
    base_dir = run_dir if run_dir else RESULTS_DIR
    path = base_dir / "scores.json"
    if not path.exists():
        raise FileNotFoundError(f"No scores found at {path}. Run judge.py first.")
    return json.loads(path.read_text())


def compute_aggregates(all_scores: list[dict]) -> dict:
    """Compute aggregate scores across all scenarios and turns."""
    dim_totals: dict[str, list[float]] = {key: [] for key, _ in DIMENSIONS}

    for scenario in all_scores:
        for turn in scenario.get("turns", []):
            for key, _ in DIMENSIONS:
                val = turn.get(key)
                if isinstance(val, dict) and "score" in val and val["score"] > 0:
                    dim_totals[key].append(val["score"])

    dimensions = []
    for key, label in DIMENSIONS:
        scores = dim_totals[key]
        avg = sum(scores) / len(scores) if scores else 0
        color_class, fill_class = score_color_class(avg)
        dimensions.append({
            "key": key,
            "label": label,
            "avg": avg,
            "count": len(scores),
            "color_class": color_class,
            "fill_class": fill_class,
        })

    return {"dimensions": dimensions}


def embed_screenshots(all_scores: list[dict]) -> list[dict]:
    """Read screenshot PNGs and embed as base64 in turn data."""
    for scenario in all_scores:
        for turn in scenario.get("turns", []):
            for key in ("screenshot_full", "screenshot_chart", "screenshot_table"):
                b64_key = key + "_b64"
                path_str = turn.get(key)
                if path_str:
                    p = Path(path_str)
                    if p.exists():
                        data = p.read_bytes()
                        turn[b64_key] = base64.standard_b64encode(data).decode("utf-8")
                    else:
                        turn[b64_key] = None
                else:
                    turn[b64_key] = None
    return all_scores


def collect_issues(all_scores: list[dict]) -> list[dict]:
    """Aggregate all issues_found across turns, deduplicate, sort by frequency."""
    counter: Counter[str] = Counter()
    for scenario in all_scores:
        for turn in scenario.get("turns", []):
            for issue in turn.get("issues_found", []):
                if issue:
                    counter[issue.strip()] += 1

    return [{"text": text, "count": count} for text, count in counter.most_common()]


def prepare_scenarios(all_scores: list[dict]) -> list[dict]:
    """Prepare scenario data for the template."""
    scenarios = []
    for scenario in all_scores:
        turns = scenario.get("turns", [])
        # Compute average score across all dimensions for this scenario
        all_turn_scores = []
        for turn in turns:
            for key, _ in DIMENSIONS:
                val = turn.get(key)
                if isinstance(val, dict) and "score" in val and val["score"] > 0:
                    all_turn_scores.append(val["score"])

        avg_score = sum(all_turn_scores) / len(all_turn_scores) if all_turn_scores else 0

        scenarios.append({
            "name": scenario.get("scenario_name", "Unknown"),
            "turns": turns,
            "avg_score": avg_score,
        })
    return scenarios


def generate_report(all_scores: list[dict], run_dir: Path | None = None) -> Path:
    """Generate the HTML report from scores data."""
    # Embed screenshots
    all_scores = embed_screenshots(all_scores)

    # Compute aggregates
    aggs = compute_aggregates(all_scores)

    # Collect issues
    issues = collect_issues(all_scores)

    # Prepare scenarios
    scenarios = prepare_scenarios(all_scores)

    # Get metadata
    judge_model = "unknown"
    for s in all_scores:
        if s.get("judge_model"):
            judge_model = s["judge_model"]
            break

    # Render template
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("report.html.j2")

    html = template.render(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        judge_model=judge_model,
        scenario_count=len(all_scores),
        dimensions=aggs["dimensions"],
        issues=issues,
        scenarios=scenarios,
    )

    # Write report
    base_dir = run_dir if run_dir else RESULTS_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    output_path = base_dir / "report.html"
    output_path.write_text(html)
    print(f"Report generated: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Eval report generator")
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Run directory (default: latest)",
    )
    args = parser.parse_args()

    # Determine run directory
    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        latest = RESULTS_DIR / "latest"
        if latest.is_symlink() or latest.exists():
            run_dir = latest.resolve()
        else:
            run_dir = None

    if run_dir:
        print(f"Run directory: {run_dir}")

    all_scores = load_scores(run_dir=run_dir)
    print(f"Loaded scores for {len(all_scores)} scenario(s)")
    generate_report(all_scores, run_dir=run_dir)


if __name__ == "__main__":
    main()
