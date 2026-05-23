"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Bot, Coins, Workflow } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";

const metricIcons = { Agents: Bot, Workflows: Workflow, "Runs today": Activity, "Tokens today": Coins };

export default function DashboardPage() {
  const stats = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboardStats,
    throwOnError: false
  });

  useEffect(() => {
    if (stats.error) toast.error(stats.error.message);
  }, [stats.error]);

  const metrics = [
    ["Agents", stats.data?.agents ?? 0],
    ["Workflows", stats.data?.workflows ?? 0],
    ["Runs today", stats.data?.runs_today ?? 0],
    ["Tokens today", (stats.data?.tokens_today ?? 0).toLocaleString()]
  ] as const;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="grid gap-3 md:grid-cols-4">
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
