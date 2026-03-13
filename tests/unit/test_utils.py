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


from backend.agents.utils import find_custom_tool_use_blocks


class TestFindCustomToolUseBlocks:
    def test_returns_only_tool_use_not_server_tool_use(self):
        custom = MagicMock(type="tool_use", name="get_trial_balance")
        server = MagicMock(type="server_tool_use", name="code_execution")
        text = MagicMock(type="text")
        response = MagicMock()
        response.content = [text, custom, server]
        assert find_custom_tool_use_blocks(response) == [custom]

    def test_returns_empty_when_only_server_tool_use(self):
        server = MagicMock(type="server_tool_use")
        code_result = MagicMock(type="code_execution_tool_result")
        response = MagicMock()
        response.content = [server, code_result]
        assert find_custom_tool_use_blocks(response) == []

    def test_returns_all_custom_tool_use_blocks(self):
        b1 = MagicMock(type="tool_use")
        b2 = MagicMock(type="tool_use")
        response = MagicMock()
        response.content = [b1, b2]
        assert find_custom_tool_use_blocks(response) == [b1, b2]


from backend.agents.utils import extract_code_execution_results


class TestExtractCodeExecutionResults:
    def test_extracts_server_tool_use_code(self):
        block = MagicMock(type="server_tool_use")
        block.input = {"code": "print(1+1)"}
        response = MagicMock()
        response.content = [block]
        results = extract_code_execution_results(response)
        assert len(results) == 1
        assert results[0] == {"type": "code_written", "code": "print(1+1)"}

    def test_extracts_code_execution_result(self):
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = "2\n"
        block.stderr = ""
        block.return_code = 0
        response = MagicMock()
        response.content = [block]
        results = extract_code_execution_results(response)
        assert len(results) == 1
        assert results[0]["type"] == "code_result"
        assert results[0]["stdout"] == "2\n"
        assert results[0]["return_code"] == 0

    def test_handles_pydantic_model_input(self):
        block = MagicMock(type="server_tool_use")
        block.input = MagicMock(spec=[])
        block.input.code = "x = 42"
        response = MagicMock()
        response.content = [block]
        results = extract_code_execution_results(response)
        assert results[0]["code"] == "x = 42"

    def test_skips_non_code_execution_blocks(self):
        text = MagicMock(type="text")
        tool = MagicMock(type="tool_use")
        response = MagicMock()
        response.content = [text, tool]
        assert extract_code_execution_results(response) == []

    def test_mixed_blocks(self):
        server = MagicMock(type="server_tool_use")
        server.input = {"code": "print('hi')"}
        result = MagicMock(type="code_execution_tool_result")
        result.stdout = "hi\n"
        result.stderr = ""
        result.return_code = 0
        text = MagicMock(type="text")
        response = MagicMock()
        response.content = [text, server, result]
        results = extract_code_execution_results(response)
        assert len(results) == 2
        assert results[0]["type"] == "code_written"
        assert results[1]["type"] == "code_result"


from backend.agents.utils import extract_structured_from_code_execution


class TestExtractStructuredFromCodeExecution:
    def test_extracts_structured_result_from_last_line(self):
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = 'Debug info\nSome calc\nSTRUCTURED_RESULT:{"headers":["Item","Qty"],"rows":[["A",10],["B",20]]}\n'
        response = MagicMock()
        response.content = [block]
        result = extract_structured_from_code_execution(response)
        assert result == {"headers": ["Item", "Qty"], "rows": [["A", 10], ["B", 20]]}

    def test_returns_none_when_no_prefix(self):
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = "just some output\n"
        response = MagicMock()
        response.content = [block]
        assert extract_structured_from_code_execution(response) is None

    def test_returns_none_for_invalid_json(self):
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = "STRUCTURED_RESULT:{bad json\n"
        response = MagicMock()
        response.content = [block]
        assert extract_structured_from_code_execution(response) is None

    def test_returns_none_when_missing_headers_or_rows(self):
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = 'STRUCTURED_RESULT:{"only_headers":["A"]}\n'
        response = MagicMock()
        response.content = [block]
        assert extract_structured_from_code_execution(response) is None

    def test_returns_none_when_no_code_execution_blocks(self):
        response = MagicMock()
        response.content = [MagicMock(type="text"), MagicMock(type="tool_use")]
        assert extract_structured_from_code_execution(response) is None

    def test_returns_first_valid_structured_result(self):
        """When multiple STRUCTURED_RESULT lines exist, return the first valid one."""
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = 'STRUCTURED_RESULT:{"headers":["First"],"rows":[]}\nmore output\nSTRUCTURED_RESULT:{"headers":["Second"],"rows":[["x",1]]}\n'
        response = MagicMock()
        response.content = [block]
        result = extract_structured_from_code_execution(response)
        assert result["headers"] == ["First"]

    def test_empty_stdout(self):
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = ""
        response = MagicMock()
        response.content = [block]
        assert extract_structured_from_code_execution(response) is None
