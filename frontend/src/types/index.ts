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
  chart_type: "bar" | "line" | "pie" | "grouped_bar";
  title: string;
  data: Record<string, unknown>[];
  config?: Record<string, unknown>;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  company?: string;
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
}

export interface Company {
  name: string;
}

export interface CompaniesResponse {
  companies: Company[];
}
