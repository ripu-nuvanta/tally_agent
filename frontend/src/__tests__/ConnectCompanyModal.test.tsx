import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConnectCompanyModal from "../components/ConnectCompanyModal";

vi.mock("../api/client");

const mockedClient = vi.mocked(await import("../api/client"));

const mockWorkspace = {
  id: "ws-new",
  name: "My Books",
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
    mockedClient.getCompanies.mockResolvedValue({ companies: [{ name: "Bharat Traders Pvt Ltd" }] });
  });

  it("renders the form with required fields and buttons", () => {
    renderModal();
    expect(screen.getByText("Connect Tally Company")).toBeInTheDocument();
    expect(screen.getByText("Friendly Name")).toBeInTheDocument();
    expect(screen.getByText("Tally Host")).toBeInTheDocument();
    expect(screen.getByText("Tally Port")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("e.g. Bharat Traders — Main Books")).toBeInTheDocument();
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

  it("verifies Tally company, creates workspace, shows confirmation, and fires onCreated on Start chat", async () => {
    mockedClient.getCompanies.mockResolvedValue({ companies: [{ name: "Bharat Traders Pvt Ltd" }] });
    mockedClient.createWorkspace.mockResolvedValue(mockWorkspace);
    const onCreated = vi.fn();
    const user = userEvent.setup();
    renderModal(vi.fn(), onCreated);

    await user.type(screen.getByPlaceholderText("e.g. Bharat Traders — Main Books"), "My Books");
    await user.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(mockedClient.getCompanies).toHaveBeenCalledWith({ host: "localhost", port: 9000 });
    });

    expect(mockedClient.createWorkspace).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "My Books",
        config: expect.objectContaining({ tally_company: "Bharat Traders Pvt Ltd" }),
      }),
    );

    // Confirmation screen
    await waitFor(() => {
      expect(screen.getByTestId("connect-confirm-company")).toHaveTextContent("Bharat Traders Pvt Ltd");
    });
    expect(screen.getByTestId("connect-confirm-name")).toHaveTextContent("My Books");

    // onCreated not yet called
    expect(onCreated).not.toHaveBeenCalled();

    // Click Start chat
    await user.click(screen.getByRole("button", { name: "Start chat" }));
    expect(onCreated).toHaveBeenCalledTimes(1);
    expect(onCreated).toHaveBeenCalledWith(mockWorkspace);
  });

  it("shows error and stays on form when Tally is unreachable", async () => {
    mockedClient.getCompanies.mockRejectedValue(new Error("Network error"));
    const onCreated = vi.fn();
    const user = userEvent.setup();
    renderModal(vi.fn(), onCreated);

    await user.type(screen.getByPlaceholderText("e.g. Bharat Traders — Main Books"), "My Books");
    await user.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(screen.getByText(/Check that Tally is running/i)).toBeInTheDocument();
    });

    expect(mockedClient.createWorkspace).not.toHaveBeenCalled();
    // Stays on form
    expect(screen.getByRole("button", { name: "Connect" })).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("shows no-company message (not generic error) when getCompanies returns empty list", async () => {
    mockedClient.getCompanies.mockResolvedValue({ companies: [] });
    const onCreated = vi.fn();
    const user = userEvent.setup();
    renderModal(vi.fn(), onCreated);

    await user.type(screen.getByPlaceholderText("e.g. Bharat Traders — Main Books"), "My Books");
    await user.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(screen.getByText(/no company is loaded in Tally/i)).toBeInTheDocument();
    });

    expect(mockedClient.createWorkspace).not.toHaveBeenCalled();
    // Stays on form
    expect(screen.getByRole("button", { name: "Connect" })).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("passes mock:true to getCompanies when Demo Mode is enabled", async () => {
    mockedClient.getCompanies.mockResolvedValue({ companies: [{ name: "Bharat Traders Pvt Ltd" }] });
    mockedClient.createWorkspace.mockResolvedValue(mockWorkspace);
    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByPlaceholderText("e.g. Bharat Traders — Main Books"), "My Books");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(mockedClient.getCompanies).toHaveBeenCalledWith({ mock: true });
    });
  });

  it("calls onClose when Cancel button is clicked", async () => {
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
