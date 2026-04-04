"""Tests for agent registry and base agent interface."""
import pytest
from backend.agents.base import BaseAgent
from backend.agents.registry import agent_registry, get_agent


def test_tally_agent_registered():
    assert "tally" in agent_registry


def test_get_agent_returns_tally():
    agent_class = get_agent("tally")
    assert agent_class is not None


def test_get_agent_unknown_raises():
    with pytest.raises(ValueError, match="Unknown agent type"):
        get_agent("nonexistent")


def test_base_agent_is_abstract():
    with pytest.raises(TypeError):
        BaseAgent()
