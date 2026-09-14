export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  data?: TableData | TableData[];
  chart?: ChartSpec;
  isError?: boolean;
  isLoading?: boolean;
}

export interface TableData {
  headers: string[];
  rows: (string | number | null)[][];
}

export interface ChartSpec {
  chart_type: "bar" | "line" | "pie" | "grouped_bar" | "composed";
  title: string;
  data: Record<string, unknown>[];
  config?: Record<string, unknown>;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  company?: string;
  workspace_id?: string;
  conversation_id?: string;
  pending_entry?: Record<string, unknown> | null;
}

export interface ChatResponse {
  message: string;
  data?: TableData | TableData[];
  chart?: ChartSpec;
  session_id: string;
}

export interface HealthResponse {
  status: string;
  tally_connected: boolean;
  tally_url: string;
  mode?: "mock" | "live" | null;
}

export interface Company {
  name: string;
}

export interface CompaniesResponse {
  companies: Company[];
}

export interface TestConnectionResponse {
  connected: boolean;
  companies: string[];
  error?: string;
}

export interface TallyModeResponse {
  mode: "mock" | "live";
}

export interface TallyModeRequest {
  mode: "mock" | "live";
}

// --- Auth types (Set A1) ---

export interface AuthUser {
  id: string;
  email: string;
  name: string;
}

export interface AuthResponse {
  user: AuthUser;
  access_token: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// --- Workspace types (Set A1) ---

export interface WorkspaceData {
  id: string;
  name: string;
  agent_type: string;
  config: Record<string, unknown>;
  memory: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  tag: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  tag: string | null;
  messages: MessageData[];
}

export interface MessageData {
  id: string;
  role: "user" | "assistant";
  content: string;
  data?: TableData | TableData[];
  chart?: ChartSpec;
  created_at: string;
}
