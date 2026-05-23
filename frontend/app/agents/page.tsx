"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Plus } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api-client";
import type { AgentCreate } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

const emptyForm: AgentCreate = {
  name: "",
  role: "",
  system_prompt: "",
  model: "claude-sonnet-4-6",
  tools: [],
  config: { temperature: 0.2, memory_enabled: true },
  channels: ["internal"]
};

export default function AgentsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<AgentCreate>(emptyForm);

  const agents = useQuery({ queryKey: ["agents"], queryFn: () => api.listAgents() });
  const tools = useQuery({ queryKey: ["tools"], queryFn: () => api.listTools() });
  const models = useQuery({ queryKey: ["models"], queryFn: () => api.listModels() });

  const createAgent = useMutation({
    mutationFn: api.createAgent,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
      setForm(emptyForm);
      setOpen(false);
      toast.success("Agent created");
    },
    onError: (error) => toast.error(error.message)
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createAgent.mutate(form);
  }

  function toggleTool(name: string) {
    setForm((current) => ({
      ...current,
      tools: current.tools.includes(name) ? current.tools.filter((tool) => tool !== name) : [...current.tools, name]
    }));
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Agents</h1>
          <p className="text-sm text-muted-foreground">Configure personalities, tools, channels, and model choices.</p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Agent
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <THead>
              <TR>
                <TH>Name</TH>
                <TH>Role</TH>
                <TH>Model</TH>
                <TH>Tools</TH>
                <TH>Channels</TH>
              </TR>
            </THead>
            <TBody>
              {agents.isLoading &&
                Array.from({ length: 4 }).map((_, index) => (
                  <TR key={index}>
                    <TD colSpan={5}>
                      <Skeleton className="h-6 w-full" />
                    </TD>
                  </TR>
                ))}
              {agents.data?.map((agent) => (
                <TR key={agent.id}>
                  <TD className="font-medium">{agent.name}</TD>
                  <TD>{agent.role}</TD>
                  <TD>{agent.model}</TD>
                  <TD>
                    <div className="flex flex-wrap gap-1">
                      {agent.tools.length ? agent.tools.map((tool) => <Badge key={tool}>{tool}</Badge>) : <span className="text-muted-foreground">None</span>}
                    </div>
                  </TD>
                  <TD>
                    <div className="flex flex-wrap gap-1">
                      {agent.channels.map((channel) => <Badge key={channel}>{channel}</Badge>)}
                    </div>
                  </TD>
                </TR>
              ))}
              {!agents.isLoading && !agents.data?.length && (
                <TR>
                  <TD colSpan={5}>
                    <EmptyState icon={Bot} message="No agents yet. Create one to start building workflows." action="New agent" onAction={() => setOpen(true)} />
                  </TD>
                </TR>
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen} title="New Agent">
        <form className="space-y-4" onSubmit={submit}>
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1 text-sm">
              <span>Name</span>
              <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
            </label>
            <label className="space-y-1 text-sm">
              <span>Model</span>
              <Select value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })}>
                {models.data?.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.display_name}
                  </option>
                ))}
              </Select>
            </label>
          </div>
          <label className="space-y-1 text-sm">
            <span>Role</span>
            <Input value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} required />
          </label>
          <label className="space-y-1 text-sm">
            <span>System prompt</span>
            <Textarea value={form.system_prompt} onChange={(event) => setForm({ ...form, system_prompt: event.target.value })} required />
          </label>
          <div className="space-y-2 text-sm">
            <span>Tools</span>
            <div className="grid grid-cols-2 gap-2">
              {tools.data?.map((tool) => (
                <label key={tool.name} className="flex items-start gap-2 rounded-md border p-2">
                  <input type="checkbox" checked={form.tools.includes(tool.name)} onChange={() => toggleTool(tool.name)} />
                  <span>
                    <span className="block font-medium">{tool.name}</span>
                    <span className="block text-xs text-muted-foreground">{tool.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" className="border bg-background text-foreground" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button disabled={createAgent.isPending}>{createAgent.isPending ? "Creating..." : "Create Agent"}</Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
