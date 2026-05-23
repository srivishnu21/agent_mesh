"use client";

import { FormEvent, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { GitBranchPlus, Play, Plus, Settings2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { api } from "@/lib/api-client";
import type { Workflow } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

const samples: Record<string, string> = {
  "Customer Support Triage":
    "Hi, I placed order ORD-1042 three days ago and the tracking link isn't working. Can you check the status and tell me what the standard delivery window is for international orders?",
  "Research & Summarize": "What are the main approaches to retrieval-augmented generation in 2025?"
};

function sampleFor(workflow: Workflow | null) {
  if (!workflow) return "";
  return samples[workflow.name] ?? "Run this workflow with a short test input.";
}

export default function WorkflowsPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<Workflow | null>(null);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const workflows = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });

  const sorted = useMemo(
    () => [...(workflows.data ?? [])].sort((a, b) => Number(b.is_template) - Number(a.is_template)),
    [workflows.data]
  );

  function openRunDialog(workflow: Workflow) {
    setSelected(workflow);
    setInput(sampleFor(workflow));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setRunning(true);
    try {
      const result = await api.triggerRun(selected.id, input);
      router.push(`/runs/${result.run_id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not start run");
    } finally {
      setRunning(false);
    }
  }

  async function createWorkflow() {
    try {
      const workflow = await api.createWorkflow({
        name: "Untitled workflow",
        description: "Describe what this workflow coordinates.",
        graph: { nodes: [], edges: [] },
        is_template: false
      });
      router.push(`/workflows/${workflow.id}/edit`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create workflow");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Workflows</h1>
          <p className="text-sm text-muted-foreground">Run seeded templates while the visual builder is still coming online.</p>
        </div>
        <Button onClick={createWorkflow}>
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
                <TH className="w-40 text-right">Action</TH>
              </TR>
            </THead>
            <TBody>
              {sorted.map((workflow) => (
                <TR key={workflow.id}>
                  <TD className="font-medium">{workflow.name}</TD>
                  <TD>{workflow.description}</TD>
                  <TD>{workflow.is_template ? <Badge>Template</Badge> : <Badge>Custom</Badge>}</TD>
                  <TD className="space-x-2 text-right">
                    <Button className="h-8 px-2 border bg-background text-foreground" onClick={() => router.push(`/workflows/${workflow.id}/edit`)}>
                      <Settings2 className="mr-1 h-4 w-4" />
                      Edit
                    </Button>
                    <Button className="h-8 px-2" onClick={() => openRunDialog(workflow)}>
                      <Play className="mr-1 h-4 w-4" />
                      Run
                    </Button>
                  </TD>
                </TR>
              ))}
              {workflows.isLoading &&
                Array.from({ length: 4 }).map((_, index) => (
                  <TR key={index}>
                    <TD colSpan={4}>
                      <Skeleton className="h-6 w-full" />
                    </TD>
                  </TR>
                ))}
              {!workflows.isLoading && !sorted.length && (
                <TR>
                  <TD colSpan={4}>
                    <EmptyState icon={GitBranchPlus} message="No workflows yet. Build one from your agent palette." action="New workflow" onAction={createWorkflow} />
                  </TD>
                </TR>
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={Boolean(selected)} onOpenChange={(open) => !open && setSelected(null)} title={`Run ${selected?.name ?? "Workflow"}`}>
        <form className="space-y-4" onSubmit={submit}>
          <label className="space-y-1 text-sm">
            <span>Input</span>
            <Textarea value={input} onChange={(event) => setInput(event.target.value)} required />
          </label>
          <div className="flex justify-end gap-2">
            <Button type="button" className="border bg-background text-foreground" onClick={() => setSelected(null)}>
              Cancel
            </Button>
            <Button disabled={running || !input.trim()}>{running ? "Starting..." : "Start Run"}</Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
