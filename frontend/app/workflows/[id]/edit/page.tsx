"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
  type EdgeChange
} from "reactflow";
import "reactflow/dist/style.css";
import { ArrowLeft, GitBranch, Play, RefreshCcw, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AgentNode } from "@/components/workflow/agent-node";
import { AgentPalette } from "@/components/workflow/agent-palette";
import { NodeInspector } from "@/components/workflow/node-inspector";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api-client";
import type { Agent, AgentCreate, Model, Workflow } from "@/lib/types";
import { cn } from "@/lib/utils";

const FEEDBACK_EDGE_PREFIX = "__workflow_feedback_edge__";

const nodeTypes = { agent: AgentNode };
type AgentNodeData = { agent?: Agent; flowRole?: "start" | "end" | "start_end" };
const customAgentDefaults: AgentCreate = {
  name: "",
  role: "",
  system_prompt: "",
  model: "gpt-5-nano",
  tools: ["web_search"],
  config: { temperature: 0.2, memory_enabled: true },
  channels: ["internal"]
};

function validateGraph(nodes: Node[], edges: Edge[]) {
  if (!nodes.length) return "Add at least one agent node before saving.";
  const incoming = new Set(edges.map((edge) => edge.target));
  const sources = nodes.filter((node) => !incoming.has(node.id));
  if (sources.length !== 1) return "Workflow must have exactly one source node.";
  const orphan = nodes.find((node) => node.id !== sources[0].id && !incoming.has(node.id));
  if (orphan) return "Every non-source node needs an incoming edge.";
  return null;
}

function feedbackEdgeId(source: string, target: string) {
  return `${FEEDBACK_EDGE_PREFIX}${source}__${target}`;
}

function isFeedbackEdgeChange(change: EdgeChange) {
  return "id" in change && change.id.startsWith(FEEDBACK_EDGE_PREFIX);
}

function feedbackEdge(source: string, target: string): Edge {
  const isBackward = source > target;
  return {
    id: feedbackEdgeId(source, target),
    source,
    target,
    animated: true,
    label: "feedback",
    type: "smoothstep",
    style: { strokeDasharray: "7 5", stroke: "#8b5cf6", strokeWidth: 2 },
    labelStyle: { fill: "#6d28d9", fontSize: 11, fontWeight: 600 },
    labelBgStyle: { fill: "#faf5ff", fillOpacity: 0.92 },
    pathOptions: { offset: isBackward ? 42 : 28 }
  };
}

