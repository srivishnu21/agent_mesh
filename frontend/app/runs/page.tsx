"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api-client";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";

export default function RunsPage() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api.listRuns() });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Runs</h1>
      <Card>
        <CardContent className="p-0">
          <Table>
            <THead>
              <TR>
                <TH>Run</TH>
                <TH>Status</TH>
                <TH>Tokens</TH>
                <TH>Cost</TH>
              </TR>
            </THead>
            <TBody>
              {runs.isLoading &&
                Array.from({ length: 5 }).map((_, index) => (
                  <TR key={index}>
                    <TD colSpan={4}>
                      <Skeleton className="h-6 w-full" />
                    </TD>
                  </TR>
                ))}
              {runs.data?.map((run) => (
                <TR key={run.id} className="hover:bg-muted/60">
                  <TD>
                    <Link className="block font-medium text-primary" href={`/runs/${run.id}`}>
                      {run.id}
                    </Link>
                  </TD>
                  <TD>
                    <Link href={`/runs/${run.id}`}>
                      <StatusBadge status={run.status} />
                    </Link>
                  </TD>
                  <TD>
                    <Link className="block" href={`/runs/${run.id}`}>
                      {run.total_tokens}
                    </Link>
                  </TD>
                  <TD>
                    <Link className="block" href={`/runs/${run.id}`}>
                      ${Number(run.total_cost_usd).toFixed(4)}
                    </Link>
                  </TD>
                </TR>
              ))}
              {!runs.isLoading && !runs.data?.length && (
                <TR>
                  <TD colSpan={4}>
                    <EmptyState icon={Activity} message="No runs yet. Start a workflow to see live events." />
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
