"""Model pricing and cost calculation for usage logging."""

PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-haiku-4-5-20251001": {"input": 0.80 / 1_000_000, "output": 4.00 / 1_000_000},
    "claude-opus-4-6": {"input": 15.00 / 1_000_000, "output": 75.00 / 1_000_000},
}


def compute_cost(agent_calls: list[dict]) -> float:
    """Compute total cost in USD for a list of agent API calls.

    Args:
        agent_calls: List of dicts with "model", "input_tokens", "output_tokens" keys.

    Returns:
        Total cost in USD. Returns 0.0 for unknown models or empty list.
    """
    total = 0.0
    for call in agent_calls:
        prices = PRICING.get(call.get("model", ""), {"input": 0, "output": 0})
        total += call.get("input_tokens", 0) * prices["input"]
        total += call.get("output_tokens", 0) * prices["output"]
    return total
