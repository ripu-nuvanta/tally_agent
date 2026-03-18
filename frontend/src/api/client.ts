import axios from "axios";
import type {
  ChatRequest,
  ChatResponse,
  CompaniesResponse,
  HealthResponse,
  TallyModeResponse,
} from "../types";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  timeout: 480000,
});

export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/chat", request);
  return data;
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health");
  return data;
}

export async function getCompanies(): Promise<CompaniesResponse> {
  const { data } = await api.get<CompaniesResponse>("/companies");
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
