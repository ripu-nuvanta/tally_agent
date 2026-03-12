import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Header from "../components/Header";
import { SessionProvider } from "../context/SessionContext";
import * as api from "../api/client";

vi.mock("../api/client");
const mockedApi = vi.mocked(api);

const reloadMock = vi.fn();
Object.defineProperty(window, "location", {
  value: { ...window.location, reload: reloadMock },
  writable: true,
});

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
    const indicator = screen.getByTestId("tally-status-dot");
    expect(indicator.className).toContain("bg-green-500");
  });

  it("shows red indicator when Tally is disconnected", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: false, tally_url: "http://localhost:9000", mode: null,
    });
    await act(async () => {
      renderWithProvider();
    });
    const indicator = screen.getByTestId("tally-status-dot");
    expect(indicator.className).toContain("bg-red-500");
  });

  it("shows gray indicator initially (checking state)", () => {
    mockedApi.getHealth.mockReturnValue(new Promise(() => {}));
    mockedApi.getTallyMode.mockReturnValue(new Promise(() => {}));
    renderWithProvider();
    const indicator = screen.getByTestId("tally-status-dot");
    expect(indicator.className).toContain("bg-gray-300");
  });

  it("shows red indicator on health check failure", async () => {
    mockedApi.getHealth.mockRejectedValue(new Error("Network"));
    await act(async () => {
      renderWithProvider();
    });
    const indicator = screen.getByTestId("tally-status-dot");
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
    expect(screen.getByTestId("tally-status-label")).toHaveTextContent("Tally");
  });

  it("shows Demo label when in mock mode", async () => {
    mockedApi.getTallyMode.mockResolvedValue({ mode: "mock" });
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: "mock",
    });
    await act(async () => {
      renderWithProvider();
    });
    expect(screen.getByTestId("tally-status-label")).toHaveTextContent("Demo");
  });

  it("toggle checkbox calls setTallyMode then window.location.reload", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: null,
    });
    vi.useRealTimers();
    const user = userEvent.setup();
    await act(async () => {
      renderWithProvider();
    });
    await user.click(screen.getByTestId("demo-mode-checkbox"));
    expect(mockedApi.setTallyMode).toHaveBeenCalledWith("mock");
    expect(reloadMock).toHaveBeenCalled();
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
    await user.click(screen.getByTestId("demo-mode-toggle"));
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
    expect(screen.getByTestId("demo-mode-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("demo-mode-checkbox")).toBeInTheDocument();
    expect(screen.getByTestId("tally-status-indicator")).toBeInTheDocument();
    expect(screen.getByTestId("tally-status-dot")).toBeInTheDocument();
    expect(screen.getByTestId("tally-status-label")).toBeInTheDocument();
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
    await user.click(screen.getByTestId("demo-mode-toggle"));
    expect(mockedApi.getTallyMode).toHaveBeenCalled();
    expect(reloadMock).not.toHaveBeenCalled();
    vi.useFakeTimers();
  });

  it("status indicator is a span (not button), not clickable", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: null,
    });
    await act(async () => {
      renderWithProvider();
    });
    const indicator = screen.getByTestId("tally-status-indicator");
    expect(indicator.tagName).toBe("SPAN");
    // Should not have onClick handler — no button role
    expect(indicator.getAttribute("role")).toBeNull();
  });
});
