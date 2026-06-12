import axios from "axios";
import type {
  AuthResponse,
  ChatRequest,
  ChatResponse,
  CompaniesResponse,
  ConversationDetail,
  ConversationSummary,
  HealthResponse,
  LoginRequest,
  RegisterRequest,
  TallyModeResponse,
  TestConnectionResponse,
  WorkspaceData,
} from "../types";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  timeout: 480000,
});

// --- Auth token management ---

let _accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

api.interceptors.request.use((config) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/")
    ) {
      originalRequest._retry = true;
      try {
        const { data } = await api.post<{ access_token: string }>("/auth/refresh");
        _accessToken = data.access_token;
        originalRequest.headers.Authorization = `Bearer ${_accessToken}`;
        return api(originalRequest);
      } catch {
        _accessToken = null;
        window.location.href = "/login";
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  },
);

// --- Auth API ---

export async function register(req: RegisterRequest): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/auth/register", req);
  _accessToken = data.access_token;
  return data;
}

export async function login(req: LoginRequest): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/auth/login", req);
  _accessToken = data.access_token;
  return data;
}

export async function refreshToken(): Promise<string> {
  const { data } = await api.post<{ access_token: string }>("/auth/refresh");
  _accessToken = data.access_token;
  return data.access_token;
}

export async function logout(): Promise<void> {
  await api.post("/auth/logout");
  _accessToken = null;
}

export async function getMe(): Promise<AuthResponse["user"]> {
  const { data } = await api.get<AuthResponse["user"]>("/auth/me");
  return data;
}

// --- Workspace API ---

export async function getWorkspaces(): Promise<WorkspaceData[]> {
  const { data } = await api.get<WorkspaceData[]>("/workspaces");
  return data;
}

export async function createWorkspace(req: {
  name: string;
  agent_type?: string;
  config?: Record<string, unknown>;
}): Promise<WorkspaceData> {
  const { data } = await api.post<WorkspaceData>("/workspaces", req);
  return data;
}

export async function deleteWorkspace(id: string): Promise<void> {
  await api.delete(`/workspaces/${id}`);
}

// --- Conversation API ---

export async function getConversations(workspaceId: string): Promise<ConversationSummary[]> {
  const { data } = await api.get<ConversationSummary[]>(`/workspaces/${workspaceId}/conversations`);
  return data;
}

export async function createConversation(
  workspaceId: string,
  req?: { title?: string; tag?: string },
): Promise<ConversationSummary> {
  const { data } = await api.post<ConversationSummary>(
    `/workspaces/${workspaceId}/conversations`,
    req || {},
  );
  return data;
}

export async function getConversation(
  workspaceId: string,
  conversationId: string,
): Promise<ConversationDetail> {
  const { data } = await api.get<ConversationDetail>(
    `/workspaces/${workspaceId}/conversations/${conversationId}`,
  );
  return data;
}

export async function updateConversation(
  workspaceId: string,
  conversationId: string,
  req: { title?: string; tag?: string },
): Promise<ConversationSummary> {
  const { data } = await api.patch<ConversationSummary>(
    `/workspaces/${workspaceId}/conversations/${conversationId}`,
    req,
  );
  return data;
}

export async function deleteConversation(
  workspaceId: string,
  conversationId: string,
): Promise<void> {
  await api.delete(`/workspaces/${workspaceId}/conversations/${conversationId}`);
}

// --- Existing APIs (unchanged) ---

export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/chat", request);
  return data;
}

export async function sendChatWithFile(
  file: File,
  message: string,
  workspaceId?: string,
  conversationId?: string,
): Promise<ChatResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("message", message);
  if (workspaceId) form.append("workspace_id", workspaceId);
  if (conversationId) form.append("conversation_id", conversationId);

  const { data } = await api.post<ChatResponse>("/chat/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export type VoucherAction = "approve" | "discard" | "edit";

export async function voucherAction(
  action: VoucherAction,
  entry: Record<string, unknown>,
  company: string,
  sessionId: string,
  workspaceId: string,
  conversationId: string,
): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/chat/voucher-action", {
    action,
    entry,
    company,
    session_id: sessionId,
    workspace_id: workspaceId,
    conversation_id: conversationId,
  });
  return data;
}

export async function getHealth(params?: { host?: string; port?: number }): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health", { params });
  return data;
}

export async function getCompanies(params?: {
  host?: string;
  port?: number;
  mock?: boolean;
}): Promise<CompaniesResponse> {
  const { data } = await api.get<CompaniesResponse>("/companies", { params });
  return data;
}

export async function testConnection(
  host: string,
  port: number,
): Promise<TestConnectionResponse> {
  const { data } = await api.post<TestConnectionResponse>("/tally/test-connection", {
    host,
    port,
  });
  return data;
}

export async function getTallyMode(): Promise<TallyModeResponse> {
  const { data } = await api.get<TallyModeResponse>("/tally-mode");
  return data;
}

export async function setTallyMode(mode: "mock" | "live"): Promise<TallyModeResponse> {
  const { data } = await api.post<TallyModeResponse>("/tally-mode", { mode });
  return data;
}
