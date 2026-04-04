"""Playwright DB-mode browser E2E test.

Requires:
- Backend running in DB mode: TALLY_MODE=mock python -m uvicorn backend.main:app --port 8000
- Frontend running: VITE_DB_MODE=true npm run dev (port 5173)
- Playwright browsers installed: npx playwright install chromium

Run: PYTHONPATH=. python -m pytest tests/e2e/test_db_playwright.py -v -s
"""

import os
import uuid

import pytest

# Skip if playwright not available or servers not running
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

pytestmark = [
    pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed"),
    pytest.mark.skipif(
        not os.environ.get("RUN_PLAYWRIGHT_DB_TESTS"),
        reason="RUN_PLAYWRIGHT_DB_TESTS not set",
    ),
]

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# Unique email per test run to avoid conflicts
_unique = uuid.uuid4().hex[:8]
TEST_EMAIL = f"pw-{_unique}@test.com"
TEST_PASSWORD = "Str0ng!Pass#99"
TEST_NAME = "Playwright User"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


class TestDBModePlaywright:
    """Full browser flow: register → connect company → chat → logout → login → persistence."""

    def test_01_redirects_to_login(self, page):
        """Unauthenticated user is redirected to /login."""
        page.goto(FRONTEND_URL)
        page.wait_for_url("**/login")
        assert "/login" in page.url
        assert page.get_by_role("heading", name="TallyPrime AI").is_visible()
        assert page.get_by_text("Sign in to your account").is_visible()

    def test_02_navigate_to_register(self, page):
        """Click Register link → navigates to /register."""
        page.get_by_role("link", name="Register").click()
        page.wait_for_url("**/register")
        assert "/register" in page.url
        assert page.get_by_text("Create your account").is_visible()

    def test_03_register_with_strong_password(self, page):
        """Fill in registration form and submit."""
        page.get_by_role("textbox", name="Name").fill(TEST_NAME)
        page.get_by_role("textbox", name="Email").fill(TEST_EMAIL)
        page.get_by_role("textbox", name="Password").fill(TEST_PASSWORD)

        # Password strength should show "Strong"
        assert page.get_by_text("Strong").is_visible()

        # Button should be enabled
        btn = page.get_by_role("button", name="Create account")
        assert btn.is_enabled()

        btn.click()

        # Should redirect to main app
        page.wait_for_url(f"{FRONTEND_URL}/")
        assert page.get_by_text(TEST_NAME).is_visible()

    def test_04_connect_company_with_demo_mode(self, page):
        """Connect a company with Demo Mode enabled."""
        page.get_by_role("button", name="+ Connect Company").click()

        # Fill modal
        page.get_by_role("textbox", name="Bharat Traders Pvt Ltd").fill("PW Test Co")
        # Toggle demo mode
        page.get_by_text("Demo Mode").click()
        assert page.get_by_text("Uses sample data").is_visible()

        page.get_by_role("button", name="Connect", exact=True).click()

        # Sidebar should now show the workspace
        page.wait_for_timeout(1000)
        assert page.get_by_text("PW Test Co").is_visible()

    def test_05_create_chat_and_send_message(self, page):
        """Create new chat and send a message."""
        page.get_by_role("button", name="+ New Chat").click()
        page.wait_for_url("**/c/**")

        # Type and send
        page.get_by_role("textbox", name="Ask about your Tally data...").fill(
            "Hi there, good morning!"
        )
        page.get_by_role("button", name="Send message").click()

        # Wait for greeting response (classifier call only, ~2-5s)
        page.wait_for_timeout(15000)

        # Should have the canned greeting response
        assert page.get_by_text("TallyPrime assistant").is_visible()

    def test_06_sidebar_shows_conversation_title(self, page):
        """Sidebar should show the auto-generated conversation title."""
        # The conversation title is auto-generated from the first message
        sidebar = page.locator("aside")
        assert sidebar.get_by_text("Hi there, good morning!").is_visible()

    def test_07_logout(self, page):
        """Sign out → redirected to login."""
        page.get_by_role("button", name=f"{TEST_NAME[0]} {TEST_NAME}").click()
        page.get_by_role("button", name="Sign out").click()
        page.wait_for_url("**/login")
        assert "/login" in page.url

    def test_08_login_and_verify_persistence(self, page):
        """Login again → workspace and conversation still exist."""
        page.get_by_role("textbox", name="Email").fill(TEST_EMAIL)
        page.get_by_role("textbox", name="Password").fill(TEST_PASSWORD)
        page.get_by_role("button", name="Sign in").click()

        # Should be back in the app
        page.wait_for_url(f"{FRONTEND_URL}/")

        # Wait for sidebar to load
        page.wait_for_timeout(2000)

        # Workspace should still exist
        assert page.get_by_text("PW Test Co").is_visible()

        # Conversation should still exist
        assert page.get_by_text("Hi there, good morning!").is_visible()

    def test_09_click_conversation_loads_history(self, page):
        """Click conversation in sidebar → chat history loads from DB."""
        page.get_by_role("button", name="Hi there, good morning!").click()
        page.wait_for_timeout(2000)

        # The user message should be visible in the chat area
        main = page.locator("main")
        assert main.get_by_text("Hi there, good morning!").is_visible()
