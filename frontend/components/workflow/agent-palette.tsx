import { GripVertical } from "lucide-react";

import type { Agent } from "@/lib/types";

export function AgentPalette({ agents }: { agents: Agent[] }) {
  return (
    <div className="space-y-2">
      {agents.map((agent) => (
        <div
          key={agent.id}
          draggable
          onDragStart={(event) => event.dataTransfer.setData("application/agent-id", agent.id)}
          className="flex cursor-grab items-start gap-2 rounded-md border bg-card p-2 text-sm active:cursor-grabbing"
        >
          <GripVertical className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <div className="font-medium">{agent.name}</div>
            <div className="line-clamp-2 text-xs text-muted-foreground">{agent.role}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
