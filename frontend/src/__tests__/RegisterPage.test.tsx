import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import RegisterPage from "../pages/RegisterPage";

const mockRegister = vi.fn();
const mockNavigate = vi.fn();

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    register: mockRegister,
    user: null,
    loading: false,
    login: vi.fn(),
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

function renderRegisterPage() {
  return render(
    <MemoryRouter>
      <RegisterPage />
    </MemoryRouter>
  );
}

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders name, email, and password fields", () => {
    renderRegisterPage();
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("renders page title and subtitle", () => {
    renderRegisterPage();
    expect(screen.getByText("TallyPrime AI")).toBeInTheDocument();
    expect(screen.getByText("Create your account")).toBeInTheDocument();
  });

  it("has a link back to login page", () => {
    renderRegisterPage();
    const link = screen.getByRole("link", { name: "Sign in" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/login");
  });

  it("Create account button is disabled when password is weak", async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText("Password"), "weak");

    const button = screen.getByRole("button", { name: "Create account" });
    expect(button).toBeDisabled();
  });

  it("Create account button is disabled when password is fair (score 3)", async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    // Length >= 12, uppercase, lowercase = score 3 = Fair
    await user.type(screen.getByLabelText("Password"), "Abcdefghijkl");

    expect(screen.getByText(/Fair/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
  });

  it("Create account button is enabled when password is strong (score 5)", async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    // 12+ chars, uppercase, lowercase, digit, special = score 5 = Strong
    await user.type(screen.getByLabelText("Password"), "Abcdefgh1!gh");

    expect(screen.getByText(/Strong/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).not.toBeDisabled();
  });

  it("password strength indicator shows Weak for simple passwords", async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText("Password"), "abc");

    expect(screen.getByText(/Weak/)).toBeInTheDocument();
  });

  it("password strength indicator shows Good for 4-scoring passwords", async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    // 12+ chars, uppercase, lowercase, digit = score 4 = Good
    await user.type(screen.getByLabelText("Password"), "Abcdefghij1k");

    expect(screen.getByText(/Good/)).toBeInTheDocument();
  });

  it("strength indicator is not shown when password field is empty", () => {
    renderRegisterPage();
    expect(screen.queryByText(/Weak|Fair|Good|Strong/)).not.toBeInTheDocument();
  });

  it("navigates to / on successful registration", async () => {
    mockRegister.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText("Name"), "Test User");
    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.type(screen.getByLabelText("Password"), "Abcdefgh1!gh");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith({
        name: "Test User",
        email: "test@example.com",
        password: "Abcdefgh1!gh",
      });
      expect(mockNavigate).toHaveBeenCalledWith("/");
    });
  });

  it("shows error message on registration failure", async () => {
    const err = { response: { data: { detail: "Email already exists" } } };
    mockRegister.mockRejectedValue(err);
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText("Name"), "Test User");
    await user.type(screen.getByLabelText("Email"), "existing@example.com");
    await user.type(screen.getByLabelText("Password"), "Abcdefgh1!gh");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(screen.getByText("Email already exists")).toBeInTheDocument();
    });
  });

  it("shows joined error when detail is an array", async () => {
    const err = { response: { data: { detail: ["Password too short", "Needs uppercase"] } } };
    mockRegister.mockRejectedValue(err);
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText("Name"), "Test User");
    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.type(screen.getByLabelText("Password"), "Abcdefgh1!gh");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(screen.getByText("Password too short. Needs uppercase")).toBeInTheDocument();
    });
  });

  it("shows network error when no response object", async () => {
    mockRegister.mockRejectedValue(new Error("Network Error"));
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText("Name"), "Test User");
    await user.type(screen.getByLabelText("Email"), "test@example.com");
    await user.type(screen.getByLabelText("Password"), "Abcdefgh1!gh");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(screen.getByText("Network error. Please check your connection.")).toBeInTheDocument();
    });
  });
});
