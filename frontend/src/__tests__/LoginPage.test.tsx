import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import LoginPage from "../pages/LoginPage";

const mockLogin = vi.fn();
const mockNavigate = vi.fn();

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    login: mockLogin,
    user: null,
    loading: false,
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderLoginPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders email and password fields and sign-in button", () => {
    renderLoginPage();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("renders page title and subtitle", () => {
    renderLoginPage();
    expect(screen.getByText("TallyPrime AI")).toBeInTheDocument();
    expect(screen.getByText("Sign in to your account")).toBeInTheDocument();
  });

  it("has a link to the register page", () => {
    renderLoginPage();
    const link = screen.getByRole("link", { name: "Register" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/register");
  });

  it("navigates to / on successful login", async () => {
    mockLogin.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.type(screen.getByLabelText("Password"), "mypassword");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({ email: "test@example.com", password: "mypassword" });
      expect(mockNavigate).toHaveBeenCalledWith("/");
    });
  });

  it("shows error message on failed login with detail", async () => {
    const err = { response: { data: { detail: "Invalid credentials" }, status: 401 } };
    mockLogin.mockRejectedValue(err);
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.type(screen.getByLabelText("Password"), "wrongpassword");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });
  });

  it("shows rate limit error on 429 response", async () => {
    const err = { response: { status: 429, data: {} } };
    mockLogin.mockRejectedValue(err);
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.type(screen.getByLabelText("Password"), "password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByText("Too many login attempts. Please try again later.")).toBeInTheDocument();
    });
  });

  it("shows network error when no response object", async () => {
    mockLogin.mockRejectedValue(new Error("Network Error"));
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.type(screen.getByLabelText("Password"), "password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByText("Network error. Please check your connection.")).toBeInTheDocument();
    });
  });

  it("shows loading state while submitting", async () => {
    let resolve: () => void;
    mockLogin.mockReturnValue(new Promise<void>((r) => { resolve = r; }));
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.type(screen.getByLabelText("Password"), "password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.getByRole("button", { name: "Signing in..." })).toBeDisabled();
    resolve!();
  });
});
