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
export type Conversation = components["schemas"]["Conversation"];
export type Message = components["schemas"]["Message"];
export type Tool = components["schemas"]["Tool"];
export type Model = components["schemas"]["Model"];
