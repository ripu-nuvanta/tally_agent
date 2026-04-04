import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import UserMenu from "../components/UserMenu";
import type { AuthUser } from "../types";

const mockLogout = vi.fn();
const mockNavigate = vi.fn();

const mockUser: AuthUser = {
  id: "user-1",
  email: "test@example.com",
  name: "Test User",
};

interface MockAuthState {
  user: AuthUser | null;
}

let mockAuthState: MockAuthState = { user: mockUser };

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    ...mockAuthState,
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: mockLogout,
  }),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderUserMenu() {
  return render(
    <MemoryRouter>
      <UserMenu />
    </MemoryRouter>
  );
}

describe("UserMenu", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockAuthState = { user: mockUser };
  });

  it("renders user initial avatar button", () => {
    renderUserMenu();
    // Avatar shows first letter of name, uppercased
    expect(screen.getByText("T")).toBeInTheDocument();
  });

  it("renders nothing when user is null", () => {
    mockAuthState = { user: null };
    const { container } = renderUserMenu();
    expect(container.firstChild).toBeNull();
  });

  it("dropdown is not visible initially", () => {
    renderUserMenu();
    expect(screen.queryByText("test@example.com")).not.toBeInTheDocument();
  });

  it("opens dropdown when avatar button is clicked", async () => {
    const user = userEvent.setup();
    renderUserMenu();

    await user.click(screen.getByText("T"));

    expect(screen.getByText("test@example.com")).toBeInTheDocument();
  });

  it("shows user name in dropdown", async () => {
    const user = userEvent.setup();
    renderUserMenu();

    await user.click(screen.getByText("T"));

    // Name appears in the dropdown header (may also appear in button — use getAllByText)
    const nameElements = screen.getAllByText("Test User");
    expect(nameElements.length).toBeGreaterThanOrEqual(1);
  });

  it("shows user email in dropdown", async () => {
    const user = userEvent.setup();
    renderUserMenu();

    await user.click(screen.getByText("T"));

    expect(screen.getByText("test@example.com")).toBeInTheDocument();
  });

  it("shows Sign out button in dropdown", async () => {
    const user = userEvent.setup();
    renderUserMenu();

    await user.click(screen.getByText("T"));

    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("calls logout and navigates to /login when Sign out is clicked", async () => {
    mockLogout.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderUserMenu();

    // Open dropdown
    await user.click(screen.getByText("T"));
    // Click sign out
    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(mockLogout).toHaveBeenCalledTimes(1);
    expect(mockNavigate).toHaveBeenCalledWith("/login");
  });

  it("closes dropdown when clicking outside", async () => {
    const user = userEvent.setup();
    renderUserMenu();

    // Open dropdown
    await user.click(screen.getByText("T"));
    expect(screen.getByText("test@example.com")).toBeInTheDocument();

    // Click outside (on the document body)
    await user.click(document.body);

    expect(screen.queryByText("test@example.com")).not.toBeInTheDocument();
  });

  it("toggles dropdown closed on second click", async () => {
    const user = userEvent.setup();
    renderUserMenu();

    // Open
    await user.click(screen.getByText("T"));
    expect(screen.getByText("test@example.com")).toBeInTheDocument();

    // Close
    await user.click(screen.getByText("T"));
    expect(screen.queryByText("test@example.com")).not.toBeInTheDocument();
  });

  it("renders initial from user name uppercased", () => {
    mockAuthState = {
      user: { id: "user-2", email: "alice@example.com", name: "alice" },
    };
    renderUserMenu();
    expect(screen.getByText("A")).toBeInTheDocument();
  });
});
