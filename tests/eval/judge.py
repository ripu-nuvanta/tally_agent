"""Judge phase — LLM-as-a-judge scoring of collected transcripts.

Usage:
    PYTHONPATH=. ANTHROPIC_API_KEY=<key> python tests/eval/judge.py
    PYTHONPATH=. python tests/eval/judge.py --transcript financial_deep_dive_20260305.json
    EVAL_JUDGE_MODEL=claude-opus-4-20250514 python tests/eval/judge.py
"""

import argparse
import asyncio
import base64
import json
import os
from pathlib import Path

from anthropic import AsyncAnthropic

from tests.eval.rubrics import (
    JUDGE_SYSTEM_PROMPT,
    build_chart_judge_prompt,
    build_judge_prompt,
    parse_judge_response,
)

RESULTS_DIR = Path(__file__).parent / "results"
SCENARIOS_DIR = Path(__file__).parent / "scenarios"

DEFAULT_MODEL = "claude-sonnet-4-20250514"


def get_judge_model() -> str:
    """Get the judge model from env or default."""
    return os.environ.get("EVAL_JUDGE_MODEL", DEFAULT_MODEL)


async def judge_turn_text(
    client: AsyncAnthropic,
    model: str,
    turn: dict,
    prior_turns: list[dict],
    scenario_turn: dict,
    ground_truth: dict | None,
) -> dict:
    """Judge a single turn on text dimensions (factual, quality, coherence, error handling).

    Args:
        client: Anthropic async client
        model: Model to use for judging
        turn: Collected turn data with response_message, response_data, chart_spec
        prior_turns: List of prior turns for conversation context
        scenario_turn: The scenario YAML turn definition with expected checks
        ground_truth: Optional ground truth data

    Returns:
        Dict with scores per dimension and check results
    """
    checks = scenario_turn.get("expect", {}).get("checks", [])

    prompt = build_judge_prompt(
        turn=turn,
        prior_turns=prior_turns,
        ground_truth=ground_truth,
        checks=checks,
    )

    response = await client.messages.create(
        model=model,
        max_tokens=2000,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.content[0].text
    return parse_judge_response(response_text)


async def judge_turn_chart(
    client: AsyncAnthropic,
    model: str,
    turn: dict,
    scenario_turn: dict,
) -> dict:
    """Judge a chart using vision (screenshot + chart spec).

    Args:
        client: Anthropic async client
        model: Model to use
        turn: Collected turn with screenshot_chart path and chart_spec
        scenario_turn: Scenario YAML turn definition

    Returns:
        Dict with chart_quality score and reasoning
    """
    screenshot_path = turn.get("screenshot_chart")
    if not screenshot_path or not Path(screenshot_path).exists():
        return {"chart_quality": {"score": 0, "reasoning": "No chart screenshot available"}}

    # Read and encode screenshot
    image_data = Path(screenshot_path).read_bytes()
    b64_image = base64.standard_b64encode(image_data).decode("utf-8")

    prompt_text = build_chart_judge_prompt(turn)

    response = await client.messages.create(
        model=model,
        max_tokens=1000,
        system="You are an expert chart evaluator. Respond with JSON only.",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt_text,
                    },
                ],
            }
        ],
    )

    response_text = response.content[0].text
    parsed = parse_judge_response(response_text)

    # Extract just the chart_quality dimension
    if "chart_quality" in parsed:
        return {"chart_quality": parsed["chart_quality"]}

    # If judge returned scores in a different format, try to extract
    for key in parsed:
        if isinstance(parsed[key], dict) and "score" in parsed[key]:
            return {"chart_quality": parsed[key]}

    return {"chart_quality": {"score": 0, "reasoning": "Failed to parse chart score"}}


