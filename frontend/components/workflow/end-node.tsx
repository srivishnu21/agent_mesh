import { Handle, Position } from "reactflow";
import { CircleCheckBig } from "lucide-react";

import { cn } from "@/lib/utils";

export const END_NODE_ID = "__END__";
export const END_ALIASES = new Set(["end", "__end__", "exit", "finish", "done"]);

export function EndNode({ selected }: { selected: boolean }) {
  return (
    <div
      className={cn(
        "flex min-w-[120px] items-center justify-center gap-2 rounded-full border-2 px-4 py-2 text-xs font-bold uppercase tracking-wide shadow-sm",
        selected ? "border-orange-500 bg-orange-100 text-orange-900" : "border-orange-300 bg-orange-50 text-orange-800"
      )}
    >
      <Handle type="target" position={Position.Left} />
      <CircleCheckBig className="h-3.5 w-3.5" />
      <span>END</span>
    </div>
  );
}
