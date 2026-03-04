import axios from "axios";
import type {
  ChatRequest,
  ChatResponse,
  CompaniesResponse,
  HealthResponse,
} from "../types";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
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
