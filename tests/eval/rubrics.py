"""LLM-as-a-judge scoring rubrics and prompt builders for eval framework."""

import json
import re
from typing import Any


# --- Judge System Prompt ---

JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for a TallyPrime AI accounting assistant.
You will be given a user query, the agent's response, and evaluation criteria.
Score each dimension on a 1-5 scale with specific reasoning.

You MUST respond with valid JSON only. No markdown, no extra text.
Use this exact format:
{
  "factual_correctness": {"score": <1-5>, "reasoning": "<why>"},
  "response_quality": {"score": <1-5>, "reasoning": "<why>"},
  "conversation_coherence": {"score": <1-5>, "reasoning": "<why>"},
  "error_handling": {"score": <1-5>, "reasoning": "<why>"},
  "checks_passed": ["<check text that passed>"],
  "checks_failed": ["<check text that failed>"],
  "issues_found": ["<description of any issues>"]
}"""


# --- Scoring Rubrics (1-5 scale) ---

FACTUAL_RUBRIC = {
    5: "All numbers, ledger names, and calculations are exactly correct. Matches ground truth perfectly. Totals row present and arithmetically correct.",
    4: "Minor rounding differences or formatting variations, but all key facts are correct. Totals row present.",
    3: "Most facts correct, but 1-2 significant errors in amounts or ledger names. Totals row may be missing.",
    2: "Multiple factual errors. Key totals wrong or ledgers misidentified. Missing totals row.",
    1: "Mostly incorrect. Made-up numbers or fundamentally wrong data.",
}

RESPONSE_QUALITY_RUBRIC = {
    5: "Clear, well-structured response. Indian currency formatting (₹12,34,567). Appropriate detail level. Professional tone.",
    4: "Good quality with minor formatting issues. Slightly verbose or terse but still useful.",
    3: "Adequate but could be improved. Missing formatting or unclear structure.",
    2: "Poor quality. Hard to understand, missing key information, or wrong formatting.",
    1: "Unusable response. Garbled, empty, or completely unhelpful.",
}

COHERENCE_RUBRIC = {
    5: "Perfectly maintains conversation context. References prior turns accurately. Builds on previous data.",
    4: "Good coherence with minor gaps. Mostly references prior context correctly.",
    3: "Some coherence issues. Occasionally ignores or contradicts prior turns.",
    2: "Poor coherence. Frequently ignores conversation history or contradicts itself.",
    1: "No coherence. Each response is independent of conversation context.",
}

ERROR_HANDLING_RUBRIC = {
    5: "Gracefully handles edge cases. Asks for clarification when needed. Never crashes or returns errors.",
    4: "Good error handling with minor gaps. Recovers from most edge cases.",
    3: "Adequate. Handles common cases but struggles with edge cases.",
    2: "Poor error handling. Crashes or returns unhelpful errors on edge cases.",
    1: "No error handling. Crashes on any unexpected input.",
}

TOTALS_VERIFICATION_INSTRUCTIONS = """\
## Data Table Completeness — Totals Verification
For comparison, ranking (top-N), and aggregation responses that include a data table:
- Verify a "Total" or "Grand Total" row exists in the data table (in response_data or response text).
- Verify the total is arithmetically correct (sum of individual numeric rows for each column).
- Compare the total against ground truth if available (e.g., trial balance totals, P&L totals).
- Penalize factual_accuracy score by 1 point if a totals row is missing from a table with 2+ data rows.
- Penalize factual_accuracy score by 1 point if a totals row is present but arithmetically wrong.
- If the response is a single aggregated number (not a multi-row table), totals verification does not apply.
"""

CHART_RUBRIC = {
    5: "Perfect chart: correct type, readable labels, proper axes, accurate data representation, appropriate colors.",
    4: "Good chart with minor issues: slight label overlap or suboptimal color choice.",
    3: "Adequate chart but notable issues: wrong chart type or hard-to-read labels.",
    2: "Poor chart: misleading visualization, missing labels, or wrong data plotted.",
    1: "Broken or missing chart when one was expected.",
}


def _should_verify_totals(turn: dict[str, Any], checks: list[str]) -> bool:
    """Return True if totals verification should be applied to this turn."""
    data = turn.get("response_data")
    if not data:
        return False
    # Need headers + 2+ data rows to verify totals
    rows = data.get("rows", [])
    if len(rows) < 2:
        return False
    # Check keywords in checks or query
    totals_keywords = {"ranked", "top", "comparison", "compare",
                       "aggregate", "breakdown", "category", "customer"}
    check_text = " ".join(checks).lower()
    query_text = turn.get("query", "").lower()
    combined = check_text + " " + query_text
    return any(kw in combined for kw in totals_keywords)


def _format_rubric(rubric: dict[int, str]) -> str:
    """Format a rubric dict into a readable string for the judge prompt."""
    return "\n".join(f"  {score}: {desc}" for score, desc in sorted(rubric.items(), reverse=True))


def build_judge_prompt(
    turn: dict[str, Any],
    prior_turns: list[dict[str, Any]],
    ground_truth: dict[str, Any] | None,
    checks: list[str],
) -> str:
    """Build the full judge prompt for evaluating a single turn (text dimensions).

    Args:
        turn: Current turn with keys: query, response_message, response_data, chart_spec
        prior_turns: List of prior turns for conversation context
        ground_truth: Optional ground truth data from golden fixtures
        checks: List of check strings from the scenario YAML
    """
    parts = []

    # Conversation context
    if prior_turns:
        parts.append("## Prior Conversation")
        for i, pt in enumerate(prior_turns):
            parts.append(f"Turn {i + 1}:")
            parts.append(f"  User: {pt.get('query', '')}")
            parts.append(f"  Agent: {pt.get('response_message', '')[:500]}")
        parts.append("")

    # Current turn
    parts.append("## Current Turn")
    parts.append(f"User Query: {turn.get('query', '')}")
    parts.append(f"Agent Response: {turn.get('response_message', '')}")

    if turn.get("response_data"):
        data_str = json.dumps(turn["response_data"], indent=2, default=str)
        # Truncate if very large
        if len(data_str) > 3000:
            data_str = data_str[:3000] + "\n... (truncated)"
        parts.append(f"\nData Table:\n{data_str}")

    if turn.get("chart_spec"):
        parts.append(f"\nChart Spec:\n{json.dumps(turn['chart_spec'], indent=2, default=str)}")

    # Ground truth
    if ground_truth:
        gt_str = json.dumps(ground_truth, indent=2, default=str)
        if len(gt_str) > 3000:
            gt_str = gt_str[:3000] + "\n... (truncated)"
        parts.append(f"\n## Ground Truth Data\n{gt_str}")

    # Checks to evaluate
    parts.append("\n## Checks to Evaluate")
    for check in checks:
        parts.append(f"- {check}")

    # Totals verification for comparison/top_n/aggregation turns
    if _should_verify_totals(turn, checks):
        parts.append(TOTALS_VERIFICATION_INSTRUCTIONS)

    # Rubrics
    parts.append("\n## Scoring Rubrics")
    parts.append(f"\nFactual Correctness:\n{_format_rubric(FACTUAL_RUBRIC)}")
    parts.append(f"\nResponse Quality:\n{_format_rubric(RESPONSE_QUALITY_RUBRIC)}")
    parts.append(f"\nConversation Coherence:\n{_format_rubric(COHERENCE_RUBRIC)}")
    parts.append(f"\nError Handling:\n{_format_rubric(ERROR_HANDLING_RUBRIC)}")

    parts.append("\nScore each dimension 1-5 with reasoning. Evaluate each check as passed or failed.")
    parts.append("Respond with JSON only.")

    return "\n".join(parts)


def build_chart_judge_prompt(turn: dict[str, Any]) -> str:
    """Build the judge prompt for visual chart evaluation.

    Args:
        turn: Current turn with keys: chart_spec, screenshot_chart
    """
    parts = []
    parts.append("## Chart Evaluation")
    parts.append("Evaluate the chart screenshot against the chart specification.")
    parts.append("")

    if turn.get("chart_spec"):
        parts.append(f"Chart Spec:\n{json.dumps(turn['chart_spec'], indent=2, default=str)}")
        parts.append("")

    parts.append(f"Scoring Rubric:\n{_format_rubric(CHART_RUBRIC)}")
    parts.append("")
    parts.append("Respond with JSON only:")
    parts.append('{"chart_quality": {"score": <1-5>, "reasoning": "<why>"}}')

    return "\n".join(parts)


def parse_judge_response(response_text: str) -> dict[str, Any]:
    """Parse the judge's JSON response, with fallback regex extraction.

    Args:
        response_text: Raw text response from the judge LLM

    Returns:
        Dict with score dimensions, each having 'score' and 'reasoning' keys.
        Also includes 'checks_passed', 'checks_failed', 'issues_found' lists.
    """
    # Try direct JSON parse first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown code block
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding any JSON object in the response
    brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", response_text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: extract individual scores with regex
    scores = {}
    dimensions = [
        "factual_correctness",
        "response_quality",
        "conversation_coherence",
        "error_handling",
        "chart_quality",
    ]
    for dim in dimensions:
        pattern = rf'"{dim}".*?"score".*?(\d)'
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            scores[dim] = {"score": int(match.group(1)), "reasoning": "Extracted via fallback regex"}

    if not scores:
        # Complete fallback — return zeros
        return {
            "factual_correctness": {"score": 0, "reasoning": "Failed to parse judge response"},
            "response_quality": {"score": 0, "reasoning": "Failed to parse judge response"},
            "conversation_coherence": {"score": 0, "reasoning": "Failed to parse judge response"},
            "error_handling": {"score": 0, "reasoning": "Failed to parse judge response"},
            "checks_passed": [],
            "checks_failed": [],
            "issues_found": ["Failed to parse judge response"],
            "_raw_response": response_text[:500],
        }

    # Fill missing keys
    scores.setdefault("checks_passed", [])
    scores.setdefault("checks_failed", [])
    scores.setdefault("issues_found", [])
    return scores
