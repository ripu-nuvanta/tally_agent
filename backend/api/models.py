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
    # The currently-pending voucher_review entry (last one not approved/discarded),
    # so a chat rate-override ("use rate 90") can recompute it before the query
    # agent runs. None for ordinary queries. See T5 (FX→INR conversion).
    pending_entry: dict[str, Any] | None = None


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


# --- Data Entry models (Set B1) ---

class VoucherReviewEntry(BaseModel):
    """A single voucher entry for review."""
    id: str
    voucher_type: str
    date: str
    vendor_name: str | None = None
    party_name: str | None = None       # canonical party (vendor or customer)
    amount: float
    debit_ledger: str
    credit_ledger: str
    narration: str
    gst_entries: list[dict[str, Any]] = []
    status: str = "draft"
    warnings: list[str] = []
    is_new_ledger: bool = False
    suggested_parent: str | None = None
    # Group B additions (Purchase / Sales / Debit Note / Credit Note)
    party_ledger: str | None = None
    is_party_ledger: bool = False
    bill_reference: str | None = None
    bill_type: str = "New Ref"
    against_invoice_options: list[dict[str, Any]] = []  # DN/CN reference dropdown
    party_vouchers: list[dict[str, Any]] = []           # raw party voucher lookup
    # FX fields (Slice A / Group B multi-currency)
    original_currency: str = "INR"
    original_amount: float | None = None
    fx_rate: float | None = None
    inr_amount: float | None = None


class VoucherReviewData(BaseModel):
    """Review card data sent as message.data for data entry flow."""
    type: Literal["voucher_review"] = "voucher_review"
    file_id: str | None = None
    entries: list[VoucherReviewEntry]
    available_ledgers: list[str] = []
    available_payment_ledgers: list[str] = []


class VoucherActionRequest(BaseModel):
    """Request body for /chat/voucher-action endpoint."""
    action: Literal["approve", "discard", "edit"]
    entry: dict[str, Any]
    company: str = ""
    session_id: str = ""
    workspace_id: str = ""
    conversation_id: str = ""
