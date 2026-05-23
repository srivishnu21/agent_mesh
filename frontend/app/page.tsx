"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Bot, Coins, DollarSign, Workflow } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";

const metricIcons = {
  Agents: Bot,
  Workflows: Workflow,
  "Runs today": Activity,
  "Tokens today": Coins,
  "Cost today": DollarSign
};

export default function DashboardPage() {
  const stats = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboardStats,
    throwOnError: false,
    refetchInterval: 15000
  });

  useEffect(() => {
    if (stats.error) toast.error(stats.error.message);
  }, [stats.error]);

  const metrics = [
    ["Agents", stats.data?.agents ?? 0],
    ["Workflows", stats.data?.workflows ?? 0],
    ["Runs today", stats.data?.runs_today ?? 0],
    ["Tokens today", (stats.data?.tokens_today ?? 0).toLocaleString()],
    ["Cost today", `$${Number(stats.data?.cost_today_usd ?? 0).toFixed(4)}`]
  ] as const;

  const trend = stats.data?.cost_trend ?? [];
  const maxTokens = useMemo(() => Math.max(1, ...trend.map((p) => p.tokens || 0)), [trend]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="grid gap-3 md:grid-cols-5">
        {metrics.map(([label, value]) => {
          const Icon = metricIcons[label];
          return (
            <Card key={label}>
              <CardContent className="flex items-center justify-between p-4">
                <div>
                  <div className="text-sm text-muted-foreground">{label}</div>
                  {stats.isLoading ? <Skeleton className="mt-2 h-7 w-16" /> : <div className="text-2xl font-semibold">{value}</div>}
                </div>
                <Icon className="h-5 w-5 text-muted-foreground" />
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Token usage (last 7 days)</CardTitle>
          </CardHeader>
          <CardContent>
            {stats.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : trend.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">No runs yet.</p>
            ) : (
              <div className="flex h-32 items-end gap-2">
                {trend.map((point) => {
                  const heightPct = Math.round(((point.tokens || 0) / maxTokens) * 100);
                  const label = new Date(point.date).toLocaleDateString(undefined, { month: "short", day: "numeric" });
                  return (
                    <div key={point.date} className="flex flex-1 flex-col items-center gap-1">
                      <div
                        className="w-full rounded-t bg-primary/70 transition-all"
                        style={{ height: `${Math.max(heightPct, 2)}%` }}
                        title={`${point.tokens.toLocaleString()} tokens · ${point.runs} runs · $${Number(point.cost_usd).toFixed(4)}`}
                      />
                      <div className="text-[10px] text-muted-foreground">{label}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Spend by agent (last 7 days)</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <THead>
                <TR>
                  <TH>Agent</TH>
                  <TH>Runs</TH>
                  <TH>Tokens</TH>
                  <TH>Cost</TH>
                </TR>
              </THead>
              <TBody>
                {stats.isLoading && (
                  <TR>
                    <TD colSpan={4}>
                      <Skeleton className="h-6 w-full" />
                    </TD>
                  </TR>
                )}
                {stats.data?.agent_cost?.map((row) => (
                  <TR key={row.agent_id ?? row.agent_name}>
                    <TD>{row.agent_name}</TD>
                    <TD>{row.runs}</TD>
                    <TD>{row.tokens.toLocaleString()}</TD>
                    <TD>${Number(row.cost_usd).toFixed(4)}</TD>
                  </TR>
                ))}
                {!stats.isLoading && !stats.data?.agent_cost?.length && (
                  <TR>
                    <TD colSpan={4} className="py-6 text-center text-muted-foreground">
                      No agent spend recorded yet.
                    </TD>
                  </TR>
                )}
              </TBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <THead>
              <TR>
                <TH>Workflow</TH>
                <TH>Status</TH>
                <TH>Started</TH>
                <TH>Tokens</TH>
                <TH>Cost</TH>
              </TR>
            </THead>
            <TBody>
              {stats.isLoading &&
                Array.from({ length: 5 }).map((_, index) => (
                  <TR key={index}>
                    <TD colSpan={5}>
                      <Skeleton className="h-6 w-full" />
                    </TD>
                  </TR>
                ))}
              {stats.data?.recent_runs.map((run) => (
                <TR key={run.id} className="hover:bg-muted/60">
                  <TD>
                    <Link className="block font-medium text-primary" href={`/runs/${run.id}`}>
                      {run.workflow_name}
                    </Link>
                  </TD>
                  <TD>
                    <StatusBadge status={run.status} />
                  </TD>
                  <TD>{run.started_at ? new Date(run.started_at).toLocaleString() : "Pending"}</TD>
                  <TD>{run.total_tokens.toLocaleString()}</TD>
                  <TD>${Number(run.total_cost_usd).toFixed(4)}</TD>
                </TR>
              ))}
              {!stats.isLoading && !stats.data?.recent_runs.length && (
                <TR>
                  <TD colSpan={5} className="py-8 text-center text-muted-foreground">
                    Run a workflow to populate the dashboard.
                  </TD>
                </TR>
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
