"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Circle,
  MessageCircleMore,
  MessageSquare,
  Package,
  Play,
  Trophy,
  Wrench
} from "lucide-react";

import { api, wsRunUrl } from "@/lib/api-client";
import type { RunEvent } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";

const eventMeta = {
  run_started: { icon: Play, color: "text-emerald-600", label: "Run started" },
  node_started: { icon: Circle, color: "text-blue-600", label: "Node started" },
  llm_call: { icon: MessageSquare, color: "text-violet-600", label: "LLM call" },
  agent_message: { icon: MessageCircleMore, color: "text-violet-600", label: "Agent message" },
  tool_call: { icon: Wrench, color: "text-amber-600", label: "Tool call" },
  tool_result: { icon: Package, color: "text-amber-600", label: "Tool result" },
  node_completed: { icon: CheckCircle2, color: "text-emerald-600", label: "Node completed" },
  run_completed: { icon: Trophy, color: "text-emerald-600", label: "Run completed" },
  error: { icon: AlertCircle, color: "text-red-600", label: "Error" }
};

function costValue(value: unknown) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function triggerInput(run: Awaited<ReturnType<typeof api.getRun>> | null) {
  const trigger = run?.trigger as { payload?: { input?: unknown }; input?: unknown } | undefined;
  return String(trigger?.payload?.input ?? trigger?.input ?? "");
}

function payloadText(event: RunEvent) {
  const payload = event.payload as Record<string, unknown>;
  if (event.event_type === "agent_message") return String(payload.content ?? "");
  if (event.event_type === "tool_call") return `${payload.tool}(${JSON.stringify(payload.args ?? {})})`;
  if (event.event_type === "tool_result") return String(payload.result ?? "");
  if (event.event_type === "llm_call") return `${payload.agent_name ?? "Agent"} iteration ${payload.iteration ?? ""}`;
  if (event.event_type === "node_started" || event.event_type === "node_completed") return String(payload.agent_name ?? "");
  if (event.event_type === "run_started") return String(payload.workflow_name ?? "");
  if (event.event_type === "run_completed") return String(payload.final_message ?? "");
  if (event.event_type === "error") return String(payload.message ?? "");
  return JSON.stringify(payload);
}

