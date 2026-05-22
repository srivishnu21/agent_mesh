import type { Agent, AgentCreate, Conversation, Message, Model, Run, RunEvent, Tool, Workflow, WorkflowCreate } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const qs = (params: Record<string, string | number | boolean | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) search.set(key, String(value));
  });
  const value = search.toString();
  return value ? `?${value}` : "";
};

export const api = {
  health: () => request<{ status: string; db: string }>("/health"),
  createAgent: (payload: AgentCreate) => request<Agent>("/api/v1/agents", { method: "POST", body: JSON.stringify(payload) }),
  listAgents: (params: { limit?: number; offset?: number } = {}) => request<Agent[]>(`/api/v1/agents${qs(params)}`),
  getAgent: (id: string) => request<Agent>(`/api/v1/agents/${id}`),
  updateAgent: (id: string, payload: Partial<AgentCreate>) => request<Agent>(`/api/v1/agents/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteAgent: (id: string) => request<void>(`/api/v1/agents/${id}`, { method: "DELETE" }),
  listTools: () => request<Tool[]>("/api/v1/agents/tools"),
  listModels: () => request<Model[]>("/api/v1/agents/models"),
  createWorkflow: (payload: WorkflowCreate) => request<Workflow>("/api/v1/workflows", { method: "POST", body: JSON.stringify(payload) }),
  listWorkflows: (params: { is_template?: boolean; limit?: number; offset?: number } = {}) => request<Workflow[]>(`/api/v1/workflows${qs(params)}`),
  getWorkflow: (id: string) => request<Workflow>(`/api/v1/workflows/${id}`),
  runWorkflow: (id: string, trigger: Record<string, unknown>) => request<{ run_id: string }>(`/api/v1/workflows/${id}/run`, { method: "POST", body: JSON.stringify({ trigger }) }),
  listRuns: (params: { workflow_id?: string; status?: string; limit?: number; offset?: number } = {}) => request<Run[]>(`/api/v1/runs${qs(params)}`),
  getRun: (id: string) => request<Run & { events: RunEvent[] }>(`/api/v1/runs/${id}`),
  listRunEvents: (id: string, params: { limit?: number; offset?: number } = {}) => request<RunEvent[]>(`/api/v1/runs/${id}/events${qs(params)}`),
  listConversations: (params: { channel?: string; limit?: number; offset?: number } = {}) => request<Conversation[]>(`/api/v1/conversations${qs(params)}`),
  getConversation: (id: string) => request<Conversation & { messages: Message[] }>(`/api/v1/conversations/${id}`),
  listMessages: (id: string, params: { limit?: number; offset?: number } = {}) => request<Message[]>(`/api/v1/conversations/${id}/messages${qs(params)}`),
  telegramWebhook: (payload: Record<string, unknown>) => request<{ ok: boolean; conversation_id: string | null; message_id: string | null }>("/api/v1/telegram/webhook", { method: "POST", body: JSON.stringify(payload) })
};

export const wsRunUrl = (runId: string) => `${API_URL.replace(/^http/, "ws")}/ws/runs/${runId}`;
