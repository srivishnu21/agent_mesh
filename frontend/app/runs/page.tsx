"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
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
              {runs.data?.map((run) => (
                <TR key={run.id}>
                  <TD>
                    <Link className="font-medium text-primary" href={`/runs/${run.id}`}>
                      {run.id}
                    </Link>
                  </TD>
                  <TD>
                    <Badge>{run.status}</Badge>
                  </TD>
                  <TD>{run.total_tokens}</TD>
                  <TD>${run.total_cost_usd}</TD>
                </TR>
              ))}
              {!runs.data?.length && (
                <TR>
                  <TD colSpan={4} className="py-8 text-center text-muted-foreground">No runs yet.</TD>
                </TR>
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
