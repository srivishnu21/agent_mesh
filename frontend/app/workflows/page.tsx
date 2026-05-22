"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";

export default function WorkflowsPage() {
  const workflows = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Workflows</h1>
          <p className="text-sm text-muted-foreground">Builder coming soon.</p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Workflow
        </Button>
      </div>
      <Card>
        <CardContent className="p-0">
          <Table>
            <THead>
              <TR>
                <TH>Name</TH>
                <TH>Description</TH>
                <TH>Type</TH>
              </TR>
            </THead>
            <TBody>
              {workflows.data?.map((workflow) => (
                <TR key={workflow.id}>
                  <TD className="font-medium">{workflow.name}</TD>
                  <TD>{workflow.description}</TD>
                  <TD>{workflow.is_template ? <Badge>Template</Badge> : <Badge>Custom</Badge>}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
