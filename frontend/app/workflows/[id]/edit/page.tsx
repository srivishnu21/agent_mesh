"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange
} from "reactflow";
import "reactflow/dist/style.css";
import { ArrowLeft, Play, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AgentNode } from "@/components/workflow/agent-node";
import { AgentPalette } from "@/components/workflow/agent-palette";
import { EndNode, END_ALIASES, END_NODE_ID } from "@/components/workflow/end-node";
import { NodeInspector, type EdgeData, type WorkflowGraphConfig } from "@/components/workflow/node-inspector";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api-client";
import type { Agent, AgentCreate, Model, Workflow } from "@/lib/types";

const nodeTypes = { agent: AgentNode, end: EndNode };

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

type RawEdge = {
  from: string;
  to: string;
  condition?: { route_equals?: string; always?: boolean } | null;
  label?: string | null;
  ui?: { feedback?: boolean } | null;
};

type RawGraph = {
  nodes?: Array<{ id: string; agent_id: string; position?: { x: number; y: number } }>;
  edges?: RawEdge[];
  config?: WorkflowGraphConfig;
};

const ROUTE_COLOR = "#d97706";
const ALWAYS_COLOR = "#64748b";
const END_COLOR = "#ea580c";
const FEEDBACK_COLOR = "#7c3aed";

function styleForEdge(target: string, condition: EdgeData["condition"], feedback?: boolean) {
  if (feedback) {
    return {
      style: { stroke: FEEDBACK_COLOR, strokeWidth: 2.5, strokeDasharray: "7 5" },
      labelStyle: { fill: FEEDBACK_COLOR, fontWeight: 700, fontSize: 11 },
      labelBgStyle: { fill: "#f5f3ff", fillOpacity: 0.95 },
      markerEnd: { type: MarkerType.ArrowClosed, color: FEEDBACK_COLOR },
      markerStart: { type: MarkerType.ArrowClosed, color: FEEDBACK_COLOR },
      type: "smoothstep" as const
    } as const;
  }
  const toEnd = target === END_NODE_ID;
  if (toEnd) {
    return {
      style: { stroke: END_COLOR, strokeWidth: 2 },
      labelStyle: { fill: END_COLOR, fontWeight: 600, fontSize: 11 },
      labelBgStyle: { fill: "#fff7ed", fillOpacity: 0.95 },
      markerEnd: { type: MarkerType.ArrowClosed, color: END_COLOR }
    } as const;
  }
  if (condition?.route_equals != null) {
    return {
      style: { stroke: ROUTE_COLOR, strokeWidth: 2, strokeDasharray: "6 4" },
      labelStyle: { fill: ROUTE_COLOR, fontWeight: 600, fontSize: 11 },
      labelBgStyle: { fill: "#fffbeb", fillOpacity: 0.95 },
      markerEnd: { type: MarkerType.ArrowClosed, color: ROUTE_COLOR }
    } as const;
  }
  if (condition?.always) {
    return {
      style: { stroke: ALWAYS_COLOR, strokeWidth: 2, strokeDasharray: "4 4" },
      labelStyle: { fill: ALWAYS_COLOR, fontWeight: 600, fontSize: 11 },
      labelBgStyle: { fill: "#f8fafc", fillOpacity: 0.95 },
      markerEnd: { type: MarkerType.ArrowClosed, color: ALWAYS_COLOR }
    } as const;
  }
  return {
    style: { strokeWidth: 2 },
    markerEnd: { type: MarkerType.ArrowClosed }
  } as const;
}

function decorateEdge(edge: Edge<EdgeData>): Edge<EdgeData> {
  const style = styleForEdge(edge.target, edge.data?.condition, edge.data?.feedback);
  return {
    ...edge,
    animated: !edge.data?.condition && edge.target !== END_NODE_ID,
    label: edge.data?.label || undefined,
    ...style
  };
}

function uniqueEdgeId(source: string, target: string, existing: Set<string>) {
  const base = `${source}->${target}`;
  if (!existing.has(base)) return base;
  let counter = 2;
  while (existing.has(`${base}#${counter}`)) counter += 1;
  return `${base}#${counter}`;
}

