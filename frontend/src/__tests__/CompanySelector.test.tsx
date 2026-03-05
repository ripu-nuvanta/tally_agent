import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CompanySelector from "../components/CompanySelector";
import { SessionProvider } from "../context/SessionContext";
import * as api from "../api/client";

vi.mock("../api/client");
const mockedApi = vi.mocked(api);

function renderWithProvider() {
  return render(
    <SessionProvider>
      <CompanySelector />
    </SessionProvider>
  );
}

describe("CompanySelector", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders nothing when no companies are returned", async () => {
    mockedApi.getCompanies.mockResolvedValue({ companies: [] });
    const { container } = renderWithProvider();
    await waitFor(() => expect(mockedApi.getCompanies).toHaveBeenCalled());
    expect(container.querySelector("select")).toBeNull();
  });

  it("renders company dropdown when companies are available", async () => {
    mockedApi.getCompanies.mockResolvedValue({
      companies: [{ name: "Bharat Traders" }, { name: "Nuvanta AI" }],
    });
    renderWithProvider();
    await waitFor(() => {
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });
    expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
    expect(screen.getByText("Nuvanta AI")).toBeInTheDocument();
  });

  it("auto-selects the first company", async () => {
    mockedApi.getCompanies.mockResolvedValue({
      companies: [{ name: "Bharat Traders" }],
    });
    renderWithProvider();
    await waitFor(() => {
      expect(screen.getByRole("combobox")).toHaveValue("Bharat Traders");
    });
  });

  it("handles API error gracefully", async () => {
    mockedApi.getCompanies.mockRejectedValue(new Error("Network error"));
    const { container } = renderWithProvider();
    await waitFor(() => expect(mockedApi.getCompanies).toHaveBeenCalled());
    expect(container.querySelector("select")).toBeNull();
  });

  it("allows changing company via dropdown", async () => {
    const user = userEvent.setup();
    mockedApi.getCompanies.mockResolvedValue({
      companies: [{ name: "Bharat Traders" }, { name: "Nuvanta AI" }],
    });
    renderWithProvider();
    await waitFor(() => {
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });
    await user.selectOptions(screen.getByRole("combobox"), "Nuvanta AI");
    expect(screen.getByRole("combobox")).toHaveValue("Nuvanta AI");
  });
});
