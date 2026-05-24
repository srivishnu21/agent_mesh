import type { Edge, Node } from "reactflow";
import { Trash2 } from "lucide-react";

import type { Agent, Workflow } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { END_NODE_ID } from "@/components/workflow/end-node";

export type EdgeCondition = { route_equals?: string; always?: boolean };
export type EdgeData = { condition?: EdgeCondition; label?: string; feedback?: boolean };

export type WorkflowGraphConfig = {
  interaction_rules?: {
    max_iterations_per_agent?: number;
    max_total_steps?: number;
  };
  schedule?: {
    enabled?: boolean;
    cron?: string;
    input?: string;
    timezone?: string;
  };
};

const FEEDBACK_DEFAULT_ROUTE = "revise";

type AgentNodeData = { agent?: Agent };

function nodeLabel(node: Node<AgentNodeData> | undefined, fallback: string) {
  if (!node) return fallback;
  if (node.id === END_NODE_ID) return "END";
  return node.data?.agent?.name ?? fallback;
}

export function NodeInspector({
  workflow,
  graphConfig,
  selectedNode,
  selectedEdge,
  nodes,
  onWorkflowChange,
  onGraphConfigChange,
  onRemoveNode,
  onEdgeChange,
  onRemoveEdge
}: {
  workflow: Workflow | null;
  graphConfig: WorkflowGraphConfig;
  selectedNode: Node<AgentNodeData> | null;
  selectedEdge: Edge<EdgeData> | null;
  nodes: Node<AgentNodeData>[];
  edges: Edge<EdgeData>[];
  onWorkflowChange: (patch: Partial<Workflow>) => void;
  onGraphConfigChange: (next: WorkflowGraphConfig) => void;
  onRemoveNode: (id: string) => void;
  onEdgeChange: (id: string, data: EdgeData) => void;
  onRemoveEdge: (id: string) => void;
}) {
  if (selectedEdge) {
    const condition = selectedEdge.data?.condition ?? {};
    const label = selectedEdge.data?.label ?? "";
    const feedback = !!selectedEdge.data?.feedback;
    const sourceNode = nodes.find((node) => node.id === selectedEdge.source);
    const targetNode = nodes.find((node) => node.id === selectedEdge.target);
    const sourceName = nodeLabel(sourceNode, selectedEdge.source);
    const targetName = nodeLabel(targetNode, selectedEdge.target);
    const targetIsEnd = selectedEdge.target === END_NODE_ID;
    const mode: "straight" | "route" | "always" = condition.always
      ? "always"
      : typeof condition.route_equals === "string"
        ? "route"
        : "straight";

    function setMode(value: string) {
      if (value === "straight") onEdgeChange(selectedEdge!.id, { label, condition: undefined, feedback });
      else if (value === "always") onEdgeChange(selectedEdge!.id, { label: label || "default", condition: { always: true }, feedback });
      else onEdgeChange(selectedEdge!.id, { label: label || "route", condition: { route_equals: condition.route_equals ?? "" }, feedback });
    }

    function setRoute(value: string) {
      onEdgeChange(selectedEdge!.id, {
        label: label || value || "route",
        condition: { route_equals: value },
        feedback
      });
    }

    function setLabel(value: string) {
      onEdgeChange(selectedEdge!.id, {
        label: value,
        condition: condition.always || condition.route_equals != null ? condition : undefined,
        feedback
      });
    }

    function toggleFeedback(next: boolean) {
      if (next) {
        // One-click feedback loop: make conditional with sensible defaults.
        const route = condition.route_equals && condition.route_equals.trim() ? condition.route_equals : FEEDBACK_DEFAULT_ROUTE;
        onEdgeChange(selectedEdge!.id, {
          label: label || route,
          condition: { route_equals: route },
          feedback: true
        });
      } else {
        onEdgeChange(selectedEdge!.id, { label, condition, feedback: false });
      }
    }

    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-sm font-semibold">Edge</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            <span className="font-medium">{sourceName}</span> {feedback ? "⇄" : "→"} <span className="font-medium">{targetName}</span>
          </p>
          {targetIsEnd && (
            <p className="mt-1 text-xs text-orange-700">
              Targets END — completes the run when this edge fires.
            </p>
          )}
        </div>
        <label className="flex items-start gap-3 rounded-md border-2 border-purple-200 bg-purple-50 p-3 text-sm">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 accent-purple-600"
            checked={feedback}
            onChange={(event) => toggleFeedback(event.target.checked)}
          />
          <span className="space-y-0.5">
            <span className="block font-semibold text-purple-900">Feedback loop</span>
            <span className="block text-xs text-purple-800">
              One-click loop-back. Renders as double-arrow. Auto-sets edge to conditional with{" "}
              <code className="rounded bg-purple-100 px-1">ROUTE: {condition.route_equals?.trim() || FEEDBACK_DEFAULT_ROUTE}</code>{" "}
              from the source agent.
            </span>
          </span>
        </label>
        <label className="space-y-1 text-sm">
          <span>Edge type</span>
          <Select value={mode} onChange={(event) => setMode(event.target.value)} disabled={feedback}>
            <option value="straight">Straight — always runs after source</option>
            <option value="route">Conditional — match agent ROUTE</option>
            <option value="always">Catch-all — fires when no other route matches</option>
          </Select>
          {feedback && (
            <span className="text-xs text-muted-foreground">Feedback loops are always conditional. Uncheck Feedback to change.</span>
          )}
        </label>
        {mode === "route" && (
          <label className="space-y-1 text-sm">
            <span>Match when ROUTE equals</span>
            <Input
              value={condition.route_equals ?? ""}
              placeholder={feedback ? FEEDBACK_DEFAULT_ROUTE : "billing"}
              onChange={(event) => setRoute(event.target.value)}
            />
            <span className="text-xs text-muted-foreground">
              Source agent must emit a line like <code className="rounded bg-muted px-1">ROUTE: {condition.route_equals?.trim() || (feedback ? FEEDBACK_DEFAULT_ROUTE : "billing")}</code> for this edge to fire.
            </span>
          </label>
        )}
        <label className="space-y-1 text-sm">
          <span>Label</span>
          <Input value={label} placeholder="optional" onChange={(event) => setLabel(event.target.value)} />
          <span className="text-xs text-muted-foreground">Shown on the canvas. Helpful for routing edges.</span>
        </label>
        <Button className="w-full border bg-background text-foreground" onClick={() => onRemoveEdge(selectedEdge.id)}>
          <Trash2 className="mr-2 h-4 w-4" />
          Delete edge
        </Button>
      </div>
    );
  }

  if (selectedNode?.id === END_NODE_ID) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-sm font-semibold">END</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Terminal sink. Any incoming edge that fires here completes the run. Connect from an agent (or a conditional edge) to finish the workflow explicitly — useful when other edges loop back.
          </p>
        </div>
        <Button className="w-full border bg-background text-foreground" onClick={() => onRemoveNode(selectedNode.id)}>
          <Trash2 className="mr-2 h-4 w-4" />
          Remove END
        </Button>
      </div>
    );
  }

  if (selectedNode?.data.agent) {
    const agent = selectedNode.data.agent;
    const skills = (agent.config?.skills as string[] | undefined) ?? [];
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-sm font-semibold">{agent.name}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{agent.role}</p>
        </div>
        <div className="space-y-1 text-xs">
          <div className="font-medium">Model</div>
          <div className="break-all text-muted-foreground">{agent.model}</div>
        </div>
        <div className="space-y-1 text-xs">
          <div className="font-medium">Tools</div>
          <div className="text-muted-foreground">{agent.tools.length ? agent.tools.join(", ") : "None"}</div>
        </div>
        <div className="space-y-1 text-xs">
          <div className="font-medium">Skills</div>
          {skills.length ? (
            <div className="flex flex-wrap gap-1">
              {skills.map((skill) => (
                <span key={skill} className="rounded-full border border-violet-200 bg-violet-50 px-1.5 py-0.5 text-[10px] text-violet-800">
                  {skill}
                </span>
              ))}
            </div>
          ) : (
            <div className="text-muted-foreground">None — set on the agent in /agents.</div>
          )}
        </div>
        <Button className="w-full border bg-background text-foreground" onClick={() => onRemoveNode(selectedNode.id)}>
          <Trash2 className="mr-2 h-4 w-4" />
          Remove node
        </Button>
      </div>
    );
  }

  const rules = graphConfig.interaction_rules ?? {};
  const schedule = graphConfig.schedule ?? {};

  function updateRules(patch: Partial<NonNullable<WorkflowGraphConfig["interaction_rules"]>>) {
    onGraphConfigChange({ ...graphConfig, interaction_rules: { ...rules, ...patch } });
  }
  function updateSchedule(patch: Partial<NonNullable<WorkflowGraphConfig["schedule"]>>) {
    onGraphConfigChange({ ...graphConfig, schedule: { ...schedule, ...patch } });
  }

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold">Workflow</h2>
      <label className="space-y-1 text-sm">
        <span>Name</span>
        <Input value={workflow?.name ?? ""} onChange={(event) => onWorkflowChange({ name: event.target.value })} />
      </label>
      <label className="space-y-1 text-sm">
        <span>Description</span>
        <Textarea value={workflow?.description ?? ""} onChange={(event) => onWorkflowChange({ description: event.target.value })} />
      </label>

      <div className="space-y-2 rounded-md border bg-amber-50/40 p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-amber-800">Interaction rules</div>
        <label className="block space-y-1 text-xs">
          <span className="font-medium">Max iterations per agent</span>
          <Input
            type="number"
            min={1}
            max={20}
            value={rules.max_iterations_per_agent ?? ""}
            placeholder="3"
            onChange={(event) => {
              const value = event.target.value ? Number(event.target.value) : undefined;
              updateRules({ max_iterations_per_agent: value });
            }}
          />
          <span className="text-[10px] text-muted-foreground">How many LLM turns each node may take while handling tool calls. Default 3.</span>
        </label>
        <label className="block space-y-1 text-xs">
          <span className="font-medium">Max total steps</span>
          <Input
            type="number"
            min={1}
            max={200}
            value={rules.max_total_steps ?? ""}
            placeholder="25"
            onChange={(event) => {
              const value = event.target.value ? Number(event.target.value) : undefined;
              updateRules({ max_total_steps: value });
            }}
          />
          <span className="text-[10px] text-muted-foreground">Hard cap on graph node executions. Stops runaway feedback loops. Default 25.</span>
        </label>
      </div>

      <div className="space-y-2 rounded-md border bg-sky-50/40 p-3">
        <div className="flex items-center justify-between">
          <div className="text-xs font-semibold uppercase tracking-wide text-sky-800">Schedule</div>
          <label className="flex items-center gap-1 text-xs">
            <input
              type="checkbox"
              checked={!!schedule.enabled}
              onChange={(event) => updateSchedule({ enabled: event.target.checked })}
            />
            <span>Enabled</span>
          </label>
        </div>
        <label className="block space-y-1 text-xs">
          <span className="font-medium">Cron expression</span>
          <Input
            value={schedule.cron ?? ""}
            placeholder="0 9 * * *"
            onChange={(event) => updateSchedule({ cron: event.target.value })}
          />
          <span className="text-[10px] text-muted-foreground">Standard 5-field cron. Example: <code className="rounded bg-muted px-1">0 9 * * *</code> runs daily at 09:00 in the configured timezone.</span>
        </label>
        <label className="block space-y-1 text-xs">
          <span className="font-medium">Timezone</span>
          <Input
            value={schedule.timezone ?? ""}
            placeholder="UTC"
            onChange={(event) => updateSchedule({ timezone: event.target.value })}
          />
        </label>
        <label className="block space-y-1 text-xs">
          <span className="font-medium">Default input</span>
          <Textarea
            value={schedule.input ?? ""}
            placeholder="Run the daily summary."
            onChange={(event) => updateSchedule({ input: event.target.value })}
          />
          <span className="text-[10px] text-muted-foreground">Text sent as the run input on every scheduled fire.</span>
        </label>
      </div>

      <div className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
        Click any edge on the canvas to edit its condition. Click any node to inspect its agent.
      </div>
    </div>
  );
}
