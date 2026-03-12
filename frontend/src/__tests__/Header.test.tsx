import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Header from "../components/Header";
import { SessionProvider } from "../context/SessionContext";
import * as api from "../api/client";

vi.mock("../api/client");
const mockedApi = vi.mocked(api);

function renderWithProvider() {
  return render(
    <SessionProvider>
      <Header />
    </SessionProvider>
  );
}

describe("Header", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetAllMocks();
    mockedApi.getCompanies.mockResolvedValue({ companies: [] });
    mockedApi.getTallyMode.mockResolvedValue({ mode: "live" });
    mockedApi.setTallyMode.mockResolvedValue({ mode: "mock" });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders app title", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: null,
    });
    await act(async () => {
      renderWithProvider();
    });
    expect(screen.getByText("TallyPrime AI")).toBeInTheDocument();
  });

  it("shows green indicator when Tally is connected", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: null,
    });
    await act(async () => {
      renderWithProvider();
    });
    const indicator = screen.getByTestId("tally-mode-indicator");
    expect(indicator.className).toContain("bg-green-500");
  });

  it("shows red indicator when Tally is disconnected", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: false, tally_url: "http://localhost:9000", mode: null,
    });
    await act(async () => {
      renderWithProvider();
    });
    const indicator = screen.getByTestId("tally-mode-indicator");
    expect(indicator.className).toContain("bg-red-500");
  });

  it("shows gray indicator initially (checking state)", () => {
    mockedApi.getHealth.mockReturnValue(new Promise(() => {}));
    mockedApi.getTallyMode.mockReturnValue(new Promise(() => {}));
    renderWithProvider();
    const indicator = screen.getByTestId("tally-mode-indicator");
    expect(indicator.className).toContain("bg-gray-300");
  });

  it("shows red indicator on health check failure", async () => {
    mockedApi.getHealth.mockRejectedValue(new Error("Network"));
    await act(async () => {
      renderWithProvider();
    });
    const indicator = screen.getByTestId("tally-mode-indicator");
    expect(indicator.className).toContain("bg-red-500");
  });

  it("polls health every 30 seconds", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: null,
    });
    await act(async () => {
      renderWithProvider();
    });
    expect(mockedApi.getHealth).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(30000);
    });
    expect(mockedApi.getHealth).toHaveBeenCalledTimes(2);

    await act(async () => {
      vi.advanceTimersByTime(30000);
    });
    expect(mockedApi.getHealth).toHaveBeenCalledTimes(3);
  });

  it("shows Tally label in live mode", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: null,
    });
    await act(async () => {
      renderWithProvider();
    });
    expect(screen.getByTestId("tally-mode-label")).toHaveTextContent("Tally");
  });

  it("shows Mock Tally label after toggle", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: null,
    });
    vi.useRealTimers();
    const user = userEvent.setup();
    await act(async () => {
      renderWithProvider();
    });
    await user.click(screen.getByTestId("tally-mode-toggle"));
    expect(screen.getByTestId("tally-mode-label")).toHaveTextContent("Mock Tally");
    vi.useFakeTimers();
  });

  it("calls setTallyMode API on toggle click", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: null,
    });
    vi.useRealTimers();
    const user = userEvent.setup();
    await act(async () => {
      renderWithProvider();
    });
    await user.click(screen.getByTestId("tally-mode-toggle"));
    expect(mockedApi.setTallyMode).toHaveBeenCalledWith("mock");
    vi.useFakeTimers();
  });

  it("has correct data-testid attributes", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: null,
    });
    await act(async () => {
      renderWithProvider();
    });
    expect(screen.getByTestId("tally-mode-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("tally-mode-indicator")).toBeInTheDocument();
    expect(screen.getByTestId("tally-mode-label")).toBeInTheDocument();
  });

  it("reconciles mode on toggle error", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: null,
    });
    vi.useRealTimers();
    mockedApi.setTallyMode.mockRejectedValue(new Error("fail"));
    const user = userEvent.setup();
    await act(async () => {
      renderWithProvider();
    });
    await user.click(screen.getByTestId("tally-mode-toggle"));
    expect(mockedApi.getTallyMode).toHaveBeenCalled();
    vi.useFakeTimers();
  });
});
