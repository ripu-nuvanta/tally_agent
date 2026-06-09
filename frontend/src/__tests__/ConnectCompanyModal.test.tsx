import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConnectCompanyModal from "../components/ConnectCompanyModal";

vi.mock("../api/client");

const mockedClient = vi.mocked(await import("../api/client"));

const mockWorkspace = {
  id: "ws-new",
  name: "Bharat Traders Pvt Ltd",
  agent_type: "tally",
  config: { tally_company: "Bharat Traders Pvt Ltd" },
  memory: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderModal(onClose = vi.fn(), onCreated = vi.fn()) {
  return render(<ConnectCompanyModal onClose={onClose} onCreated={onCreated} />);
}

describe("ConnectCompanyModal", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockedClient.testConnection.mockResolvedValue({
      connected: true,
      companies: ["Bharat Traders Pvt Ltd"],
    });
    mockedClient.createWorkspace.mockResolvedValue(mockWorkspace);
  });

  // --- Initial state ---
  it("renders host + port fields and a Test Connection button, no dropdown", () => {
    renderModal();
    expect(screen.getByText("Connect Tally Company")).toBeInTheDocument();
    expect(screen.getByText("Tally Host")).toBeInTheDocument();
    expect(screen.getByText("Tally Port")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Test Connection" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Company")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  // --- Connecting state ---
  it("shows a connecting label while test-connection is in flight", async () => {
    let resolve!: (v: { connected: boolean; companies: string[] }) => void;
    mockedClient.testConnection.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("button", { name: "Test Connection" }));
    expect(screen.getByText("Connecting...")).toBeInTheDocument();
    resolve({ connected: true, companies: ["Bharat Traders Pvt Ltd"] });
    await waitFor(() =>
      expect(screen.queryByText("Connecting...")).not.toBeInTheDocument(),
    );
  });

  // --- Connected: single company auto-selected ---
  it("auto-selects a single returned company and enables Create Workspace", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("button", { name: "Test Connection" }));

    await waitFor(() =>
      expect(mockedClient.testConnection).toHaveBeenCalledWith("localhost", 9000),
    );
    // Single company shown (read-only confirmation, not a select)
    expect(screen.getAllByText("Bharat Traders Pvt Ltd").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Create Workspace" })).toBeEnabled();
  });

  // --- Connected: multiple companies require selection ---
  it("renders a dropdown for multiple companies and requires a selection", async () => {
    mockedClient.testConnection.mockResolvedValue({
      connected: true,
      companies: ["Bharat Traders Pvt Ltd", "Acme Exports"],
    });
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("button", { name: "Test Connection" }));

    const select = await screen.findByLabelText("Company");
    expect(select).toBeInTheDocument();
    // Create disabled until a company is picked
    expect(screen.getByRole("button", { name: "Create Workspace" })).toBeDisabled();

    await user.selectOptions(select, "Acme Exports");
    expect(screen.getByRole("button", { name: "Create Workspace" })).toBeEnabled();
  });

  // --- Connected → create → confirm → onCreated(ws) ---
  it("creates workspace using the selected company name and fires onCreated", async () => {
    const onCreated = vi.fn();
    const user = userEvent.setup();
    renderModal(vi.fn(), onCreated);

    await user.click(screen.getByRole("button", { name: "Test Connection" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Create Workspace" })).toBeEnabled(),
    );
    await user.click(screen.getByRole("button", { name: "Create Workspace" }));

    await waitFor(() =>
      expect(mockedClient.createWorkspace).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Bharat Traders Pvt Ltd",
          config: expect.objectContaining({
            tally_company: "Bharat Traders Pvt Ltd",
            mock_mode: false,
          }),
        }),
      ),
    );

    // Confirmation screen, then onCreated on Start chat
    await waitFor(() =>
      expect(screen.getByTestId("connect-confirm-company")).toHaveTextContent(
        "Bharat Traders Pvt Ltd",
      ),
    );
    expect(onCreated).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Start chat" }));
    expect(onCreated).toHaveBeenCalledWith(mockWorkspace);
  });

  // --- Connection failed (error from API) ---
  it("shows an error message when the connection fails and allows retry", async () => {
    mockedClient.testConnection.mockResolvedValue({
      connected: false,
      companies: [],
      error: "Connection refused",
    });
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("button", { name: "Test Connection" }));

    await waitFor(() =>
      expect(screen.getByText("Connection refused")).toBeInTheDocument(),
    );
    // Retry button still available
    expect(screen.getByRole("button", { name: "Test Connection" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Company")).not.toBeInTheDocument();
  });

  // --- Connection failed (thrown error) ---
  it("shows a fallback error when test-connection throws", async () => {
    mockedClient.testConnection.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("button", { name: "Test Connection" }));

    await waitFor(() =>
      expect(screen.getByText(/Could not reach Tally/i)).toBeInTheDocument(),
    );
  });

  // --- Mock mode on ---
  it("auto-fills the fixture company in demo mode without calling testConnection", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("checkbox"));

    // No Test Connection needed; company already selected
    expect(mockedClient.testConnection).not.toHaveBeenCalled();
    expect(screen.getAllByText("Bharat Traders Pvt Ltd").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Create Workspace" })).toBeEnabled();
  });

  // --- Mock mode toggle resets state ---
  it("resets connection state when demo mode is toggled off", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("checkbox")); // on
    expect(screen.getByRole("button", { name: "Create Workspace" })).toBeEnabled();
    await user.click(screen.getByRole("checkbox")); // off
    expect(screen.getByRole("button", { name: "Test Connection" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Workspace" })).toBeDisabled();
  });

  it("sets mock_mode true in config when created in demo mode", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Create Workspace" }));
    await waitFor(() =>
      expect(mockedClient.createWorkspace).toHaveBeenCalledWith(
        expect.objectContaining({
          config: expect.objectContaining({ mock_mode: true }),
        }),
      ),
    );
  });

  it("calls onClose when Cancel is clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderModal(onClose);
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders modal with mobile-safe width classes", () => {
    renderModal();
    const modalPanel = screen.getByText("Connect Tally Company").closest("div")!;
    expect(modalPanel.className).toContain("mx-4");
    expect(modalPanel.className).toContain("md:mx-auto");
    expect(modalPanel.className).toContain("md:max-w-md");
  });
});
