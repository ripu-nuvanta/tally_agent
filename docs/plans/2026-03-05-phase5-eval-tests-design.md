# Phase 5: Eval Tests — LLM-as-a-Judge Chat Session Evaluation

**Date:** 2026-03-05
**Status:** IMPLEMENTED

## Overview

Evaluation framework for assessing the TallyPrime AI Agent's response quality across multi-turn chat sessions. Uses a two-phase pipeline (collect → judge) with LLM-as-a-judge for scoring and Playwright for visual chart evaluation against the real frontend.

## Architecture: Two-Phase Pipeline

### Phase 1 — Collect
Run conversation scenarios against the real agent + real frontend via Playwright. Capture responses, screenshots, and timing. Produces reusable transcript artifacts.

### Phase 2 — Judge
Feed transcripts + screenshots + ground truth to an LLM judge. Score each turn across 4 dimensions + chart quality. Generate JSON scores and HTML dashboard report.

**Key benefit:** Can re-judge without re-running expensive conversations. Swap judge models or tweak rubrics cheaply.

## Directory Structure

```
tests/eval/
├── scenarios/                    # Conversation scenario definitions (YAML)
│   ├── financial_deep_dive.yaml
│   ├── cross_report_analysis.yaml
│   ├── edge_case_gauntlet.yaml
│   └── trends_and_breakdowns.yaml
├── golden/                       # Pre-recorded ground truth (JSON)
│   ├── financial_deep_dive.json
│   ├── cross_report_analysis.json
│   ├── edge_case_gauntlet.json
│   └── trends_and_breakdowns.json
├── collect.py                    # Phase 1: Run scenarios via Playwright + capture
├── judge.py                      # Phase 2: LLM-as-a-judge scoring
├── report.py                     # Generate HTML report from scores
├── rubrics.py                    # Scoring rubrics & judge prompts per dimension
├── conftest.py                   # Shared fixtures (client, browser, etc.)
└── results/                      # Output directory (gitignored)
    ├── transcripts/              # Raw session JSON per scenario run
    ├── screenshots/              # Playwright chart/table/fullpage screenshots
    ├── scores.json               # Judge output
    └── report.html               # Final HTML dashboard
```

## Scenario Definition Format (YAML)

```yaml
name: "Financial Report Deep-Dive"
description: "Start with trial balance, drill into ledgers, test negative balance handling"
tags: [negative_balances, drill_down, formatting]

turns:
  - query: "Show me the trial balance for FY 2025-26"
    expect:
      query_type: simple_lookup
      has_data: true
      has_chart: true
      chart_type: bar
      ground_truth_key: "trial_balance"
      checks:
        - "Response mentions debit and credit totals"
        - "Negative balances shown with minus sign"
        - "Indian rupee formatting used"

  - query: "Which ledgers have negative closing balance?"
    expect:
      query_type: top_n
      has_data: true
      checks:
        - "Lists ledgers with negative balances correctly"
        - "Explains what negative balance means in context"
```

- `checks`: Natural language assertions evaluated by the LLM judge (not regex)
- `ground_truth_key`: Maps to golden fixture for factual accuracy comparison
- `chart_type`: Single value or list of acceptable types

## Scenarios (4 scenarios, 27 turns)

### Scenario 1: Financial Report Deep-Dive (6 turns)
1. "Show me the trial balance for FY 2025-26" — baseline data fetch + chart
2. "Which ledgers have negative closing balance?" — negative balance handling
3. "What's the total of all expense ledgers?" — aggregation on prior data
4. "Compare the top 3 expense ledgers" — comparison + grouped bar chart
5. "Show me monthly trend for the largest expense" — trend + line chart, references prior context
6. "What percentage of total expenses does it represent?" — follow-up calculation, coherence

### Scenario 2: Cross-Report Analysis (6 turns)
1. "Show me the profit and loss statement" — P&L + chart
2. "Now show the balance sheet" — second report, new chart
3. "How do total liabilities compare to total assets?" — cross-report comparison
4. "Show receivables aging — who owes us the most?" — bills receivable + pie chart
5. "What are our top 5 sales by customer?" — top_n + bar chart
6. "Summarize the company's financial health" — open-ended synthesis

