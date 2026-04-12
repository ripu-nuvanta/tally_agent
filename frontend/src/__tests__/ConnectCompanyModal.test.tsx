import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConnectCompanyModal from "../components/ConnectCompanyModal";

vi.mock("../api/client");

const mockedClient = vi.mocked(await import("../api/client"));

const mockWorkspace = {
  id: "ws-new",
  name: "Test Company",
  agent_type: "tally",
  config: {},
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
  });

  it("renders the form with required fields and buttons", () => {
    renderModal();
    expect(screen.getByText("Connect Tally Company")).toBeInTheDocument();
    expect(screen.getByText("Company Name")).toBeInTheDocument();
    expect(screen.getByText("Tally Host")).toBeInTheDocument();
    expect(screen.getByText("Tally Port")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Bharat Traders Pvt Ltd")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("toggles Demo Mode label when checkbox is clicked", async () => {
    const user = userEvent.setup();
    renderModal();

    // Default: "Connects to live Tally"
    expect(screen.getByText("Connects to live Tally")).toBeInTheDocument();

    // Click the Demo Mode toggle (visually hidden checkbox)
    const checkbox = screen.getByRole("checkbox");
    await user.click(checkbox);

    expect(screen.getByText("Uses sample data")).toBeInTheDocument();
  });

  it("calls createWorkspace and onCreated on successful submit", async () => {
    mockedClient.createWorkspace.mockResolvedValue(mockWorkspace);
    const onCreated = vi.fn();
    const user = userEvent.setup();
    renderModal(vi.fn(), onCreated);

    await user.clear(screen.getByPlaceholderText("Bharat Traders Pvt Ltd"));
    await user.type(screen.getByPlaceholderText("Bharat Traders Pvt Ltd"), "Test Company");
    await user.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(mockedClient.createWorkspace).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Test Company" })
      );
      expect(onCreated).toHaveBeenCalledTimes(1);
    });
  });

  it("shows error message when createWorkspace fails", async () => {
    mockedClient.createWorkspace.mockRejectedValue(new Error("Network error"));
    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByPlaceholderText("Bharat Traders Pvt Ltd"), "Bad Company");
    await user.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(screen.getByText("Failed to connect company. Please try again.")).toBeInTheDocument();
    });
  });

  it("calls onClose when Cancel button is clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderModal(onClose);

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
