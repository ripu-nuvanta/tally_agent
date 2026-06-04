import { render, screen, act } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import TallyStatusBadge from "../components/TallyStatusBadge";
import { getHealth } from "../api/client";

vi.mock("../api/client", () => ({ getHealth: vi.fn() }));

describe("TallyStatusBadge", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); });

  it("shows Demo (no polling) for mock workspaces", () => {
    render(<TallyStatusBadge config={{ mock_mode: true }} />);
    expect(screen.getByTestId("header-workspace-badge")).toHaveTextContent("Demo");
    expect(getHealth).not.toHaveBeenCalled();
  });

  it("polls workspace host/port and shows Live when connected", async () => {
    vi.mocked(getHealth).mockResolvedValue({ status: "healthy", tally_connected: true, tally_url: "http://192.168.1.5:9000", mode: "live" });
    render(<TallyStatusBadge config={{ tally_host: "192.168.1.5", tally_port: 9000 }} />);
    expect(screen.getByTestId("header-workspace-badge")).toHaveAttribute("data-status", "checking");
    await act(async () => { await vi.runOnlyPendingTimersAsync(); });
    expect(getHealth).toHaveBeenCalledWith({ host: "192.168.1.5", port: 9000 });
    expect(screen.getByTestId("header-workspace-badge")).toHaveAttribute("data-status", "connected");
    expect(screen.getByTestId("header-workspace-badge")).toHaveTextContent("Live");
  });

  it("shows Offline when disconnected, then re-polls after 30s", async () => {
    vi.mocked(getHealth)
      .mockResolvedValueOnce({ status: "degraded", tally_connected: false, tally_url: "x", mode: "live" })
      .mockResolvedValueOnce({ status: "healthy", tally_connected: true, tally_url: "x", mode: "live" });
    render(<TallyStatusBadge config={{ tally_host: "h" }} />);
    // Flush only the initial check()'s microtask (not the 30s interval) so we
    // observe the first (disconnected) result before the re-poll fires.
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(screen.getByTestId("header-workspace-badge")).toHaveTextContent("Offline");
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(screen.getByTestId("header-workspace-badge")).toHaveTextContent("Live");
  });

  it("shows Offline when getHealth throws", async () => {
    vi.mocked(getHealth).mockRejectedValue(new Error("network"));
    render(<TallyStatusBadge config={{ tally_host: "h" }} />);
    await act(async () => { await vi.runOnlyPendingTimersAsync(); });
    expect(screen.getByTestId("header-workspace-badge")).toHaveAttribute("data-status", "disconnected");
  });
});
