"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Copy, MoreHorizontal, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api-client";
import type { Agent, AgentCreate } from "@/lib/types";
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
  model: "gpt-5-nano",
  tools: [],
  config: { temperature: 0.2, memory_enabled: true },
  channels: ["internal"]
};

function agentToForm(agent: Agent): AgentCreate {
  return {
    name: agent.name,
    role: agent.role,
    system_prompt: agent.system_prompt,
    model: agent.model,
    tools: agent.tools,
    config: agent.config,
    channels: agent.channels
  };
}

function toolChipClass(tool: string) {
  const colors: Record<string, string> = {
    web_search: "border-amber-200 bg-amber-50 text-amber-800",
    sql_query: "border-orange-200 bg-orange-50 text-orange-800",
    order_lookup: "border-yellow-200 bg-yellow-50 text-yellow-800",
    send_email: "border-rose-200 bg-rose-50 text-rose-800",
    calculator: "border-lime-200 bg-lime-50 text-lime-800"
  };
  return colors[tool] ?? "border-amber-200 bg-amber-50 text-amber-800";
}

function channelChipClass(channel: string) {
  const colors: Record<string, string> = {
    telegram: "border-sky-200 bg-sky-50 text-sky-800",
    internal: "border-violet-200 bg-violet-50 text-violet-800",
    web: "border-blue-200 bg-blue-50 text-blue-800",
    slack: "border-purple-200 bg-purple-50 text-purple-800"
  };
  return colors[channel] ?? "border-blue-200 bg-blue-50 text-blue-800";
}

