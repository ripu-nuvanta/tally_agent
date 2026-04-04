import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import ProtectedRoute from "../components/ProtectedRoute";
import type { AuthUser } from "../types";

interface MockAuthState {
  user: AuthUser | null;
  loading: boolean;
}

let mockAuthState: MockAuthState = { user: null, loading: false };

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    ...mockAuthState,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

function renderProtectedRoute(children: React.ReactNode = <div>Protected Content</div>) {
  return render(
    <MemoryRouter initialEntries={["/protected"]}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route
          path="/protected"
          element={<ProtectedRoute>{children}</ProtectedRoute>}
        />
      </Routes>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  it("shows loading state when auth is loading", () => {
    mockAuthState = { user: null, loading: true };
    renderProtectedRoute();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("redirects to /login when user is null", () => {
    mockAuthState = { user: null, loading: false };
    renderProtectedRoute();
    expect(screen.getByText("Login Page")).toBeInTheDocument();
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  it("renders children when user is authenticated", () => {
    mockAuthState = {
      user: { id: "user-1", email: "test@example.com", name: "Test User" },
      loading: false,
    };
    renderProtectedRoute();
    expect(screen.getByText("Protected Content")).toBeInTheDocument();
    expect(screen.queryByText("Login Page")).not.toBeInTheDocument();
  });

  it("renders custom children when authenticated", () => {
    mockAuthState = {
      user: { id: "user-1", email: "test@example.com", name: "Test User" },
      loading: false,
    };
    renderProtectedRoute(<span>Dashboard</span>);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("does not render children while loading", () => {
    mockAuthState = { user: null, loading: true };
    renderProtectedRoute();
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });
});