export default function WorkflowEditor({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [nodes, setNodes] = useState<Node<AgentNodeData>[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [feedbackEdges, setFeedbackEdges] = useState<Edge[]>([]);
  const [connectionMode, setConnectionMode] = useState<"run" | "feedback">("run");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [runOpen, setRunOpen] = useState(false);
  const [runInput, setRunInput] = useState("");
  const [running, setRunning] = useState(false);
  const [agentOpen, setAgentOpen] = useState(false);
  const [agentForm, setAgentForm] = useState<AgentCreate>(customAgentDefaults);
  const [creatingAgent, setCreatingAgent] = useState(false);

  useEffect(() => {
    Promise.all([api.getWorkflow(params.id), api.listAgents(), api.listModels()])
      .then(([loadedWorkflow, loadedAgents, loadedModels]) => {
        setWorkflow(loadedWorkflow);
        setAgents(loadedAgents);
        setModels(loadedModels);
        const graph = loadedWorkflow.graph as {
          nodes?: Array<{ id: string; agent_id: string; position?: { x: number; y: number } }>;
          edges?: Array<{ from: string; to: string }>;
          ui?: {
            feedback_edges?: Array<{ from: string; to: string }>;
          };
        };
        const hydratedNodes = (graph.nodes ?? []).map((node, index) => ({
            id: node.id,
            type: "agent",
            position: node.position ?? { x: 120 + index * 260, y: 140 },
            data: { agent: loadedAgents.find((agent) => agent.id === node.agent_id) }
          }));
        const hydratedEdges = (graph.edges ?? []).map((edge) => ({ id: `${edge.from}-${edge.to}`, source: edge.from, target: edge.to, animated: true }));
        const hydratedFeedbackEdges = (graph.ui?.feedback_edges ?? []).map((edge) => feedbackEdge(edge.from, edge.to));

        setNodes(hydratedNodes);
        setEdges(hydratedEdges);
        setFeedbackEdges(hydratedFeedbackEdges);
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "Could not load workflow"));
  }, [params.id]);

  const selectedNode = useMemo(() => nodes.find((node) => node.id === selectedNodeId) ?? null, [nodes, selectedNodeId]);
  const displayNodes = useMemo<Node<AgentNodeData>[]>(() => {
    const incoming = new Set(edges.map((edge) => edge.target));
    const outgoing = new Set(edges.map((edge) => edge.source));

    return nodes.map((node) => {
      const isStart = !incoming.has(node.id);
      const isEnd = !outgoing.has(node.id);
      const flowRole = isStart && isEnd ? "start_end" : isStart ? "start" : isEnd ? "end" : undefined;
      return { ...node, data: { ...node.data, flowRole } };
    });
  }, [edges, nodes]);
  const displayEdges = useMemo<Edge[]>(() => [...feedbackEdges, ...edges], [edges, feedbackEdges]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    if (!changes.length) return;
    setNodes((current) => applyNodeChanges(changes, current));
    setDirty(true);
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    const feedbackChanges = changes.filter(isFeedbackEdgeChange);
    const realEdgeChanges = changes.filter((change) => !isFeedbackEdgeChange(change));
    if (feedbackChanges.length) setFeedbackEdges((current) => applyEdgeChanges(feedbackChanges, current));
    if (!realEdgeChanges.length && feedbackChanges.length) {
      setDirty(true);
      return;
    }
    if (!realEdgeChanges.length) return;
    setEdges((current) => applyEdgeChanges(realEdgeChanges, current));
    setDirty(true);
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target) return;

    if (connectionMode === "feedback") {
      const edge = feedbackEdge(connection.source, connection.target);
      setFeedbackEdges((current) => addEdge(edge, current.filter((item) => item.id !== edge.id)));
      setDirty(true);
      return;
    }

    setEdges((current) => addEdge({ ...connection, id: `${connection.source}-${connection.target}`, animated: true }, current));
    setDirty(true);
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const agentId = event.dataTransfer.getData("application/agent-id");
      const toolName = event.dataTransfer.getData("application/tool-name");
      if (toolName) {
        const bounds = event.currentTarget.getBoundingClientRect();
        const x = event.clientX - bounds.left;
        const y = event.clientY - bounds.top;
        const droppedNode = nodes.find((node) => {
          const width = 220;
          const height = 120;
          return x >= node.position.x && x <= node.position.x + width && y >= node.position.y && y <= node.position.y + height;
        });
        const selectedNode = nodes.find((node) => node.id === selectedNodeId);
        const target = droppedNode ?? selectedNode ?? (nodes.length === 1 ? nodes[0] : null);
        if (!target?.data.agent) {
          toast.error("Select an agent or drop the tool onto one.");
          return;
        }
        const agent = target.data.agent;
        if (agent.tools.includes(toolName)) {
          toast.info(`${agent.name} already has ${toolName}`);
          return;
        }
        const updatedAgent = { ...agent, tools: [...agent.tools, toolName] };
        setAgents((current) => current.map((item) => (item.id === agent.id ? updatedAgent : item)));
        setNodes((current) => current.map((node) => (node.id === target.id ? { ...node, data: { agent: updatedAgent } } : node)));
        api.updateAgent(agent.id, { tools: updatedAgent.tools }).catch((error) => toast.error(error instanceof Error ? error.message : "Could not update agent tools"));
        toast.success(`Added ${toolName} to ${agent.name}`);
        setDirty(true);
        return;
      }
      const agent = agents.find((item) => item.id === agentId);
      if (!agent) return;
      const bounds = event.currentTarget.getBoundingClientRect();
      const id = `${agent.id}-${Date.now()}`;
      setNodes((current) => [
        ...current,
        {
          id,
          type: "agent",
          position: { x: event.clientX - bounds.left - 95, y: event.clientY - bounds.top - 40 },
          data: { agent }
        }
      ]);
      setSelectedNodeId(id);
      setDirty(true);
    },
    [agents, nodes, selectedNodeId]
  );

  async function createCustomAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreatingAgent(true);
    try {
      const created = await api.createAgent(agentForm);
      setAgents((current) => [...current, created]);
      setAgentForm({ ...customAgentDefaults, name: "", role: "", system_prompt: "" });
      setAgentOpen(false);
      toast.success("Agent created. Drag it onto the canvas.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create agent");
    } finally {
      setCreatingAgent(false);
    }
  }

  function toggleAgentTool(tool: string) {
    setAgentForm((current) => ({
      ...current,
      tools: current.tools.includes(tool) ? current.tools.filter((item) => item !== tool) : [...current.tools, tool]
    }));
  }

  async function save() {
    const validation = validateGraph(nodes, edges);
    if (validation) {
      toast.error(validation);
      return;
    }
    if (!workflow) return;
    const { markers: _markers, marker_edges: _markerEdges, ...ui } = ((workflow.graph as { ui?: Record<string, unknown> }).ui ?? {}) as Record<string, unknown>;
    const graph = {
      nodes: nodes.map((node) => ({ id: node.id, agent_id: node.data.agent?.id, position: node.position })),
      edges: edges.map((edge) => ({ from: edge.source, to: edge.target })),
      ui: {
        ...ui,
        feedback_edges: feedbackEdges.map((edge) => ({ from: edge.source, to: edge.target }))
      }
    };
    try {
      const updated = await api.updateWorkflow(workflow.id, {
        name: workflow.name,
        description: workflow.description,
        graph,
        is_template: workflow.is_template
      });
      setWorkflow(updated);
      setDirty(false);
      toast.success("Workflow saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save workflow");
    }
  }

  async function run(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRunning(true);
    try {
      const result = await api.triggerRun(params.id, runInput);
      router.push(`/runs/${result.run_id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not start run");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-48px)] flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button className="border bg-background text-foreground" onClick={() => router.push("/workflows")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Workflows
          </Button>
          <div>
            <h1 className="text-xl font-semibold">{workflow?.name ?? "Workflow editor"}</h1>
            <div className="text-xs text-muted-foreground">{dirty ? "Unsaved changes" : "Saved"}</div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button className="border bg-background text-foreground" onClick={() => setRunOpen(true)}>
            <Play className="mr-2 h-4 w-4" />
            Run
          </Button>
          <div className="flex rounded-md border bg-background p-1">
            <Button
              className={cn("h-8 px-2", connectionMode === "run" ? "" : "bg-background text-foreground")}
              onClick={() => setConnectionMode("run")}
              title="Create executable workflow edges"
            >
              <GitBranch className="mr-1 h-4 w-4" />
              Run path
            </Button>
            <Button
              className={cn("h-8 px-2", connectionMode === "feedback" ? "" : "bg-background text-foreground")}
              onClick={() => setConnectionMode("feedback")}
              title="Create visual feedback-loop edges"
            >
              <RefreshCcw className="mr-1 h-4 w-4" />
              Feedback
            </Button>
          </div>
          <Button onClick={save}>
            <Save className="mr-2 h-4 w-4" />
            Save
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[260px_1fr_300px] gap-3">
        <Card className="overflow-auto p-3">
          <AgentPalette agents={agents} onNewAgent={() => setAgentOpen(true)} />
        </Card>
        <Card className="overflow-hidden">
          <ReactFlow
            nodes={displayNodes}
            edges={displayEdges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            onPaneClick={() => setSelectedNodeId(null)}
            onDrop={onDrop}
            onDragOver={(event) => {
              event.preventDefault();
              event.dataTransfer.dropEffect = "move";
            }}
            fitView
          >
            <Background />
            <MiniMap />
            <Controls />
          </ReactFlow>
        </Card>
        <Card className="overflow-auto p-3">
          <NodeInspector
            workflow={workflow}
            selectedNode={selectedNode}
            edges={edges}
            onWorkflowChange={(patch) => {
              setWorkflow((current) => (current ? { ...current, ...patch } : current));
              setDirty(true);
            }}
            onRemoveNode={(id) => {
              setNodes((current) => current.filter((node) => node.id !== id));
              setEdges((current) => current.filter((edge) => edge.source !== id && edge.target !== id));
              setFeedbackEdges((current) => current.filter((edge) => edge.source !== id && edge.target !== id));
              setSelectedNodeId(null);
              setDirty(true);
            }}
          />
        </Card>
      </div>

      <Dialog open={runOpen} onOpenChange={setRunOpen} title={`Run ${workflow?.name ?? "workflow"}`}>
        <form className="space-y-4" onSubmit={run}>
          <label className="space-y-1 text-sm">
            <span>Input</span>
            <Textarea value={runInput} onChange={(event) => setRunInput(event.target.value)} required />
          </label>
          <div className="flex justify-end gap-2">
            <Button type="button" className="border bg-background text-foreground" onClick={() => setRunOpen(false)}>
              Cancel
            </Button>
            <Button disabled={running || !runInput.trim()}>{running ? "Starting..." : "Start run"}</Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={agentOpen} onOpenChange={setAgentOpen} title="Custom agent">
        <form className="space-y-4" onSubmit={createCustomAgent}>
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1 text-sm">
              <span>Name</span>
              <Input value={agentForm.name} onChange={(event) => setAgentForm({ ...agentForm, name: event.target.value })} required />
            </label>
            <label className="space-y-1 text-sm">
              <span>Model</span>
              <Select value={agentForm.model} onChange={(event) => setAgentForm({ ...agentForm, model: event.target.value })} required>
                {models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.display_name}
                  </option>
                ))}
              </Select>
            </label>
          </div>
          <label className="space-y-1 text-sm">
            <span>Role</span>
            <Input value={agentForm.role} onChange={(event) => setAgentForm({ ...agentForm, role: event.target.value })} required />
          </label>
          <label className="space-y-1 text-sm">
            <span>System prompt</span>
            <Textarea className="min-h-56" value={agentForm.system_prompt} onChange={(event) => setAgentForm({ ...agentForm, system_prompt: event.target.value })} required />
          </label>
          <div className="space-y-2 text-sm">
            <span>Tools</span>
            <div className="grid grid-cols-2 gap-2">
              {["web_search", "sql_query", "order_lookup", "send_email", "calculator"].map((tool) => (
                <label key={tool} className="flex items-center gap-2 rounded-md border p-2">
                  <input type="checkbox" checked={agentForm.tools.includes(tool)} onChange={() => toggleAgentTool(tool)} />
                  <span>{tool}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" className="border bg-background text-foreground" onClick={() => setAgentOpen(false)}>
              Cancel
            </Button>
            <Button disabled={creatingAgent}>{creatingAgent ? "Creating..." : "Create agent"}</Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
