import { Bot, GripVertical, Plus, Search, Send, ShoppingCart, Table2, Wrench } from "lucide-react";

import type { Agent } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const workflowTools = [
  { name: "web_search", label: "Web search", description: "Search current public information.", icon: Search, className: "border-amber-200 bg-amber-50 text-amber-900" },
  { name: "sql_query", label: "SQL query", description: "Query relational business data.", icon: Table2, className: "border-orange-200 bg-orange-50 text-orange-900" },
  { name: "order_lookup", label: "Order lookup", description: "Check order status and tracking.", icon: ShoppingCart, className: "border-yellow-200 bg-yellow-50 text-yellow-900" },
  { name: "send_email", label: "Send email", description: "Draft or send customer updates.", icon: Send, className: "border-rose-200 bg-rose-50 text-rose-900" },
  { name: "calculator", label: "Calculator", description: "Run deterministic arithmetic.", icon: Wrench, className: "border-lime-200 bg-lime-50 text-lime-900" }
];

export function AgentPalette({ agents, onNewAgent }: { agents: Agent[]; onNewAgent: () => void }) {
  return (
    <div className="space-y-5">
      <section className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Agents</h2>
          <Button className="h-8 px-2" onClick={onNewAgent}>
            <Plus className="mr-1 h-4 w-4" />
            Agent
          </Button>
        </div>
        <button
          type="button"
          onClick={onNewAgent}
          className="flex w-full items-start gap-2 rounded-md border border-dashed bg-muted/40 p-2 text-left text-sm hover:bg-muted"
        >
          <Bot className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <span className="min-w-0">
            <span className="block font-medium">Custom agent</span>
            <span className="block text-xs text-muted-foreground">Define a new agent with its own role, prompt, model, and tools.</span>
          </span>
        </button>
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
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Tools</h2>
        {workflowTools.map((tool) => {
          const Icon = tool.icon;
          return (
            <div
              key={tool.name}
              draggable
              onDragStart={(event) => event.dataTransfer.setData("application/tool-name", tool.name)}
              className={cn("flex cursor-grab items-start gap-2 rounded-md border p-2 text-sm active:cursor-grabbing", tool.className)}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="min-w-0">
                <div className="font-medium">{tool.label}</div>
                <div className="line-clamp-2 text-xs text-muted-foreground">{tool.description}</div>
              </div>
            </div>
          );
        })}
        <div className="rounded-md border bg-muted/40 p-2 text-xs text-muted-foreground">
          Drop a tool onto an agent node to add that capability to the agent config.
        </div>
      </section>
    </div>
  );
}
