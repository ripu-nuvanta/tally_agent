import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider, useAuth } from "../context/AuthContext";
import type { AuthUser } from "../types";

vi.mock("../api/client");

const mockedClient = vi.mocked(await import("../api/client"));

const mockUser: AuthUser = { id: "user-1", email: "test@example.com", name: "Test User" };

function TestConsumer() {
  const { user, loading, login, register, logout } = useAuth();
  return (
    <div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="user">{user ? user.email : "null"}</div>
      <button onClick={() => login({ email: "a@b.com", password: "pass" })}>Login</button>
      <button onClick={() => register({ email: "a@b.com", password: "pass", name: "A" })}>Register</button>
      <button onClick={() => logout()}>Logout</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <AuthProvider>
      <TestConsumer />
    </AuthProvider>
  );
}

describe("AuthContext / AuthProvider", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("throws when useAuth is used outside AuthProvider", () => {
    const originalError = console.error;
    console.error = vi.fn();
    expect(() => render(<TestConsumer />)).toThrow("useAuth must be used within AuthProvider");
    console.error = originalError;
  });

  it("starts with loading=true then resolves to loading=false when session restores", async () => {
    mockedClient.refreshToken.mockResolvedValue("new-token");
    mockedClient.getMe.mockResolvedValue(mockUser);

    renderWithProvider();

    // Eventually loading becomes false
    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });
  });

  it("sets user when session is restored successfully", async () => {
    mockedClient.refreshToken.mockResolvedValue("new-token");
    mockedClient.getMe.mockResolvedValue(mockUser);

    renderWithProvider();

    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe("test@example.com");
    });
  });

  it("leaves user null when session restore fails", async () => {
    mockedClient.refreshToken.mockRejectedValue(new Error("No session"));

    renderWithProvider();

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });
    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("sets user after successful login", async () => {
    mockedClient.refreshToken.mockRejectedValue(new Error("No session"));
    mockedClient.login.mockResolvedValue({ user: mockUser, access_token: "tok" });

    const user = userEvent.setup();
    renderWithProvider();

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));

    await user.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe("test@example.com");
    });
  });

  it("sets user after successful register", async () => {
    mockedClient.refreshToken.mockRejectedValue(new Error("No session"));
    mockedClient.register.mockResolvedValue({ user: mockUser, access_token: "tok" });

    const user = userEvent.setup();
    renderWithProvider();

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));

    await user.click(screen.getByRole("button", { name: "Register" }));

    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe("test@example.com");
    });
  });

  it("clears user after logout", async () => {
    mockedClient.refreshToken.mockResolvedValue("tok");
    mockedClient.getMe.mockResolvedValue(mockUser);
    mockedClient.logout.mockResolvedValue(undefined);

    const user = userEvent.setup();
    renderWithProvider();

    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe("test@example.com"));

    await user.click(screen.getByRole("button", { name: "Logout" }));

    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe("null");
    });
  });

  it("calls setAccessToken(null) when session restore fails", async () => {
    mockedClient.refreshToken.mockRejectedValue(new Error("No session"));

    renderWithProvider();

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));

    expect(mockedClient.setAccessToken).toHaveBeenCalledWith(null);
  });
});
