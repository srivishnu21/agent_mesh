"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { Bot, CheckCircle2, ExternalLink, KeyRound, MessageCircle, ServerCog, Timer, Workflow } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { API_URL, USER_KEY, api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function SettingRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b py-3 last:border-b-0">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="text-right text-sm font-medium">{value}</div>
    </div>
  );
}

export default function SettingsPage() {
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    setUsername(window.localStorage.getItem(USER_KEY));
  }, []);

  const auth = useQuery({ queryKey: ["auth-status"], queryFn: api.authStatus });
  const models = useQuery({ queryKey: ["models"], queryFn: api.listModels });
  const tools = useQuery({ queryKey: ["tools"], queryFn: api.listTools });
  const workflows = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });

  useEffect(() => {
    const error = auth.error ?? models.error ?? tools.error ?? workflows.error;
    if (error) toast.error(error.message);
  }, [auth.error, models.error, tools.error, workflows.error]);

  const scheduledCount = useMemo(() => {
    return (workflows.data ?? []).filter((workflow) => {
      const graph = (workflow.graph ?? {}) as { config?: { schedule?: { enabled?: boolean } } };
      return !!graph.config?.schedule?.enabled;
    }).length;
  }, [workflows.data]);

  const templateCount = (workflows.data ?? []).filter((workflow) => workflow.is_template).length;
  const customCount = Math.max(0, (workflows.data ?? []).length - templateCount);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">Runtime, auth, Telegram, tools, and workflow scheduling status.</p>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center gap-2 space-y-0">
            <KeyRound className="h-4 w-4 text-primary" />
            <CardTitle>Access</CardTitle>
          </CardHeader>
          <CardContent>
            <SettingRow
              label="Auth mode"
              value={
                auth.isLoading ? (
                  <Skeleton className="ml-auto h-5 w-20" />
                ) : auth.data?.enabled ? (
                  <Badge className="border-emerald-200 bg-emerald-50 text-emerald-800">Enabled</Badge>
                ) : (
                  <Badge className="border-slate-200 bg-slate-50 text-slate-700">Local dev</Badge>
                )
              }
            />
            <SettingRow label="Signed in as" value={username ?? "anonymous"} />
            <SettingRow label="Public endpoints" value="/health, /api/v1/auth/*, Telegram webhook" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center gap-2 space-y-0">
            <ServerCog className="h-4 w-4 text-primary" />
            <CardTitle>Runtime</CardTitle>
          </CardHeader>
          <CardContent>
            <SettingRow label="API URL" value={<code className="rounded bg-muted px-1.5 py-0.5 text-xs">{API_URL}</code>} />
            <SettingRow
              label="Models"
              value={models.isLoading ? <Skeleton className="ml-auto h-5 w-16" /> : `${models.data?.length ?? 0} available`}
            />
            <SettingRow
              label="Tools"
              value={tools.isLoading ? <Skeleton className="ml-auto h-5 w-16" /> : `${tools.data?.length ?? 0} registered`}
            />
            <SettingRow label="Provider" value="OpenAI-compatible adapter" />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center gap-2 space-y-0">
            <MessageCircle className="h-4 w-4 text-primary" />
            <CardTitle>Telegram</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="rounded-md border bg-muted/40 p-3">
              <div className="font-medium">@agent_mesh_poc_bot</div>
              <div className="mt-1 text-xs text-muted-foreground">Use /start for instructions, /workflows to select a workflow, then chat normally.</div>
            </div>
            <div className="flex gap-2">
              <a
                className="inline-flex h-8 items-center justify-center rounded-md bg-primary px-2 text-sm font-medium text-primary-foreground transition hover:opacity-90"
                href="https://t.me/agent_mesh_poc_bot"
                target="_blank"
                rel="noreferrer"
              >
                Open bot
                <ExternalLink className="ml-1 h-3.5 w-3.5" />
              </a>
              <Link
                className="inline-flex h-8 items-center justify-center rounded-md border bg-background px-2 text-sm font-medium text-foreground transition hover:opacity-90"
                href="/conversations"
              >
                Conversations
              </Link>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center gap-2 space-y-0">
            <Workflow className="h-4 w-4 text-primary" />
            <CardTitle>Workflows</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <SettingRow label="Templates" value={workflows.isLoading ? <Skeleton className="ml-auto h-5 w-8" /> : templateCount} />
            <SettingRow label="Custom" value={workflows.isLoading ? <Skeleton className="ml-auto h-5 w-8" /> : customCount} />
            <Link
              className="inline-flex h-8 w-full items-center justify-center rounded-md border bg-background px-3 text-sm font-medium text-foreground transition hover:opacity-90"
              href="/workflows"
            >
              Manage workflows
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center gap-2 space-y-0">
            <Timer className="h-4 w-4 text-primary" />
            <CardTitle>Scheduling</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <SettingRow label="Enabled schedules" value={workflows.isLoading ? <Skeleton className="ml-auto h-5 w-8" /> : scheduledCount} />
            <div className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
              Configure cron in the workflow editor. Scheduler reads <code className="rounded bg-muted px-1">graph.config.schedule</code>.
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center gap-2 space-y-0">
          <Bot className="h-4 w-4 text-primary" />
          <CardTitle>Registered Tools</CardTitle>
        </CardHeader>
        <CardContent>
          {tools.isLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : (
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {(tools.data ?? []).map((tool) => (
                <div key={tool.name} className="rounded-md border p-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    <div className="font-medium">{tool.name}</div>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{tool.description}</div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
