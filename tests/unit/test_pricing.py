"""Tests for model pricing and cost calculation."""
from backend.utils.pricing import compute_cost, PRICING


def test_pricing_has_expected_models():
    assert "claude-sonnet-4-6" in PRICING
    assert "claude-haiku-4-5-20251001" in PRICING
    assert "claude-opus-4-6" in PRICING


def test_compute_cost_single_agent():
    calls = [{"model": "claude-sonnet-4-6", "input_tokens": 1_000_000, "output_tokens": 0}]
    cost = compute_cost(calls)
    assert abs(cost - 3.00) < 0.001


def test_compute_cost_multi_agent():
    calls = [
        {"model": "claude-haiku-4-5-20251001", "input_tokens": 800, "output_tokens": 50},
        {"model": "claude-sonnet-4-6", "input_tokens": 5000, "output_tokens": 1200},
    ]
    cost = compute_cost(calls)
    expected = 0.00084 + 0.033
    assert abs(cost - expected) < 0.0001


def test_compute_cost_unknown_model_uses_zero():
    calls = [{"model": "unknown-model", "input_tokens": 1000, "output_tokens": 500}]
    assert compute_cost(calls) == 0.0


def test_compute_cost_empty_list():
    assert compute_cost([]) == 0.0
