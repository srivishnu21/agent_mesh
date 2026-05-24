import type { Agent, AgentCreate, Conversation, DashboardStats, Message, Model, Run, RunEvent, Tool, Workflow, WorkflowCreate } from "./types";

/**
 * Resolve the backend base URL.
 *
 * Priority:
 *  1. `NEXT_PUBLIC_API_URL` — baked at build time (use for prod with fixed host).
 *  2. Runtime: derive from `window.location` so the browser hits the same host
 *     on port 8000. Lets a single image work on localhost, a VM external IP,
 *     or any reverse-proxied hostname without rebuilding.
 *  3. SSR fallback: `http://backend:8000` (Docker network) for any server-side
 *     fetch during Next.js render.
 */
function resolveApiUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) return envUrl;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://backend:8000";
}

export const API_URL = resolveApiUrl();

export const TOKEN_KEY = "am_token";
export const USER_KEY = "am_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setSession(token: string, username: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, username);
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...init?.headers
    }
  });

  if (response.status === 401) {
    clearSession();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new Error("401 Unauthorized");
  }

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
  authStatus: () => request<{ enabled: boolean }>("/api/v1/auth/status"),
  login: (username: string, password: string) =>
    request<{ token: string; username: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    }),
  me: () => request<{ username: string }>("/api/v1/auth/me"),
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
  updateWorkflow: (id: string, payload: Partial<WorkflowCreate>) => request<Workflow>(`/api/v1/workflows/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteWorkflow: (id: string, params: { force?: boolean } = {}) =>
    request<void>(`/api/v1/workflows/${id}${qs(params)}`, { method: "DELETE" }),
  runWorkflow: (id: string, input: string) => request<{ run_id: string }>(`/api/v1/workflows/${id}/run`, { method: "POST", body: JSON.stringify({ input }) }),
  triggerRun: (workflowId: string, input: string) => request<{ run_id: string }>(`/api/v1/workflows/${workflowId}/run`, { method: "POST", body: JSON.stringify({ input }) }),
  listRuns: (params: { workflow_id?: string; status?: string; limit?: number; offset?: number } = {}) => request<Run[]>(`/api/v1/runs${qs(params)}`),
  getRun: (id: string) => request<Run & { events: RunEvent[] }>(`/api/v1/runs/${id}`),
  listRunEvents: (id: string, params: { limit?: number; offset?: number } = {}) => request<RunEvent[]>(`/api/v1/runs/${id}/events${qs(params)}`),
  listConversations: (params: { channel?: string; limit?: number; offset?: number } = {}) => request<Conversation[]>(`/api/v1/conversations${qs(params)}`),
  getConversation: (id: string) => request<Conversation & { messages: Message[] }>(`/api/v1/conversations/${id}`),
  listMessages: (id: string, params: { limit?: number; offset?: number } = {}) => request<Message[]>(`/api/v1/conversations/${id}/messages${qs(params)}`),
  dashboardStats: () => request<DashboardStats>("/api/v1/stats/dashboard"),
  telegramWebhook: (payload: Record<string, unknown>) => request<{ ok: boolean; conversation_id: string | null; message_id: string | null }>("/api/v1/telegram/webhook", { method: "POST", body: JSON.stringify(payload) })
};

export const wsRunUrl = (runId: string) => {
  const token = getToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${API_URL.replace(/^http/, "ws")}/ws/runs/${runId}${query}`;
};

export async function triggerRun(workflowId: string, input: string) {
  return api.triggerRun(workflowId, input);
}

export async function getRunEvents(runId: string) {
  return api.listRunEvents(runId);
}
