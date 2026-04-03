"""Agent type registry — maps agent_type strings to agent implementations."""
from backend.agents.base import BaseAgent

agent_registry: dict[str, type[BaseAgent]] = {}


def get_agent(agent_type: str) -> type[BaseAgent]:
    """Retrieve an agent class by type name.

    Args:
        agent_type: The name of the agent type (e.g. 'tally').

    Returns:
        The agent class.

    Raises:
        ValueError: If the agent type is not registered.
    """
    if agent_type not in agent_registry:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return agent_registry[agent_type]


def _register_agents() -> None:
    """Register all available agents."""
    from backend.agents.orchestrator import Orchestrator

    agent_registry["tally"] = Orchestrator


_register_agents()