### Scenario 3: Edge Case Gauntlet (8 turns)
1. "Show me the balance" — ambiguous, should trigger clarification
2. "Trial balance for March 2025 to March 2026" — wrong date format
3. "What's the balance of Cash & Bank (Combined)?" — special characters in ledger name
4. "Show ledgers with zero balance" — zero/empty handling
5. "Compare sales of Q1 vs Q2 vs Q3 vs Q4" — 4-way comparison, complex chart
6. "Show me stock summary" — quantities not currency
7. "What was the sales amount for HCODE last month?" — specific ledger + date range
8. "Show everything" — maximally vague, tests error handling

### Scenario 4: Trends & Breakdowns (7 turns)
1. "Show me monthly cash flow for FY 2025-26" — line chart, positive/negative values
2. "Break down expenses by category for each month" — stacked bar chart
3. "What's the month-over-month growth in sales?" — trend with percentages, line chart
4. "Show quarterly revenue vs expenses" — grouped bar, two series over 4 quarters
5. "Which months had negative cash flow?" — filters from prior data, negative highlighting
6. "Show purchase breakdown by vendor — top 10" — bar/pie, label readability with many items
7. "Compare this quarter's expenses with last quarter — category-wise" — stacked/grouped bar

## Collection Phase (Phase 1)

**Prerequisites:** Backend on `localhost:8000`, frontend on `localhost:5173`.

```bash
python tests/eval/collect.py --scenario all --host 192.168.18.219 --port 9000
python tests/eval/collect.py --scenario financial_deep_dive  # single scenario
```

**Per scenario:**
1. Launch Playwright browser → navigate to real frontend (`http://localhost:5173`)
2. Select company via `CompanySelector`
3. For each turn:
   - Type query into `ChatInput`, submit
   - Wait for response (loading indicator disappears)
   - Extract response text, data table, chart spec from DOM
   - Screenshot chart container element (if chart rendered)
   - Screenshot data table (if table rendered)
   - Record: message, data, chart, query_type, latency, screenshot paths
   - If `clarification_needed`, auto-respond and retry (max 3 retries)
4. If `RUN_LIVE_TESTS=1`: also run direct Tally queries for ground truth
   - Otherwise: load from `golden/{scenario}.json`
5. Take full-page screenshot (conversation flow)
6. Save transcript to `results/transcripts/{scenario}_{timestamp}.json`

**Transcript format:**
```json
{
  "scenario": "financial_deep_dive",
  "timestamp": "2026-03-05T14:30:00",
  "source": "live|golden",
  "turns": [
    {
      "turn_idx": 0,
      "query": "Show me the trial balance for FY 2025-26",
      "response": { "query_type": "...", "message": "...", "data": {...}, "chart": {...} },
      "screenshot_chart": "screenshots/financial_deep_dive_turn0_chart.png",
      "screenshot_table": "screenshots/financial_deep_dive_turn0_table.png",
      "ground_truth": { "trial_balance": {...} },
      "latency_ms": 3200,
      "clarification_retries": 0
    }
  ]
}
```

## Judge Phase (Phase 2)

```bash
python tests/eval/judge.py                          # all transcripts
python tests/eval/judge.py --transcript financial_deep_dive_20260305.json
```

### Scoring Dimensions (1-5 scale)

| Dimension | Evaluates |
|-----------|-----------|
| **Factual Correctness** | Numbers match ground truth, correct sign convention, totals add up, correct ledger names |
| **Response Quality** | Proper accounting terminology, Indian formatting (₹, lakhs), clear structure, answers the question |
| **Conversation Coherence** | References prior context, no contradictions, handles follow-ups, maintains state |
| **Error Handling** | Graceful with ambiguity, clarifies when appropriate, doesn't hallucinate data |
| **Chart Quality** | (Visual, from screenshots) Readable labels, appropriate scale, correct chart type, data matches response, colors distinguishable |

### Judge Input Per Turn
- User query
- Agent response (message + data + chart spec)
- Ground truth (if available)
- Scenario `checks` list for that turn
- All prior turns (for coherence)
- Chart screenshot as image (for chart quality)