function validateGraph(nodes: Node<AgentNodeData>[], edges: Edge<EdgeData>[]) {
  const agentNodes = nodes.filter((node) => node.id !== END_NODE_ID);
  if (!agentNodes.length) return "Add at least one agent node before saving.";

  // every agent node must be connected to something (single-node graphs are allowed)
  if (agentNodes.length > 1) {
    for (const node of agentNodes) {
      const touched = edges.some((edge) => edge.source === node.id || edge.target === node.id);
      if (!touched) return `Agent node "${node.data.agent?.name ?? node.id}" is disconnected from the graph.`;
    }
  }

  // catch-all duplicates per source
  const catchAllPerSource = new Map<string, number>();
  for (const edge of edges) {
    if (edge.data?.condition?.always) {
      catchAllPerSource.set(edge.source, (catchAllPerSource.get(edge.source) ?? 0) + 1);
    }
  }
  for (const [source, count] of catchAllPerSource.entries()) {
    if (count > 1) {
      const node = nodes.find((item) => item.id === source);
      return `Agent "${node?.data.agent?.name ?? source}" has more than one catch-all edge. Keep only one.`;
    }
  }

  // empty route_equals
  for (const edge of edges) {
    if (edge.data?.condition?.route_equals != null && !edge.data.condition.route_equals.trim()) {
      return "A conditional edge has an empty ROUTE value. Set the value the source agent emits.";
    }
  }

  return null;
}

