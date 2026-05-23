import type { Edge, Node } from "reactflow";
import { Trash2 } from "lucide-react";

import type { Agent, Workflow } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export function NodeInspector({
  workflow,
  selectedNode,
  onWorkflowChange,
  onRemoveNode
}: {
  workflow: Workflow | null;
  selectedNode: Node<{ agent?: Agent }> | null;
  edges: Edge[];
  onWorkflowChange: (patch: Partial<Workflow>) => void;
  onRemoveNode: (id: string) => void;
}) {
  if (selectedNode?.data.agent) {
    const agent = selectedNode.data.agent;
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
        <Button className="w-full border bg-background text-foreground" onClick={() => onRemoveNode(selectedNode.id)}>
          <Trash2 className="mr-2 h-4 w-4" />
          Remove node
        </Button>
      </div>
    );
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
    </div>
  );
}
