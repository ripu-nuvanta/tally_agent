"""Tests for API request/response models."""

from backend.api.models import (
    ChatRequest,
    ChatResponse,
    ChartSpec,
    ErrorResponse,
    HealthResponse,
    CompaniesResponse,
    CompanyItem,
    ReportResponse,
)


def test_chat_request_minimal():
    req = ChatRequest(message="What is my sales total?")
    assert req.message == "What is my sales total?"
    assert req.session_id is None
    assert req.company is None


def test_chat_request_full():
    req = ChatRequest(message="Hello", session_id="abc-123", company="Test Co")
    assert req.session_id == "abc-123"
    assert req.company == "Test Co"


def test_chat_response_minimal():
    resp = ChatResponse(message="Your sales are ₹10,000", session_id="abc")
    assert resp.data is None
    assert resp.chart is None


def test_chat_response_with_chart():
    chart = ChartSpec(
        chart_type="bar",
        title="Sales",
        data=[{"name": "Q1", "value": 100}],
    )
    resp = ChatResponse(message="Here's a chart", chart=chart, session_id="abc")
    assert resp.chart.chart_type == "bar"
    assert resp.chart.config is None


def test_health_response():
    resp = HealthResponse(status="healthy", tally_connected=True, tally_url="http://localhost:9000")
    assert resp.tally_connected is True


def test_companies_response():
    resp = CompaniesResponse(companies=[CompanyItem(name="Test Co")])
    assert len(resp.companies) == 1


def test_report_response():
    resp = ReportResponse(
        headers=["Account", "Debit", "Credit"],
        rows=[["Cash", 1000, 0]],
    )
    assert len(resp.headers) == 3
    assert len(resp.rows) == 1


def test_error_response():
    resp = ErrorResponse(error="Tally unreachable")
    assert resp.detail is None
