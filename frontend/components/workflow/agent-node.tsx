import { Handle, Position } from "reactflow";

import type { Agent } from "@/lib/types";
import { cn } from "@/lib/utils";

type FlowRole = "start" | "end" | "start_end";

function toolChipClass(tool: string) {
  const colors: Record<string, string> = {
    web_search: "bg-amber-100 text-amber-800",
    sql_query: "bg-orange-100 text-orange-800",
    order_lookup: "bg-yellow-100 text-yellow-800",
    send_email: "bg-rose-100 text-rose-800",
    calculator: "bg-lime-100 text-lime-800"
  };
  return colors[tool] ?? "bg-amber-100 text-amber-800";
}

export function AgentNode({ data, selected }: { data: { agent?: Agent; flowRole?: FlowRole }; selected: boolean }) {
  const agent = data.agent;
  const skills = (agent?.config?.skills as string[] | undefined) ?? [];
  return (
    <div className={cn("min-w-[210px] rounded-md border-2 bg-white p-3 shadow-sm", selected ? "border-primary" : "border-border")}>
      <Handle type="target" position={Position.Left} />
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm font-semibold">{agent?.name ?? "Missing agent"}</div>
        {data.flowRole && (
          <div className="flex shrink-0 gap-1">
            {(data.flowRole === "start" || data.flowRole === "start_end") && (
              <span className="rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[9px] font-bold text-emerald-700">START</span>
            )}
            {(data.flowRole === "end" || data.flowRole === "start_end") && (
              <span className="rounded border border-sky-200 bg-sky-50 px-1.5 py-0.5 text-[9px] font-bold text-sky-700">END</span>
            )}
          </div>
        )}
      </div>
      <div className="mt-1 max-w-[200px] text-xs text-muted-foreground">{agent?.role ?? "Agent config unavailable"}</div>
      {!!agent?.tools?.length && (
        <div className="mt-2 flex flex-wrap gap-1">
          {agent.tools.map((tool) => (
            <span key={tool} className={cn("rounded px-1.5 py-0.5 text-[10px]", toolChipClass(tool))}>
              {tool}
            </span>
          ))}
        </div>
      )}
      {!!skills.length && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {skills.slice(0, 4).map((skill) => (
            <span key={skill} className="rounded-full border border-violet-200 bg-violet-50 px-1.5 py-0.5 text-[10px] text-violet-800">
              {skill}
            </span>
          ))}
          {skills.length > 4 && (
            <span className="text-[10px] text-muted-foreground">+{skills.length - 4}</span>
          )}
        </div>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