async def judge_transcript(
    client: AsyncAnthropic,
    model: str,
    transcript: dict,
    scenario: dict,
) -> dict:
    """Judge an entire transcript (all turns).

    Args:
        client: Anthropic async client
        model: Model to use
        transcript: Collected transcript dict
        scenario: Parsed YAML scenario dict

    Returns:
        Full scores dict with per-turn results and metadata
    """
    scores = {
        "scenario_name": transcript["scenario_name"],
        "scenario_file": transcript.get("scenario_file", ""),
        "judge_model": model,
        "timestamp": transcript.get("timestamp", ""),
        "turns": [],
    }

    prior_turns = []

    for turn_idx, turn in enumerate(transcript["turns"]):
        scenario_turn = scenario["turns"][turn_idx] if turn_idx < len(scenario["turns"]) else {}

        print(f"  Judging turn {turn_idx + 1}/{len(transcript['turns'])}...")

        # Judge text dimensions
        text_scores = await judge_turn_text(
            client, model, turn, prior_turns, scenario_turn, turn.get("ground_truth"),
        )

        # Judge chart if present
        chart_scores = {}
        if turn.get("has_chart") and turn.get("screenshot_chart"):
            chart_scores = await judge_turn_chart(client, model, turn, scenario_turn)

        # Combine scores
        turn_scores = {
            "turn_index": turn.get("turn_index", turn_idx + 1),
            "query": turn.get("query", ""),
            "latency_seconds": turn.get("latency_seconds", 0),
            "has_table": turn.get("has_table", False),
            "has_chart": turn.get("has_chart", False),
            "screenshot_chart": turn.get("screenshot_chart"),
            "screenshot_table": turn.get("screenshot_table"),
            **text_scores,
            **chart_scores,
        }

        scores["turns"].append(turn_scores)

        # Add to prior turns for next iteration's context
        prior_turns.append({
            "query": turn.get("query", ""),
            "response_message": turn.get("response_message", ""),
        })

        # Log progress
        fc = text_scores.get("factual_correctness", {}).get("score", "?")
        rq = text_scores.get("response_quality", {}).get("score", "?")
        cc = text_scores.get("conversation_coherence", {}).get("score", "?")
        cq = chart_scores.get("chart_quality", {}).get("score", "-")
        print(f"    Scores: factual={fc}, quality={rq}, coherence={cc}, chart={cq}")

    return scores


def find_transcripts(transcript_name: str | None = None) -> list[Path]:
    """Find transcript files to judge."""
    transcripts_dir = RESULTS_DIR / "transcripts"
    if not transcripts_dir.exists():
        return []

    if transcript_name:
        # Exact filename or partial match
        exact = transcripts_dir / transcript_name
        if exact.exists():
            return [exact]
        matches = list(transcripts_dir.glob(f"*{transcript_name}*"))
        return sorted(matches)

    # All transcripts
    return sorted(transcripts_dir.glob("*.json"))


def load_scenario_for_transcript(transcript: dict) -> dict | None:
    """Load the matching scenario YAML for a transcript."""
    scenario_file = transcript.get("scenario_file", "")
    if scenario_file:
        path = SCENARIOS_DIR / f"{scenario_file}.yaml"
        if path.exists():
            import yaml
            return yaml.safe_load(path.read_text())

    # Try matching by name
    scenario_name = transcript.get("scenario_name", "")
    slug = scenario_name.lower().replace(" ", "_").replace("-", "_")
    path = SCENARIOS_DIR / f"{slug}.yaml"
    if path.exists():
        import yaml
        return yaml.safe_load(path.read_text())

    return None


def save_scores(all_scores: list[dict]) -> Path:
    """Save all scores to results/scores.json."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / "scores.json"
    path.write_text(json.dumps(all_scores, indent=2, default=str))
    print(f"Scores saved: {path}")
    return path


async def main():
    parser = argparse.ArgumentParser(description="Eval judge phase")
    parser.add_argument(
        "--transcript",
        default=None,
        help="Specific transcript filename to judge (default: all)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Judge model (default: {DEFAULT_MODEL}, or EVAL_JUDGE_MODEL env)",
    )
    args = parser.parse_args()

    model = args.model or get_judge_model()
    print(f"Judge model: {model}")

    transcript_paths = find_transcripts(args.transcript)
    if not transcript_paths:
        print("No transcripts found. Run collect.py first.")
        return

    print(f"Found {len(transcript_paths)} transcript(s)")

    client = AsyncAnthropic()
    all_scores = []

    for path in transcript_paths:
        print(f"\n{'='*60}")
        print(f"Judging: {path.name}")
        print(f"{'='*60}")

        transcript = json.loads(path.read_text())
        scenario = load_scenario_for_transcript(transcript)

        if not scenario:
            print(f"  WARNING: No matching scenario found, skipping")
            continue

        scores = await judge_transcript(client, model, transcript, scenario)
        all_scores.append(scores)

    save_scores(all_scores)
    print(f"\nJudging complete. {len(all_scores)} scenario(s) scored.")


if __name__ == "__main__":
    asyncio.run(main())
