"""Tests for workspace and conversation API request/response models."""
from backend.api.models import (
    ConversationCreateRequest, ConversationUpdateRequest,
    WorkspaceCreateRequest, WorkspaceUpdateRequest,
)

def test_workspace_create_defaults():
    req = WorkspaceCreateRequest(name="Test Co")
    assert req.agent_type == "tally"
    assert req.config == {}

def test_workspace_create_with_config():
    req = WorkspaceCreateRequest(name="Test Co", config={"tally_host": "192.168.1.5", "tally_port": 9000})
    assert req.config["tally_host"] == "192.168.1.5"

def test_workspace_update_partial():
    req = WorkspaceUpdateRequest(name="New Name")
    assert req.name == "New Name"
    assert req.config is None
    assert req.memory is None

def test_conversation_create_defaults():
    req = ConversationCreateRequest()
    assert req.title is None
    assert req.tag is None

def test_conversation_update_partial():
    req = ConversationUpdateRequest(title="Sales Analysis")
    assert req.title == "Sales Analysis"
    assert req.tag is None
