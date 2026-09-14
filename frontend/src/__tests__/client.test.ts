import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock axios so that axios.create() returns a stub instance whose methods we control.
const mockPost = vi.fn();
const mockInstance = {
  post: mockPost,
  get: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
  interceptors: {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  },
};

vi.mock("axios", () => ({
  default: {
    create: vi.fn(() => mockInstance),
  },
}));

// Import after the mock is registered.
const { testConnection, voucherAction } = await import("../api/client");

describe("testConnection", () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it("POSTs host+port to /tally/test-connection and returns the response data", async () => {
    mockPost.mockResolvedValue({
      data: { connected: true, companies: ["Bharat Traders Pvt Ltd"] },
    });

    const result = await testConnection("192.168.1.5", 9000);

    expect(mockPost).toHaveBeenCalledWith("/tally/test-connection", {
      host: "192.168.1.5",
      port: 9000,
    });
    expect(result).toEqual({
      connected: true,
      companies: ["Bharat Traders Pvt Ltd"],
    });
  });

  it("returns the error field when the connection fails", async () => {
    mockPost.mockResolvedValue({
      data: { connected: false, companies: [], error: "Connection refused" },
    });

    const result = await testConnection("localhost", 9000);

    expect(result.connected).toBe(false);
    expect(result.companies).toEqual([]);
    expect(result.error).toBe("Connection refused");
  });

  it("propagates network rejections", async () => {
    mockPost.mockRejectedValue(new Error("Network error"));
    await expect(testConnection("localhost", 9000)).rejects.toThrow("Network error");
  });
});

describe("voucherAction", () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it("POSTs conversation_id in the body so the backend can persist status", async () => {
    mockPost.mockResolvedValue({
      data: { message: "ok", data: { type: "voucher_written" }, session_id: "s1" },
    });

    await voucherAction(
      "approve",
      { id: "e1" },
      "Bharat Traders",
      "sess-1",
      "ws-1",
      "conv-1",
    );

    expect(mockPost).toHaveBeenCalledWith("/chat/voucher-action", {
      action: "approve",
      entry: { id: "e1" },
      company: "Bharat Traders",
      session_id: "sess-1",
      workspace_id: "ws-1",
      conversation_id: "conv-1",
    });
  });
});
