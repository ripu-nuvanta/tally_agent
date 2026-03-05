import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
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
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders app title", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000",
    });
    await act(async () => {
      renderWithProvider();
    });
    expect(screen.getByText("TallyPrime AI")).toBeInTheDocument();
  });

  it("shows green dot when Tally is connected", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000",
    });
    await act(async () => {
      renderWithProvider();
    });
    expect(screen.getByTitle("Tally connected")).toBeInTheDocument();
  });

  it("shows red dot when Tally is disconnected", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: false, tally_url: "http://localhost:9000",
    });
    await act(async () => {
      renderWithProvider();
    });
    expect(screen.getByTitle("Tally disconnected")).toBeInTheDocument();
  });

  it("shows gray dot initially (checking state)", () => {
    mockedApi.getHealth.mockReturnValue(new Promise(() => {}));
    renderWithProvider();
    expect(screen.getByTitle("Checking Tally connection...")).toBeInTheDocument();
  });

  it("shows red dot on health check failure", async () => {
    mockedApi.getHealth.mockRejectedValue(new Error("Network"));
    await act(async () => {
      renderWithProvider();
    });
    expect(screen.getByTitle("Tally disconnected")).toBeInTheDocument();
  });

  it("polls health every 30 seconds", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok", tally_connected: true, tally_url: "http://localhost:9000",
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
});
