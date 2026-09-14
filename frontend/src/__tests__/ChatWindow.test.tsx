import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatWindow from "../components/ChatWindow";
import { SessionProvider } from "../context/SessionContext";
import * as api from "../api/client";

vi.mock("../api/client");
const mockedApi = vi.mocked(api);

Element.prototype.scrollIntoView = vi.fn();

function renderWithProvider(props?: { workspaceId?: string; conversationId?: string }) {
  return render(
    <SessionProvider>
      <ChatWindow {...props} />
    </SessionProvider>
  );
}

describe("ChatWindow", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders empty state with welcome message", () => {
    renderWithProvider();
    expect(screen.getByText("TallyPrime AI Assistant")).toBeInTheDocument();
    expect(screen.getByText("Ask me anything about your accounting data")).toBeInTheDocument();
  });

  it("renders quick actions in empty state", () => {
    renderWithProvider();
    expect(screen.getByRole("button", { name: "Cash balance" })).toBeInTheDocument();
  });

  it("shows user message after sending", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({ message: "Here is the trial balance", session_id: "sess-1" });
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "Show trial balance{Enter}");
    expect(screen.getByText("Show trial balance")).toBeInTheDocument();
  });

  it("shows agent response after successful API call", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({ message: "Your trial balance is ready", session_id: "sess-1" });
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "Trial balance{Enter}");
    await waitFor(() => {
      expect(screen.getByText("Your trial balance is ready")).toBeInTheDocument();
    });
  });

  it("shows error message on network error", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockRejectedValue(new Error("Network Error"));
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "test{Enter}");
    await waitFor(() => {
      expect(screen.getByText("Cannot connect to the server. Please check if the backend is running.")).toBeInTheDocument();
    });
  });

  it("shows generic error on non-network error", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockRejectedValue(new Error("Server Error"));
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "test{Enter}");
    await waitFor(() => {
      expect(screen.getByText("Something went wrong. Please try again.")).toBeInTheDocument();
    });
  });

  it("sends session_id on subsequent messages", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({ message: "Response 1", session_id: "sess-123" });
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "query 1{Enter}");
    await waitFor(() => { expect(screen.getByText("Response 1")).toBeInTheDocument(); });

    mockedApi.sendChat.mockResolvedValue({ message: "Response 2", session_id: "sess-123" });
    await user.type(textarea, "query 2{Enter}");
    await waitFor(() => {
      expect(mockedApi.sendChat).toHaveBeenLastCalledWith(expect.objectContaining({ session_id: "sess-123" }));
    });
  });

  it("renders data table in response", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({
      message: "Here is your data",
      data: { headers: ["Ledger", "Balance"], rows: [["Cash", 50000]] },
      session_id: "sess-1",
    });
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "cash balance{Enter}");
    await waitFor(() => {
      expect(screen.getByText("Cash")).toBeInTheDocument();
      expect(screen.getByText("Ledger")).toBeInTheDocument();
    });
  });

  it("triggers send from quick action click", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({ message: "P&L data", session_id: "sess-1" });
    renderWithProvider();
    await user.click(screen.getByRole("button", { name: "P&L last month" }));
    expect(mockedApi.sendChat).toHaveBeenCalledWith(expect.objectContaining({ message: "P&L last month" }));
  });

  describe("page-reload: workspace resolution after mount", () => {
    const mockConversation = {
      id: "conv-1",
      title: "Test conversation",
      tag: null,
      messages: [
        { id: "msg-1", role: "user" as const, content: "Hello", created_at: "2024-01-01T00:00:00Z" },
        { id: "msg-2", role: "assistant" as const, content: "Hi there!", created_at: "2024-01-01T00:00:01Z" },
      ],
    };

    it("loads messages immediately when both conversationId and workspaceId are provided at mount", async () => {
      mockedApi.getConversation.mockResolvedValue(mockConversation);
      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId="ws-1" />
        </SessionProvider>
      );
      await waitFor(() => {
        expect(screen.getByText("Hello")).toBeInTheDocument();
        expect(screen.getByText("Hi there!")).toBeInTheDocument();
      });
      expect(mockedApi.getConversation).toHaveBeenCalledWith("ws-1", "conv-1");
    });

    it("does not call getConversation when workspaceId is missing", () => {
      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" />
        </SessionProvider>
      );
      expect(mockedApi.getConversation).not.toHaveBeenCalled();
    });

    it("loads messages when workspaceId is resolved after mount (page-reload scenario)", async () => {
      mockedApi.getConversation.mockResolvedValue(mockConversation);

      // Simulate page-reload: initially no workspaceId (sidebar hasn't resolved yet)
      const { rerender } = render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId={undefined} />
        </SessionProvider>
      );

      // workspaceId is undefined — getConversation should NOT be called yet
      expect(mockedApi.getConversation).not.toHaveBeenCalled();
      expect(screen.queryByText("Hello")).not.toBeInTheDocument();

      // Sidebar resolves the workspace and ChatApp sets activeWorkspaceId → workspaceId prop updates
      await act(async () => {
        rerender(
          <SessionProvider>
            <ChatWindow conversationId="conv-1" workspaceId="ws-1" />
          </SessionProvider>
        );
      });

      await waitFor(() => {
        expect(screen.getByText("Hello")).toBeInTheDocument();
        expect(screen.getByText("Hi there!")).toBeInTheDocument();
      });
      expect(mockedApi.getConversation).toHaveBeenCalledWith("ws-1", "conv-1");
    });

    it("shows empty state when getConversation returns no messages", async () => {
      mockedApi.getConversation.mockResolvedValue({ ...mockConversation, messages: [] });
      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId="ws-1" />
        </SessionProvider>
      );
      await waitFor(() => {
        expect(mockedApi.getConversation).toHaveBeenCalled();
      });
      expect(screen.getByText("TallyPrime AI Assistant")).toBeInTheDocument();
    });

    it("shows empty state when getConversation fails", async () => {
      mockedApi.getConversation.mockRejectedValue(new Error("Not found"));
      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId="ws-1" />
        </SessionProvider>
      );
      await waitFor(() => {
        expect(mockedApi.getConversation).toHaveBeenCalled();
      });
      expect(screen.getByText("TallyPrime AI Assistant")).toBeInTheDocument();
    });
  });

  describe("pending_entry forwarding (T8 — FX rate override)", () => {
    const voucherReviewData = {
      type: "voucher_review",
      entries: [
        {
          id: "v-1",
          voucher_type: "Payment",
          date: "20260404",
          vendor_name: "Acme",
          amount: 8350,
          debit_ledger: "Travel Expenses",
          credit_ledger: "Cash",
          narration: "Acme",
          gst_entries: [],
          status: "draft",
          warnings: [],
          is_new_ledger: false,
          suggested_parent: null,
          original_currency: "USD",
          original_amount: 100,
          fx_rate: 83.5,
        },
      ],
      available_ledgers: ["Travel Expenses"],
      available_payment_ledgers: ["Cash"],
    };

    async function uploadVoucher(user: ReturnType<typeof userEvent.setup>) {
      mockedApi.sendChatWithFile.mockResolvedValue({
        message: "Review this entry",
        data: voucherReviewData as never,
        session_id: "sess-fx",
      });
      const fileInput = screen.getByTestId("file-input");
      const file = new File(["x"], "receipt.png", { type: "image/png" });
      await user.upload(fileInput, file);
      await user.click(screen.getByRole("button", { name: "Send message" }));
      await waitFor(() => {
        expect(screen.getByText("Review this entry")).toBeInTheDocument();
      });
    }

    it("includes pending_entry on the next chat after a voucher_review is shown", async () => {
      const user = userEvent.setup();
      renderWithProvider();
      await uploadVoucher(user);

      mockedApi.sendChat.mockResolvedValue({ message: "ok", session_id: "sess-fx" });
      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "use rate 84.5{Enter}");

      await waitFor(() => {
        expect(mockedApi.sendChat).toHaveBeenCalled();
      });
      expect(mockedApi.sendChat).toHaveBeenLastCalledWith(
        expect.objectContaining({
          pending_entry: expect.objectContaining({ id: "v-1", original_currency: "USD" }),
        }),
      );
    });

    it("forwards the updated entry when a chat rate-override returns a new voucher_review", async () => {
      const user = userEvent.setup();
      renderWithProvider();
      await uploadVoucher(user);

      // Rate-override chat response is itself a voucher_review with the new rate
      const updatedVoucher = {
        ...voucherReviewData,
        entries: [{ ...voucherReviewData.entries[0], amount: 8450, fx_rate: 84.5 }],
      };
      mockedApi.sendChat.mockResolvedValue({
        message: "Updated rate",
        data: updatedVoucher as never,
        session_id: "sess-fx",
      });
      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "use rate 84.5{Enter}");
      await waitFor(() => {
        expect(screen.getByText("Updated rate")).toBeInTheDocument();
      });

      // A subsequent chat forwards the *updated* pending entry (new rate)
      mockedApi.sendChat.mockResolvedValue({ message: "ok", session_id: "sess-fx" });
      await user.type(textarea, "use rate 85{Enter}");
      await waitFor(() => {
        expect(mockedApi.sendChat).toHaveBeenLastCalledWith(
          expect.objectContaining({
            pending_entry: expect.objectContaining({ id: "v-1", fx_rate: 84.5 }),
          }),
        );
      });
    });

    it("clears pending_entry after the voucher is discarded", async () => {
      const user = userEvent.setup();
      renderWithProvider();
      await uploadVoucher(user);

      mockedApi.voucherAction.mockResolvedValue({
        message: "Entry discarded.",
        data: { type: "voucher_discarded", entry_id: "v-1" } as never,
        session_id: "sess-fx",
      });
      await user.click(screen.getByText("Discard"));
      await waitFor(() => {
        expect(mockedApi.voucherAction).toHaveBeenCalled();
      });

      mockedApi.sendChat.mockResolvedValue({ message: "ok", session_id: "sess-fx" });
      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "hello{Enter}");
      await waitFor(() => {
        expect(mockedApi.sendChat).toHaveBeenCalled();
      });
      expect(mockedApi.sendChat).toHaveBeenLastCalledWith(
        expect.not.objectContaining({ pending_entry: expect.anything() }),
      );
    });
  });

  describe("voucher write result handling (BUG 2 — failed write must not show Written)", () => {
    const voucherReviewData = {
      type: "voucher_review",
      entries: [
        {
          id: "v-9",
          voucher_type: "Purchase",
          date: "20260404",
          vendor_name: "Croma",
          amount: 8350,
          debit_ledger: "Purchase Accounts",
          credit_ledger: "Croma",
          narration: "Croma",
          gst_entries: [],
          status: "draft",
          warnings: [],
          is_new_ledger: false,
          suggested_parent: null,
        },
      ],
      available_ledgers: ["Purchase Accounts"],
      available_payment_ledgers: ["Croma"],
    };

    async function uploadVoucher(user: ReturnType<typeof userEvent.setup>) {
      mockedApi.sendChatWithFile.mockResolvedValue({
        message: "Review this entry",
        data: voucherReviewData as never,
        session_id: "sess-w",
      });
      const fileInput = screen.getByTestId("file-input");
      const file = new File(["x"], "invoice.png", { type: "image/png" });
      await user.upload(fileInput, file);
      await user.click(screen.getByRole("button", { name: "Send message" }));
      await waitFor(() => {
        expect(screen.getByText("Review this entry")).toBeInTheDocument();
      });
    }

    it("does NOT mark the entry Written when the write returns a voucher_error", async () => {
      const user = userEvent.setup();
      renderWithProvider();
      await uploadVoucher(user);

      mockedApi.voucherAction.mockResolvedValue({
        message: "Couldn't create stock group in Tally — add it manually.",
        data: { type: "voucher_error", entry_id: "v-9" } as never,
        session_id: "sess-w",
      });
      await user.click(screen.getByRole("button", { name: /Write to Tally/ }));

      await waitFor(() => {
        expect(mockedApi.voucherAction).toHaveBeenCalled();
      });
      // The error message is surfaced...
      await waitFor(() => {
        expect(
          screen.getByText("Couldn't create stock group in Tally — add it manually."),
        ).toBeInTheDocument();
      });
      // ...the entry must NOT be shown as Written...
      expect(screen.queryByText("Written")).not.toBeInTheDocument();
      // ...and its status reverts to draft (action buttons available again).
      expect(screen.getByRole("button", { name: /Write to Tally/ })).toBeInTheDocument();
    });

    it("marks the entry Written when the write returns voucher_written (regression)", async () => {
      const user = userEvent.setup();
      renderWithProvider();
      await uploadVoucher(user);

      mockedApi.voucherAction.mockResolvedValue({
        message: "Voucher written to Tally.",
        data: { type: "voucher_written", entry_id: "v-9" } as never,
        session_id: "sess-w",
      });
      await user.click(screen.getByRole("button", { name: /Write to Tally/ }));

      await waitFor(() => {
        expect(screen.getByText("Written")).toBeInTheDocument();
      });
      // Terminal state: the write button is gone.
      expect(screen.queryByRole("button", { name: /Write to Tally/ })).not.toBeInTheDocument();
    });
  });

  describe("voucher action persistence in deferred-creation flow (BUG — conversation_id lost)", () => {
    const voucherReviewData = {
      type: "voucher_review",
      entries: [
        {
          id: "v-defer",
          voucher_type: "Purchase",
          date: "20260404",
          vendor_name: "Croma",
          amount: 8350,
          debit_ledger: "Purchase Accounts",
          credit_ledger: "Croma",
          narration: "Croma",
          gst_entries: [],
          status: "draft",
          warnings: [],
          is_new_ledger: false,
          suggested_parent: null,
        },
      ],
      available_ledgers: ["Purchase Accounts"],
      available_payment_ledgers: ["Croma"],
    };

    it("passes the just-created conversation id to voucherAction when uploading into a fresh chat", async () => {
      const user = userEvent.setup();
      const newConv = { id: "new-conv-123", title: null, tag: null, created_at: "2026-01-01", updated_at: "2026-01-01" };
      mockedApi.createConversation.mockResolvedValue(newConv);
      mockedApi.sendChatWithFile.mockResolvedValue({
        message: "Review this entry",
        data: voucherReviewData as never,
        session_id: "sess-w",
      });
      // After deferred creation the parent navigates and re-renders the window
      // with the new conversationId — getConversation is hit by the load effect.
      mockedApi.getConversation.mockResolvedValue({
        id: "new-conv-123",
        title: null,
        tag: null,
        messages: [],
      } as never);
      mockedApi.voucherAction.mockResolvedValue({
        message: "Voucher written to Tally.",
        data: { type: "voucher_written", entry_id: "v-defer" } as never,
        session_id: "sess-w",
      });

      function Wrapper(props: { conversationId?: string; workspaceId?: string }) {
        return (
          <SessionProvider>
            <ChatWindow workspaceName="Test" {...props} />
          </SessionProvider>
        );
      }

      // Fresh chat: conversationId prop is undefined (deferred creation).
      const { rerender } = render(<Wrapper workspaceId="ws-1" />);

      const fileInput = screen.getByTestId("file-input");
      const file = new File(["x"], "invoice.png", { type: "image/png" });
      await user.upload(fileInput, file);
      await user.click(screen.getByRole("button", { name: "Send message" }));
      await waitFor(() => {
        expect(screen.getByText("Review this entry")).toBeInTheDocument();
      });

      // CRITICAL — reproduce the live timing: the parent navigates to /c/:id
      // after deferred creation, so the conversationId prop updates to the new
      // id. This fires the load effect that nulls justCreatedConvRef, exposing
      // the stale-closure bug (the prior test skipped this rerender and so
      // falsely passed).
      await act(async () => {
        rerender(<Wrapper workspaceId="ws-1" conversationId="new-conv-123" />);
      });

      await user.click(screen.getByRole("button", { name: /Write to Tally/ }));

      await waitFor(() => {
        expect(mockedApi.voucherAction).toHaveBeenCalled();
      });
      // The 6th positional arg is conversationId — it must be the deferred-created
      // id, NOT "" (which makes the backend silently skip persistence).
      expect(mockedApi.voucherAction).toHaveBeenCalledWith(
        "approve",
        expect.anything(),
        expect.anything(),
        expect.anything(),
        "ws-1",
        "new-conv-123",
      );
    });
  });

  describe("voucher edit save (BUG — Save must be a LOCAL merge, not a backend write)", () => {
    const inventoryVoucherReview = {
      type: "voucher_review",
      entries: [
        {
          id: "v-edit",
          voucher_type: "Purchase",
          date: "20260410",
          vendor_name: "Acme Supplies",
          party_name: "Acme Supplies",
          party_ledger: "Acme Supplies",
          is_party_ledger: true,
          amount: 13570,
          debit_ledger: "Purchase Accounts",
          credit_ledger: "Acme Supplies",
          narration: "Purchase — Acme Supplies",
          reference: "OLD-123",
          gst_entries: [],
          status: "draft",
          warnings: [],
          is_new_ledger: false,
          suggested_parent: null,
          is_inventory: true,
          line_items: [
            {
              description: "A4 Paper Ream 500 sheets",
              qty: 4,
              rate: 250,
              unit: "Nos",
              gst_rate: 18,
              amount: 1000,
              matched_item: "A4 Paper Ream",
              create_new: false,
              stock_name: "A4 Paper Ream 500 sheets",
              stock_group: "Office Supplies",
              hsn: "4802",
              ledger: "Purchase Accounts",
            },
          ],
          available_stock_items: ["A4 Paper Ream", "Stapler"],
          default_stock_group: "Office Supplies",
        },
      ],
      available_ledgers: ["Purchase Accounts"],
      available_payment_ledgers: ["Cash"],
      available_supplier_ledgers: ["Acme Supplies", "Beta Traders"],
      available_customer_ledgers: ["Globex Ltd"],
    };

    async function uploadInventoryVoucher(user: ReturnType<typeof userEvent.setup>) {
      mockedApi.sendChatWithFile.mockResolvedValue({
        message: "Review this entry",
        data: inventoryVoucherReview as never,
        session_id: "sess-edit",
      });
      const fileInput = screen.getByTestId("file-input");
      const file = new File(["x"], "invoice.png", { type: "image/png" });
      await user.upload(fileInput, file);
      await user.click(screen.getByRole("button", { name: "Send message" }));
      await waitFor(() => {
        expect(screen.getByText("Review this entry")).toBeInTheDocument();
      });
    }

    it("merges edited reference + qty locally on Save without writing to the backend", async () => {
      const user = userEvent.setup();
      // Save persists the draft (no Tally write) — stub it so the fire-and-forget
      // call resolves; the assertion below is that the WRITE path is untouched.
      mockedApi.saveVoucherDraft.mockResolvedValue({
        message: "Draft saved.",
        data: { type: "voucher_draft_saved", entry_id: "v-edit" } as never,
        session_id: "sess-edit",
      });
      renderWithProvider();
      await uploadInventoryVoucher(user);

      // Pre-edit: the card shows the OLD invoice number.
      expect(screen.getByText("OLD-123")).toBeInTheDocument();

      // Open the edit form, change the Supplier Invoice No. and a line-item qty.
      await user.click(screen.getByRole("button", { name: "Edit Entry" }));
      const invoiceField = screen.getByLabelText("Supplier Invoice No.");
      await user.clear(invoiceField);
      await user.type(invoiceField, "NEW-999");
      const qtyField = screen.getByLabelText("Qty 1");
      await user.clear(qtyField);
      await user.type(qtyField, "9");

      await user.click(screen.getByRole("button", { name: "Save" }));

      // (a) The card re-renders with the NEW invoice number and NEW qty.
      await waitFor(() => {
        expect(screen.getByText("NEW-999")).toBeInTheDocument();
      });
      expect(screen.queryByText("OLD-123")).not.toBeInTheDocument();
      // New qty visible in the expanded line table.
      await user.click(screen.getByText("Show details"));
      const table = screen.getByTestId("voucher-line-items-v-edit");
      expect(table).toHaveTextContent("9 Nos");

      // (b) The entry stays a draft — action buttons are back.
      expect(screen.getByRole("button", { name: /Write to Tally/ })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Edit Entry" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Discard" })).toBeInTheDocument();

      // (c) Save must NOT round-trip to the WRITE path (no premature write).
      expect(mockedApi.voucherAction).not.toHaveBeenCalled();
    });

    it("persists the edited draft via save_draft (no write) on Save", async () => {
      const user = userEvent.setup();
      mockedApi.saveVoucherDraft.mockResolvedValue({
        message: "Draft saved.",
        data: { type: "voucher_draft_saved", entry_id: "v-edit" } as never,
        session_id: "sess-edit",
      });
      mockedApi.createConversation.mockResolvedValue({
        id: "new-conv-edit", title: null, tag: null,
        created_at: "2026-01-01", updated_at: "2026-01-01",
      });
      renderWithProvider({ workspaceId: "ws-1" });
      await uploadInventoryVoucher(user);

      await user.click(screen.getByRole("button", { name: "Edit Entry" }));
      const invoiceField = screen.getByLabelText("Supplier Invoice No.");
      await user.clear(invoiceField);
      await user.type(invoiceField, "NEW-999");
      const qtyField = screen.getByLabelText("Qty 1");
      await user.clear(qtyField);
      await user.type(qtyField, "9");

      await user.click(screen.getByRole("button", { name: "Save" }));

      // Draft IS persisted with the merged edits…
      await waitFor(() => {
        expect(mockedApi.saveVoucherDraft).toHaveBeenCalled();
      });
      const savedEntry = mockedApi.saveVoucherDraft.mock.calls[0][0] as Record<
        string,
        unknown
      >;
      expect(savedEntry.id).toBe("v-edit");
      expect(savedEntry.reference).toBe("NEW-999");
      expect((savedEntry.line_items as Array<Record<string, unknown>>)[0].qty).toBe(9);

      // …but the WRITE path is never hit.
      expect(mockedApi.voucherAction).not.toHaveBeenCalled();
    });
  });

  describe("workspace landing page (Task 5)", () => {
    it("shows workspace name when workspaceName is provided without conversationId", () => {
      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Bharat Traders" />
        </SessionProvider>
      );
      expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
      expect(screen.getByText(/Connected to/)).toBeInTheDocument();
    });

    it("shows hint text on landing page", () => {
      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Bharat Traders" />
        </SessionProvider>
      );
      expect(screen.getByText("Type or upload to start a conversation")).toBeInTheDocument();
    });

    it("shows quick action buttons on landing page", () => {
      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Bharat Traders" />
        </SessionProvider>
      );
      expect(screen.getByRole("button", { name: "Cash balance" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Top 10 customers" })).toBeInTheDocument();
    });

    it("does not show hint text when conversationId is set", () => {
      mockedApi.getConversation.mockResolvedValue({
        id: "conv-1",
        title: "Test",
        tag: null,
        messages: [],
      });
      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId="ws-1" workspaceName="Bharat Traders" />
        </SessionProvider>
      );
      expect(screen.queryByText("Type or upload to start a conversation")).not.toBeInTheDocument();
    });
  });

  describe("deferred conversation creation (Task 6)", () => {
    it("creates conversation on first send when no conversationId", async () => {
      const user = userEvent.setup();
      const newConv = { id: "conv-new", title: null, tag: null, created_at: "2026-01-01", updated_at: "2026-01-01" };
      mockedApi.createConversation.mockResolvedValue(newConv);
      mockedApi.sendChat.mockResolvedValue({ message: "Response", session_id: "sess-1" });
      const onCreated = vi.fn();

      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Test" onConversationCreated={onCreated} />
        </SessionProvider>
      );

      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "Show trial balance{Enter}");

      await waitFor(() => {
        expect(mockedApi.createConversation).toHaveBeenCalledWith("ws-1");
      });
      await waitFor(() => {
        expect(mockedApi.sendChat).toHaveBeenCalledWith(
          expect.objectContaining({ conversation_id: "conv-new" }),
        );
      });
      expect(onCreated).toHaveBeenCalledWith("conv-new");
    });

    it("does not create conversation when conversationId is already set", async () => {
      const user = userEvent.setup();
      mockedApi.getConversation.mockResolvedValue({
        id: "conv-1",
        title: "Test",
        tag: null,
        messages: [],
      });
      mockedApi.sendChat.mockResolvedValue({ message: "Response", session_id: "sess-1" });
      const onCreated = vi.fn();

      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId="ws-1" onConversationCreated={onCreated} />
        </SessionProvider>
      );

      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "Show trial balance{Enter}");

      await waitFor(() => {
        expect(mockedApi.sendChat).toHaveBeenCalled();
      });
      expect(mockedApi.createConversation).not.toHaveBeenCalled();
      expect(onCreated).not.toHaveBeenCalled();
    });

    it("quick action triggers deferred creation", async () => {
      const user = userEvent.setup();
      const newConv = { id: "conv-qa", title: null, tag: null, created_at: "2026-01-01", updated_at: "2026-01-01" };
      mockedApi.createConversation.mockResolvedValue(newConv);
      mockedApi.sendChat.mockResolvedValue({ message: "P&L data", session_id: "sess-1" });
      const onCreated = vi.fn();

      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Test" onConversationCreated={onCreated} />
        </SessionProvider>
      );

      await user.click(screen.getByRole("button", { name: "P&L last month" }));

      await waitFor(() => {
        expect(mockedApi.createConversation).toHaveBeenCalledWith("ws-1");
      });
      await waitFor(() => {
        expect(mockedApi.sendChat).toHaveBeenCalledWith(
          expect.objectContaining({ conversation_id: "conv-qa" }),
        );
      });
      expect(onCreated).toHaveBeenCalledWith("conv-qa");
    });

    it("does not clobber optimistic messages when first send creates the conversation", async () => {
      const user = userEvent.setup();
      const newConv = { id: "conv-new", title: null, tag: null, created_at: "2026-01-01", updated_at: "2026-01-01" };
      mockedApi.createConversation.mockResolvedValue(newConv);
      // Server hasn't persisted the optimistic messages yet
      mockedApi.getConversation.mockResolvedValue({ id: "conv-new", title: null, tag: null, messages: [] });
      mockedApi.sendChat.mockResolvedValue({ message: "Reply A", session_id: "s1" });

      function Wrapper(props: { conversationId?: string; workspaceId?: string }) {
        return (
          <SessionProvider>
            <ChatWindow {...props} />
          </SessionProvider>
        );
      }

      const { rerender } = render(<Wrapper workspaceId="ws-1" />);

      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "First question{Enter}");

      await waitFor(() => {
        expect(mockedApi.createConversation).toHaveBeenCalledWith("ws-1");
      });

      // Simulate parent navigation to /c/:id after creation
      await act(async () => {
        rerender(<Wrapper workspaceId="ws-1" conversationId="conv-new" />);
      });

      // The ref guard should prevent getConversation from wiping optimistic state
      await waitFor(() => {
        expect(screen.getByText("Reply A")).toBeInTheDocument();
      });
      expect(screen.getByText("First question")).toBeInTheDocument();
    });

    it("does not clear optimistic messages when workspaceId changes mid-send", async () => {
      const user = userEvent.setup();
      // createConversation never resolves → the send stays in flight and
      // conversationId remains undefined for the whole test window.
      mockedApi.createConversation.mockReturnValue(new Promise(() => {}));
      mockedApi.getConversation.mockResolvedValue({ id: "conv-x", title: null, tag: null, messages: [] });

      function Wrapper(props: { conversationId?: string; workspaceId?: string }) {
        return (
          <SessionProvider>
            <ChatWindow {...props} />
          </SessionProvider>
        );
      }

      const { rerender } = render(<Wrapper workspaceId="ws-1" />);

      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "Mid-send question{Enter}");

      // Optimistic user message is rendered while the send is in flight.
      expect(screen.getByText("Mid-send question")).toBeInTheDocument();

      // workspaceId changes mid-send (conversationId still undefined). The
      // load-effect re-runs and would hit the clear branch — but the
      // sendingRef guard must skip it so the optimistic message survives.
      await act(async () => {
        rerender(<Wrapper workspaceId="ws-2" />);
      });

      expect(screen.getByText("Mid-send question")).toBeInTheDocument();
    });

    it("clears messages when navigating to the new-chat landing page", async () => {
      mockedApi.getConversation.mockResolvedValue({
        id: "conv-1",
        title: "Test",
        tag: null,
        messages: [
          { id: "m1", role: "user" as const, content: "old question", created_at: "2026-01-01T00:00:00Z" },
          { id: "m2", role: "assistant" as const, content: "old answer", created_at: "2026-01-01T00:00:01Z" },
        ],
      });

      function Wrapper(props: { conversationId?: string; workspaceId?: string }) {
        return (
          <SessionProvider>
            <ChatWindow {...props} />
          </SessionProvider>
        );
      }

      const { rerender } = render(<Wrapper workspaceId="ws-1" conversationId="conv-1" />);

      await waitFor(() => {
        expect(screen.getByText("old answer")).toBeInTheDocument();
      });

      // Navigate to new-chat landing page (conversationId becomes undefined)
      await act(async () => {
        rerender(<Wrapper workspaceId="ws-1" conversationId={undefined} />);
      });

      await waitFor(() => {
        expect(screen.queryByText("old question")).not.toBeInTheDocument();
      });
      expect(screen.queryByText("old answer")).not.toBeInTheDocument();
      expect(screen.getByText("TallyPrime AI Assistant")).toBeInTheDocument();
    });

    it("omits pending_entry when no voucher is pending", async () => {
      const user = userEvent.setup();
      mockedApi.sendChat.mockResolvedValue({ message: "Response", session_id: "sess-1" });
      renderWithProvider();
      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "cash balance{Enter}");
      await waitFor(() => {
        expect(mockedApi.sendChat).toHaveBeenCalled();
      });
      expect(mockedApi.sendChat).toHaveBeenLastCalledWith(
        expect.not.objectContaining({ pending_entry: expect.anything() }),
      );
    });

    it("loading prevents double creation on rapid sends", async () => {
      const user = userEvent.setup();
      // Make createConversation slow so we can test double-send prevention
      const newConv = { id: "conv-once", title: null, tag: null, created_at: "2026-01-01", updated_at: "2026-01-01" };
      mockedApi.createConversation.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(newConv), 100))
      );
      mockedApi.sendChat.mockResolvedValue({ message: "Response", session_id: "sess-1" });

      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Test" />
        </SessionProvider>
      );

      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      // First send
      await user.type(textarea, "Query 1{Enter}");

      // The loading state should disable the send button, preventing second send
      // The send button should be disabled while loading
      const sendButton = screen.getByRole("button", { name: "Send message" });
      expect(sendButton).toBeDisabled();

      await waitFor(() => {
        expect(mockedApi.createConversation).toHaveBeenCalledTimes(1);
      });
    });
  });
});
