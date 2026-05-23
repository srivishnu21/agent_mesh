import { Handle, Position } from "reactflow";

import type { Agent } from "@/lib/types";
import { cn } from "@/lib/utils";

export function AgentNode({ data, selected }: { data: { agent?: Agent }; selected: boolean }) {
  const agent = data.agent;
  return (
    <div className={cn("min-w-[190px] rounded-md border-2 bg-white p-3 shadow-sm", selected ? "border-primary" : "border-border")}>
      <Handle type="target" position={Position.Left} />
      <div className="text-sm font-semibold">{agent?.name ?? "Missing agent"}</div>
      <div className="mt-1 max-w-[180px] text-xs text-muted-foreground">{agent?.role ?? "Agent config unavailable"}</div>
      {!!agent?.tools?.length && (
        <div className="mt-2 flex flex-wrap gap-1">
          {agent.tools.map((tool) => (
            <span key={tool} className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-800">
              {tool}
            </span>
          ))}
        </div>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