export default function WorkflowEditor({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [nodes, setNodes] = useState<Node<AgentNodeData>[]>([]);
  const [edges, setEdges] = useState<Edge<EdgeData>[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [graphConfig, setGraphConfig] = useState<WorkflowGraphConfig>({});
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

        const graph = (loadedWorkflow.graph ?? {}) as RawGraph;
        const rawNodes = graph.nodes ?? [];
        const rawEdges = graph.edges ?? [];

        const hydratedNodes: Node<AgentNodeData>[] = rawNodes.map((node, index) => ({
          id: node.id,
          type: "agent",
          position: node.position ?? { x: 120 + index * 260, y: 140 },
          data: { agent: loadedAgents.find((agent) => agent.id === node.agent_id) }
        }));

        const needsEnd = rawEdges.some((edge) => END_ALIASES.has(String(edge.to).toLowerCase()));
        if (needsEnd) {
          const maxX = hydratedNodes.reduce((max, node) => Math.max(max, node.position.x), 0);
          const avgY = hydratedNodes.length
            ? hydratedNodes.reduce((sum, node) => sum + node.position.y, 0) / hydratedNodes.length
            : 200;
          hydratedNodes.push({
            id: END_NODE_ID,
            type: "end",
            position: { x: maxX + 280, y: avgY },
            data: {}
          });
        }

        const seen = new Set<string>();
        const hydratedEdges: Edge<EdgeData>[] = rawEdges.map((edge) => {
          const isEnd = END_ALIASES.has(String(edge.to).toLowerCase());
          const target = isEnd ? END_NODE_ID : edge.to;
          const condition = edge.condition ?? undefined;
          const data: EdgeData = {
            condition: condition ? { ...condition } : undefined,
            label: edge.label ?? undefined,
            feedback: !!edge.ui?.feedback
          };
          const id = uniqueEdgeId(edge.from, target, seen);
          seen.add(id);
          return decorateEdge({
            id,
            source: edge.from,
            target,
            data
          });
        });

        setNodes(hydratedNodes);
        setEdges(hydratedEdges);
        setGraphConfig(graph.config ?? {});
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "Could not load workflow"));
  }, [params.id]);

  const selectedNode = useMemo(() => nodes.find((node) => node.id === selectedNodeId) ?? null, [nodes, selectedNodeId]);
  const selectedEdge = useMemo(() => edges.find((edge) => edge.id === selectedEdgeId) ?? null, [edges, selectedEdgeId]);

  const displayNodes = useMemo<Node<AgentNodeData>[]>(() => {
    const incoming = new Set(edges.map((edge) => edge.target));
    const outgoing = new Set(edges.map((edge) => edge.source));
    return nodes.map((node) => {
      if (node.id === END_NODE_ID) return node;
      const isStart = !incoming.has(node.id);
      const isEnd = !outgoing.has(node.id);
      const flowRole = isStart && isEnd ? "start_end" : isStart ? "start" : isEnd ? "end" : undefined;
      return { ...node, data: { ...node.data, flowRole } };
    });
  }, [edges, nodes]);

  const displayEdges = useMemo<Edge<EdgeData>[]>(
    () =>
      edges.map((edge) => {
        const selected = edge.id === selectedEdgeId;
        const decorated = decorateEdge(edge);
        if (!selected) return decorated;
        return {
          ...decorated,
          style: { ...(decorated.style ?? {}), strokeWidth: 3, filter: "drop-shadow(0 0 2px rgba(59,130,246,0.55))" }
        };
      }),
    [edges, selectedEdgeId]
  );

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    if (!changes.length) return;
    setNodes((current) => applyNodeChanges(changes, current));
    setDirty(true);
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    if (!changes.length) return;
    setEdges((current) => applyEdgeChanges(changes, current) as Edge<EdgeData>[]);
    setDirty(true);
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    if (!connection.source || !connection.target) return;
    if (connection.source === END_NODE_ID) {
      toast.error("END is terminal — it cannot have outgoing edges.");
      return;
    }
    if (connection.source === connection.target) {
      toast.error("Self-loops aren't supported.");
      return;
    }
    setEdges((current) => {
      const existingIds = new Set(current.map((edge) => edge.id));
      const id = uniqueEdgeId(connection.source!, connection.target!, existingIds);
      const newEdge = decorateEdge({
        id,
        source: connection.source!,
        target: connection.target!,
        data: {}
      });
      const next = addEdge(newEdge, current) as Edge<EdgeData>[];
      setSelectedEdgeId(id);
      return next;
    });
    setDirty(true);
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const bounds = event.currentTarget.getBoundingClientRect();
      const x = event.clientX - bounds.left;
      const y = event.clientY - bounds.top;

      const endNode = event.dataTransfer.getData("application/end-node");
      if (endNode) {
        if (nodes.some((node) => node.id === END_NODE_ID)) {
          toast.info("END node already on the canvas.");
          return;
        }
        setNodes((current) => [
          ...current,
          {
            id: END_NODE_ID,
            type: "end",
            position: { x: x - 60, y: y - 20 },
            data: {}
          }
        ]);
        setSelectedNodeId(END_NODE_ID);
        setDirty(true);
        return;
      }

      const toolName = event.dataTransfer.getData("application/tool-name");
      if (toolName) {
        const droppedNode = nodes.find((node) => {
          if (node.id === END_NODE_ID) return false;
          const width = 220;
          const height = 120;
          return x >= node.position.x && x <= node.position.x + width && y >= node.position.y && y <= node.position.y + height;
        });
        const focused = nodes.find((node) => node.id === selectedNodeId && node.id !== END_NODE_ID);
        const target = droppedNode ?? focused ?? (nodes.filter((node) => node.id !== END_NODE_ID).length === 1 ? nodes.find((node) => node.id !== END_NODE_ID) ?? null : null);
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

      const agentId = event.dataTransfer.getData("application/agent-id");
      const agent = agents.find((item) => item.id === agentId);
      if (!agent) return;
      const id = `${agent.id}-${Date.now()}`;
      setNodes((current) => [
        ...current,
        {
          id,
          type: "agent",
          position: { x: x - 95, y: y - 40 },
          data: { agent }
        }
      ]);
      setSelectedNodeId(id);
      setSelectedEdgeId(null);
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

  function applyEdgeData(id: string, data: EdgeData) {
    setEdges((current) =>
      current.map((edge) => {
        if (edge.id !== id) return edge;
        return decorateEdge({ ...edge, data });
      })
    );
    setDirty(true);
  }

  function removeEdge(id: string) {
    setEdges((current) => current.filter((edge) => edge.id !== id));
    if (selectedEdgeId === id) setSelectedEdgeId(null);
    setDirty(true);
  }

  function removeNode(id: string) {
    setNodes((current) => current.filter((node) => node.id !== id));
    setEdges((current) => current.filter((edge) => edge.source !== id && edge.target !== id));
    if (selectedNodeId === id) setSelectedNodeId(null);
    setDirty(true);
  }

  async function save() {
    const validation = validateGraph(nodes, edges);
    if (validation) {
      toast.error(validation);
      return;
    }
    if (!workflow) return;
    const graph: RawGraph = {
      nodes: nodes
        .filter((node) => node.id !== END_NODE_ID)
        .map((node) => ({ id: node.id, agent_id: node.data.agent?.id ?? "", position: node.position })),
      config: graphConfig,
      edges: edges.map((edge) => {
        const out: RawEdge = {
          from: edge.source,
          to: edge.target === END_NODE_ID ? "END" : edge.target
        };
        const condition = edge.data?.condition;
        if (condition?.always) out.condition = { always: true };
        else if (condition?.route_equals != null) out.condition = { route_equals: condition.route_equals };
        if (edge.data?.label) out.label = edge.data.label;
        if (edge.data?.feedback) out.ui = { feedback: true };
        return out;
      })
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
          <Button onClick={save}>
            <Save className="mr-2 h-4 w-4" />
            Save
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[260px_1fr_320px] gap-3">
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
            onNodeClick={(_, node) => {
              setSelectedNodeId(node.id);
              setSelectedEdgeId(null);
            }}
            onEdgeClick={(_, edge) => {
              setSelectedEdgeId(edge.id);
              setSelectedNodeId(null);
            }}
            onPaneClick={() => {
              setSelectedNodeId(null);
              setSelectedEdgeId(null);
            }}
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
            graphConfig={graphConfig}
            selectedNode={selectedNode}
            selectedEdge={selectedEdge}
            nodes={nodes}
            edges={edges}
            onWorkflowChange={(patch) => {
              setWorkflow((current) => (current ? { ...current, ...patch } : current));
              setDirty(true);
            }}
            onGraphConfigChange={(next) => {
              setGraphConfig(next);
              setDirty(true);
            }}
            onRemoveNode={removeNode}
            onEdgeChange={applyEdgeData}
            onRemoveEdge={removeEdge}
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