export default function RunDetailPage({ params }: { params: { id: string } }) {
  const [run, setRun] = useState<Awaited<ReturnType<typeof api.getRun>> | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mounted = true;
    api.getRun(params.id).then((data) => {
      if (!mounted) return;
      setRun(data);
      setEvents(data.events ?? []);
    });
    api.listRunEvents(params.id).then((data) => mounted && setEvents(data));

    const socket = new WebSocket(wsRunUrl(params.id));
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as RunEvent;
      setEvents((previous) => {
        if (previous.some((item) => item.id === event.id)) return previous;
        return [...previous, event];
      });
      if (event.event_type === "run_completed" || event.event_type === "error") {
        api.getRun(params.id).then(setRun);
      }
    };
    return () => {
      mounted = false;
      socket.close();
    };
  }, [params.id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [events]);

  const totals = useMemo(
    () => ({
      tokens: events.reduce((sum, event) => sum + (event.tokens ?? 0), 0),
      cost: events.reduce((sum, event) => sum + costValue(event.cost_usd), 0)
    }),
    [events]
  );
  const runStarted = events.find((event) => event.event_type === "run_started");
  const workflowName = String((runStarted?.payload as Record<string, unknown> | undefined)?.workflow_name ?? run?.workflow_id ?? "Workflow");
  const input = triggerInput(run);
  const toolUsage = useMemo(() => {
    const rows: Array<{ call: RunEvent; result?: RunEvent }> = [];
    const pendingByTool = new Map<string, RunEvent[]>();

    events.forEach((event) => {
      const payload = event.payload as Record<string, unknown>;
      if (event.event_type === "tool_call") {
        const tool = String(payload.tool ?? "tool");
        const list = pendingByTool.get(tool) ?? [];
        list.push(event);
        pendingByTool.set(tool, list);
        rows.push({ call: event });
      }
      if (event.event_type === "tool_result") {
        const tool = String(payload.tool ?? "tool");
        const list = pendingByTool.get(tool) ?? [];
        const call = list.shift();
        if (call) {
          const row = rows.find((item) => item.call.id === call.id);
          if (row) row.result = event;
        }
      }
    });

    return rows;
  }, [events]);

  function toggleExpanded(eventId: string) {
    setExpandedEvents((current) => {
      const next = new Set(current);
      if (next.has(eventId)) next.delete(eventId);
      else next.add(eventId);
      return next;
    });
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="truncate">Run {params.id}</CardTitle>
              {run && <StatusBadge status={run.status} />}
              <Badge className={connected ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-50 text-slate-700"}>
                {connected ? "Live" : "Disconnected"}
              </Badge>
            </div>
            <div className="text-sm text-muted-foreground">Workflow: {workflowName}</div>
            {input && <div className="max-w-4xl text-sm">Input: &quot;{input}&quot;</div>}
          </div>
          <div className="shrink-0 text-right text-sm">
            <div>Tokens: {(run?.total_tokens || totals.tokens).toLocaleString()}</div>
            <div>Cost: ${(Number(run?.total_cost_usd ?? totals.cost) || totals.cost).toFixed(4)}</div>
          </div>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tool Usage</CardTitle>
        </CardHeader>
        <CardContent>
          {toolUsage.length ? (
            <div className="space-y-3">
              {toolUsage.map(({ call, result }) => {
                const callPayload = call.payload as Record<string, unknown>;
                const resultPayload = (result?.payload ?? {}) as Record<string, unknown>;
                return (
                  <div key={call.id} className="rounded-lg border bg-card p-3">
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <Wrench className="h-4 w-4 text-amber-600" />
                      <span className="font-medium">{String(callPayload.tool ?? "tool")}</span>
                      <span className="font-mono text-xs text-muted-foreground">{new Date(call.created_at).toLocaleTimeString()}</span>
                      <Badge className={result ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700"}>
                        {result ? "completed" : "pending"}
                      </Badge>
                    </div>
                    <div className="mt-2 grid gap-2 text-xs md:grid-cols-2">
                      <div>
                        <div className="mb-1 font-medium">Arguments</div>
                        <pre className="max-h-56 overflow-auto rounded-md bg-muted p-2">{JSON.stringify(callPayload.args ?? {}, null, 2)}</pre>
                      </div>
                      <div>
                        <div className="mb-1 font-medium">Result</div>
                        <pre className="max-h-56 overflow-auto rounded-md bg-muted p-2 whitespace-pre-wrap">{String(resultPayload.result ?? "Waiting for result...")}</pre>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed bg-muted/30 p-4 text-sm text-muted-foreground">
              No tool calls were recorded for this run. The model answered directly without invoking an assigned tool.
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Event Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea ref={scrollRef} className="max-h-[640px] pr-2">
            <div className="space-y-3">
              {events.map((event) => {
                const meta = eventMeta[event.event_type as keyof typeof eventMeta] ?? eventMeta.agent_message;
                const Icon = meta.icon;
                const text = payloadText(event);
                const payload = JSON.stringify(event.payload, null, 2);
                const isExpanded = expandedEvents.has(event.id);
                const shouldCollapse = text.length > 400;
                const visibleText = shouldCollapse && !isExpanded ? `${text.slice(0, 400)}...` : text;
                return (
                  <div key={event.id} className="rounded-lg border bg-card p-3">
                    <div className="flex items-start gap-3">
                      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", meta.color)} />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2 text-sm">
                          <span className="font-mono text-xs text-muted-foreground">{new Date(event.created_at).toLocaleTimeString()}</span>
                          <span className="font-medium">{event.event_type}</span>
                          <span className="text-muted-foreground">{meta.label}</span>
                        </div>
                        {text && <div className="mt-2 whitespace-pre-wrap text-sm">{visibleText}</div>}
                        {shouldCollapse && (
                          <button className="mt-1 text-xs font-medium text-primary hover:underline" onClick={() => toggleExpanded(event.id)}>
                            {isExpanded ? "Show less" : "Show full text"}
                          </button>
                        )}
                        <details className="mt-2 text-xs text-muted-foreground">
                          <summary className="cursor-pointer">Full payload</summary>
                          <pre className="mt-2 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-2 text-foreground">{payload}</pre>
                        </details>
                      </div>
                    </div>
                  </div>
                );
              })}
              {!events.length && <div className="py-8 text-center text-sm text-muted-foreground">Waiting for run events...</div>}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
