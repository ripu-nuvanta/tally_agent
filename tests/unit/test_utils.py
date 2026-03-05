"""Unit tests for backend.agents.utils."""

from unittest.mock import MagicMock

from backend.agents.utils import find_tool_use_block, find_all_tool_use_blocks, extract_text


class TestFindToolUseBlock:
    def test_returns_first_tool_use_block(self):
        block = MagicMock()
        block.type = "tool_use"
        block.name = "get_trial_balance"
        text_block = MagicMock()
        text_block.type = "text"

        response = MagicMock()
        response.content = [text_block, block]

        result = find_tool_use_block(response)
        assert result is block

    def test_returns_none_when_no_tool_use_block(self):
        """Issue #10: must return None instead of raising ValueError."""
        text_block = MagicMock()
        text_block.type = "text"
        response = MagicMock()
        response.content = [text_block]

        result = find_tool_use_block(response)
        assert result is None

    def test_returns_none_for_empty_content(self):
        response = MagicMock()
        response.content = []
        assert find_tool_use_block(response) is None


class TestFindAllToolUseBlocks:
    def test_returns_all_tool_use_blocks(self):
        b1 = MagicMock(type="tool_use")
        b2 = MagicMock(type="text")
        b3 = MagicMock(type="tool_use")
        response = MagicMock()
        response.content = [b1, b2, b3]
        assert find_all_tool_use_blocks(response) == [b1, b3]

    def test_returns_empty_for_no_tool_use(self):
        response = MagicMock()
        response.content = [MagicMock(type="text")]
        assert find_all_tool_use_blocks(response) == []


class TestExtractText:
    def test_extracts_text_from_response(self):
        block = MagicMock()
        block.type = "text"
        block.text = "Hello world"
        response = MagicMock()
        response.content = [block]
        assert extract_text(response) == "Hello world"

    def test_returns_empty_when_no_text_block(self):
        block = MagicMock()
        block.type = "tool_use"
        response = MagicMock()
        response.content = [block]
        assert extract_text(response) == ""
