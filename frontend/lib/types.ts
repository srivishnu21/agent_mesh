import type { components } from "./api-types";

type JsonObject = Record<string, unknown>;

export type Agent = components["schemas"]["Agent"] & {
  tools: string[];
  config: JsonObject;
  channels: string[];
};
export type AgentCreate = components["schemas"]["AgentCreate"] & {
  tools: string[];
  config: JsonObject;
  channels: string[];
};
export type Workflow = components["schemas"]["Workflow"];
export type WorkflowCreate = components["schemas"]["WorkflowCreate"];
export type Run = components["schemas"]["Run"];
export type RunEvent = components["schemas"]["RunEvent"];
export type DashboardStats = {
  agents: number;
  workflows: number;
  runs_today: number;
  tokens_today: number;
  recent_runs: Array<{
    id: string;
    workflow_id: string;
    workflow_name: string;
    status: Run["status"];
    started_at: string | null;
    total_tokens: number;
    total_cost_usd: string | number;
  }>;
};
export type Conversation = components["schemas"]["Conversation"] & {
  last_message_preview?: string | null;
  last_message_at?: string | null;
  message_count?: number;
  telegram_user?: JsonObject | null;
};
export type Message = components["schemas"]["Message"];
export type Tool = components["schemas"]["Tool"];
export type Model = components["schemas"]["Model"];
