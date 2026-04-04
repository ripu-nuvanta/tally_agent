"""Base agent interface — all registered agents must implement this."""
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    @abstractmethod
    async def process_query(
        self,
        message: str,
        workspace_config: dict[str, Any],
        workspace_memory: dict[str, Any],
        conversation_messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Process a user query and return a response.

        Args:
            message: The user's query text.
            workspace_config: Workspace-wide configuration.
            workspace_memory: Workspace-wide state/memory.
            conversation_messages: Chat history.
            **kwargs: Additional agent-specific parameters.

        Returns:
            A response dictionary with keys like 'text', 'table', 'chart', etc.
        """
        ...
