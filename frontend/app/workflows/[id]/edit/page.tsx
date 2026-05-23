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
import { ArrowLeft, Play, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { AgentNode } from "@/components/workflow/agent-node";
import { AgentPalette } from "@/components/workflow/agent-palette";
import { NodeInspector } from "@/components/workflow/node-inspector";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api-client";
import type { Agent, Workflow } from "@/lib/types";

const nodeTypes = { agent: AgentNode };

function validateGraph(nodes: Node[], edges: Edge[]) {
  if (!nodes.length) return "Add at least one agent node before saving.";
  const incoming = new Set(edges.map((edge) => edge.target));
  const sources = nodes.filter((node) => !incoming.has(node.id));
  if (sources.length !== 1) return "Workflow must have exactly one source node.";
  const orphan = nodes.find((node) => node.id !== sources[0].id && !incoming.has(node.id));
  if (orphan) return "Every non-source node needs an incoming edge.";
  return null;
}

export default function WorkflowEditor({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [nodes, setNodes] = useState<Node<{ agent?: Agent }>[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [runOpen, setRunOpen] = useState(false);
  const [runInput, setRunInput] = useState("");
  const [running, setRunning] = useState(false);

  useEffect(() => {
    Promise.all([api.getWorkflow(params.id), api.listAgents()])
      .then(([loadedWorkflow, loadedAgents]) => {
        setWorkflow(loadedWorkflow);
        setAgents(loadedAgents);
        const graph = loadedWorkflow.graph as { nodes?: Array<{ id: string; agent_id: string; position?: { x: number; y: number } }>; edges?: Array<{ from: string; to: string }> };
        setNodes(
          (graph.nodes ?? []).map((node, index) => ({
            id: node.id,
            type: "agent",
            position: node.position ?? { x: 120 + index * 260, y: 140 },
            data: { agent: loadedAgents.find((agent) => agent.id === node.agent_id) }
          }))
        );
        setEdges((graph.edges ?? []).map((edge) => ({ id: `${edge.from}-${edge.to}`, source: edge.from, target: edge.to, animated: true })));
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "Could not load workflow"));
  }, [params.id]);

  const selectedNode = useMemo(() => nodes.find((node) => node.id === selectedNodeId) ?? null, [nodes, selectedNodeId]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((current) => applyNodeChanges(changes, current));
    setDirty(true);
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((current) => applyEdgeChanges(changes, current));
    setDirty(true);
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    setEdges((current) => addEdge({ ...connection, animated: true }, current));
    setDirty(true);
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const agentId = event.dataTransfer.getData("application/agent-id");
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
    [agents]
  );

  async function save() {
    const validation = validateGraph(nodes, edges);
    if (validation) {
      toast.error(validation);
      return;
    }
    if (!workflow) return;
    const graph = {
      nodes: nodes.map((node) => ({ id: node.id, agent_id: node.data.agent?.id, position: node.position })),
      edges: edges.map((edge) => ({ from: edge.source, to: edge.target }))
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

      <div className="grid min-h-0 flex-1 grid-cols-[260px_1fr_300px] gap-3">
        <Card className="overflow-auto p-3">
          <h2 className="mb-3 text-sm font-semibold">Agents</h2>
          <AgentPalette agents={agents} />
        </Card>
        <Card className="overflow-hidden">
          <ReactFlow
            nodes={nodes}
            edges={edges}
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
    </div>
  );
}
