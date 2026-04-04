"""Request and response models for the FastAPI endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, field_validator


class ChatRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v
    session_id: str | None = None
    company: str | None = None
    workspace_id: str | None = None
    conversation_id: str | None = None


class ChartSpec(BaseModel):
    chart_type: str
    title: str
    data: list[dict[str, Any]]
    config: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    message: str
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    chart: ChartSpec | None = None
    session_id: str


class HealthResponse(BaseModel):
    status: str
    tally_connected: bool
    tally_url: str
    mode: str | None = None


class CompanyItem(BaseModel):
    name: str


class CompaniesResponse(BaseModel):
    companies: list[CompanyItem]


class ReportResponse(BaseModel):
    headers: list[str]
    rows: list[list[Any]]


class TallyModeRequest(BaseModel):
    mode: Literal["mock", "live"]


class TallyModeResponse(BaseModel):
    mode: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


# --- Auth models (Set A1) ---

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.lower().strip()


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.lower().strip()


class AuthResponse(BaseModel):
    user: dict[str, Any]
    access_token: str


class TokenResponse(BaseModel):
    access_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: str


# --- Workspace models (Set A1) ---

class WorkspaceCreateRequest(BaseModel):
    name: str
    agent_type: str = "tally"
    config: dict[str, Any] = {}

class WorkspaceUpdateRequest(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    memory: dict[str, Any] | None = None

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    agent_type: str
    config: dict[str, Any]
    memory: dict[str, Any]
    created_at: str
    updated_at: str

# --- Conversation models (Set A1) ---

class ConversationCreateRequest(BaseModel):
    title: str | None = None
    tag: str | None = None

class ConversationUpdateRequest(BaseModel):
    title: str | None = None
    tag: str | None = None

class ConversationSummaryResponse(BaseModel):
    id: str
    title: str | None
    tag: str | None
    created_at: str
    updated_at: str

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    chart: dict[str, Any] | None = None
    created_at: str

class ConversationDetailResponse(BaseModel):
    id: str
    title: str | None
    tag: str | None
    messages: list[MessageResponse]