### Rubrics

```
Factual Correctness:
  5: All numbers exactly match ground truth, correct signs, proper totals
  4: Minor formatting differences but numbers correct
  3: Most numbers correct, 1-2 small discrepancies
  2: Multiple incorrect numbers or wrong sign convention
  1: Fundamentally wrong data or hallucinated numbers

Response Quality:
  5: Perfect accounting terminology, Indian formatting, clear and direct
  4: Good response with minor wording issues
  3: Adequate but missing formatting or unclear in places
  2: Poor structure or missing key information
  1: Incoherent or doesn't address the question

Conversation Coherence:
  5: Perfect context tracking, references prior data accurately
  4: Good coherence with minor missed references
  3: Partially tracks context, some disconnects
  2: Frequently loses context or contradicts prior turns
  1: No awareness of conversation history

Error Handling:
  5: Gracefully handles all edge cases, asks clarification when needed
  4: Handles most edge cases well
  3: Some edge cases handled, others missed
  2: Poor handling, crashes or returns wrong data on edge cases
  1: Fails completely on non-standard input

Chart Quality (visual):
  5: Perfect chart — readable labels, correct scale, appropriate type, data matches
  4: Minor cosmetic issues (slightly crowded) but correct
  3: Usable but has issues (wrong scale, truncated labels)
  2: Chart type inappropriate or data doesn't match response
  1: Unreadable or misleading
```

### Judge Output Per Turn
```json
{
  "turn_idx": 0,
  "scores": {
    "factual_correctness": { "score": 4, "reasoning": "..." },
    "response_quality": { "score": 5, "reasoning": "..." },
    "conversation_coherence": { "score": 5, "reasoning": "..." },
    "error_handling": { "score": 5, "reasoning": "..." },
    "chart_quality": { "score": 3, "reasoning": "Labels overlap on X-axis..." }
  },
  "checks_passed": ["Indian rupee formatting used"],
  "checks_failed": ["Negative balances shown with minus sign"],
  "issues_found": ["Closing balance computed as debit+credit (should be debit-credit)"]
}
```

**Judge model:** `claude-sonnet-4-20250514` (configurable via `EVAL_JUDGE_MODEL` env var). Uses vision for screenshot evaluation.

## HTML Report

Self-contained single HTML file with inline CSS/JS and base64-embedded screenshots.

**Sections:**
1. **Header** — timestamp, source (live/golden), judge model
2. **Overall Scores** — averages across all scenarios, bar visualization per dimension
3. **Per-Scenario Breakdown** — expandable, shows per-turn scores with screenshot thumbnails
4. **Issues Found** — aggregated and deduplicated, sorted by severity (red/yellow/green)

**Color coding:** Green (4-5), Yellow (3), Red (1-2).

## Ground Truth Strategy

Controlled by `RUN_LIVE_TESTS` env variable:
- **Set:** Collection phase also runs direct Tally queries via `TallyClient` for ground truth. Results saved alongside transcript.
- **Not set:** Loads pre-recorded golden fixtures from `tests/eval/golden/`. Fast and repeatable, no Tally needed.

Golden fixtures are generated once from a live run and committed to the repo.

## Known Issues to Validate

The eval framework should catch these known problems:
1. **Trial balance closing_balance = debit + credit** (should be debit - credit)
2. **Negative balances in charts** — pie uses `abs()` which hides sign information
3. **Stacked bar never triggered** — defined but no orchestrator path activates it
4. **Label overflow** on charts with many items (10+ ledgers)
5. **No ₹ symbol in chart tooltips** — only in table formatting
6. **Mixed positive/negative on same chart axis** — cash flow scenario

## Run Commands

```bash
# Phase 1: Collect (needs backend + frontend + Tally running)
python tests/eval/collect.py --scenario all --host <TALLY_IP> --port 9000

# Phase 1: Collect with live ground truth
RUN_LIVE_TESTS=1 python tests/eval/collect.py --scenario all --host <TALLY_IP> --port 9000

# Phase 2: Judge
ANTHROPIC_API_KEY=<key> python tests/eval/judge.py

# Phase 3: Report
python tests/eval/report.py
# → opens results/report.html
```