export default function AgentsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<AgentCreate>(emptyForm);
  const [skillsText, setSkillsText] = useState("");
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);

  const agents = useQuery({ queryKey: ["agents"], queryFn: () => api.listAgents() });
  const tools = useQuery({ queryKey: ["tools"], queryFn: () => api.listTools() });
  const models = useQuery({ queryKey: ["models"], queryFn: () => api.listModels() });

  const createAgent = useMutation({
    mutationFn: api.createAgent,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
      setForm(emptyForm);
      setEditingAgent(null);
      setOpen(false);
      toast.success("Agent created");
    },
    onError: (error) => toast.error(error.message)
  });

  const updateAgent = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AgentCreate }) => api.updateAgent(id, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
      setForm(emptyForm);
      setEditingAgent(null);
      setOpen(false);
      toast.success("Agent updated");
    },
    onError: (error) => toast.error(error.message)
  });

  const duplicateAgent = useMutation({
    mutationFn: (agent: Agent) => api.createAgent({ ...agentToForm(agent), name: `${agent.name} copy` }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
      toast.success("Agent duplicated");
    },
    onError: (error) => toast.error(error.message)
  });

  const deleteAgent = useMutation({
    mutationFn: api.deleteAgent,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
      toast.success("Agent deleted");
    },
    onError: (error) => toast.error(error.message)
  });

  function openCreate() {
    setEditingAgent(null);
    setForm(emptyForm);
    setSkillsText("");
    setOpen(true);
  }

  function openEdit(agent: Agent) {
    setEditingAgent(agent);
    setForm(agentToForm(agent));
    setSkillsText(((agent.config?.skills as string[] | undefined) ?? []).join(", "));
    setOpen(true);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const skills = skillsText
      .split(",")
      .map((skill) => skill.trim())
      .filter(Boolean);
    const payload: AgentCreate = { ...form, config: { ...form.config, skills } };
    if (editingAgent) updateAgent.mutate({ id: editingAgent.id, payload });
    else createAgent.mutate(payload);
  }

  function toggleTool(name: string) {
    setForm((current) => ({
      ...current,
      tools: current.tools.includes(name) ? current.tools.filter((tool) => tool !== name) : [...current.tools, name]
    }));
  }

  function toggleChannel(name: string) {
    setForm((current) => ({
      ...current,
      channels: current.channels.includes(name) ? current.channels.filter((channel) => channel !== name) : [...current.channels, name]
    }));
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Agents</h1>
          <p className="text-sm text-muted-foreground">Configure personalities, tools, channels, and model choices.</p>
        </div>
        <Button onClick={openCreate}>
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
                <TH>Skills</TH>
                <TH>Channels</TH>
                <TH className="w-12" />
              </TR>
            </THead>
            <TBody>
              {agents.isLoading &&
                Array.from({ length: 4 }).map((_, index) => (
                  <TR key={index}>
                    <TD colSpan={7}>
                      <Skeleton className="h-6 w-full" />
                    </TD>
                  </TR>
                ))}
              {agents.data?.map((agent) => (
                <TR
                  key={agent.id}
                  className="group cursor-pointer transition-colors hover:bg-muted/60"
                  onClick={() => openEdit(agent)}
                >
                  <TD className="font-medium">{agent.name}</TD>
                  <TD>{agent.role}</TD>
                  <TD>{agent.model}</TD>
                  <TD>
                    <div className="flex flex-wrap gap-1">
                      {agent.tools.length ? agent.tools.map((tool) => <Badge key={tool} className={toolChipClass(tool)}>{tool}</Badge>) : <span className="text-muted-foreground">None</span>}
                    </div>
                  </TD>
                  <TD>
                    <div className="flex flex-wrap gap-1">
                      {((agent.config?.skills as string[] | undefined) ?? []).length
                        ? ((agent.config!.skills as string[])).map((skill) => (
                            <Badge key={skill} className="border-violet-200 bg-violet-50 text-violet-800">
                              {skill}
                            </Badge>
                          ))
                        : <span className="text-muted-foreground">None</span>}
                    </div>
                  </TD>
                  <TD>
                    <div className="flex flex-wrap gap-1">
                      {agent.channels.map((channel) => <Badge key={channel} className={channelChipClass(channel)}>{channel}</Badge>)}
                    </div>
                  </TD>
                  <TD onClick={(event) => event.stopPropagation()}>
                    <div className="relative flex justify-end">
                      <Button className="h-8 w-8 border bg-background p-0 text-foreground opacity-0 transition-opacity group-hover:opacity-100">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                      <div className="invisible absolute right-0 top-8 z-20 w-36 rounded-md border bg-background p-1 opacity-0 shadow-lg transition group-hover:visible group-hover:opacity-100">
                        <button className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted" onClick={() => openEdit(agent)}>
                          <Pencil className="h-4 w-4" />
                          Edit
                        </button>
                        <button className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted" onClick={() => duplicateAgent.mutate(agent)}>
                          <Copy className="h-4 w-4" />
                          Duplicate
                        </button>
                        <button
                          className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-red-700 hover:bg-red-50"
                          onClick={() => {
                            if (window.confirm(`Delete ${agent.name}?`)) deleteAgent.mutate(agent.id);
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </button>
                      </div>
                    </div>
                  </TD>
                </TR>
              ))}
              {!agents.isLoading && !agents.data?.length && (
                <TR>
                  <TD colSpan={7}>
                    <EmptyState icon={Bot} message="No agents yet. Create one to start building workflows." action="New agent" onAction={openCreate} />
                  </TD>
                </TR>
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen} title={editingAgent ? "Edit Agent" : "New Agent"}>
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
            <Textarea className="min-h-64" value={form.system_prompt} onChange={(event) => setForm({ ...form, system_prompt: event.target.value })} required />
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
          <label className="space-y-1 text-sm">
            <span>Skills (comma-separated)</span>
            <Input
              value={skillsText}
              onChange={(event) => setSkillsText(event.target.value)}
              onBlur={() => {
                const skills = skillsText
                  .split(",")
                  .map((skill) => skill.trim())
                  .filter(Boolean);
                setForm((current) => ({ ...current, config: { ...current.config, skills } }));
              }}
              placeholder="copywriting, summarization, routing"
            />
            <span className="text-xs text-muted-foreground">
              Free-form capability labels for this agent. Surfaced on the agent card and workflow node.
            </span>
          </label>
          <div className="space-y-2 text-sm">
            <span>Channels</span>
            <div className="grid grid-cols-3 gap-2">
              {["internal", "telegram", "web"].map((channel) => (
                <label key={channel} className="flex items-center gap-2 rounded-md border p-2">
                  <input type="checkbox" checked={form.channels.includes(channel)} onChange={() => toggleChannel(channel)} />
                  <span>{channel}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" className="border bg-background text-foreground" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button disabled={createAgent.isPending || updateAgent.isPending}>
              {editingAgent ? (updateAgent.isPending ? "Saving..." : "Save Agent") : createAgent.isPending ? "Creating..." : "Create Agent"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
