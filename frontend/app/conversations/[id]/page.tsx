"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export default function ConversationDetailPage({ params }: { params: { id: string } }) {
  const conversation = useQuery({ queryKey: ["conversation", params.id], queryFn: () => api.getConversation(params.id) });
  const messages = [...(conversation.data?.messages ?? [])].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Conversation</CardTitle>
          <div className="text-sm text-muted-foreground">
            {conversation.data?.channel ?? "Channel"} / {conversation.data?.external_id ?? params.id}
          </div>
        </CardHeader>
      </Card>

      <Card>
        <CardContent className="space-y-3 p-4">
          {conversation.isLoading &&
            Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className={cn("h-16 w-2/3", index % 2 ? "ml-auto" : "")} />)}
          {messages.map((message) => {
            const runId = typeof message.metadata?.run_id === "string" ? message.metadata.run_id : null;
            const isAgent = message.role === "agent";
            return (
              <div key={message.id} className={cn("flex", isAgent ? "justify-end" : "justify-start")}>
                <div className={cn("max-w-[72%] rounded-md border p-3 text-sm", isAgent ? "bg-primary text-primary-foreground" : "bg-muted")}>
                  <div className="whitespace-pre-wrap">{message.content}</div>
                  <div className={cn("mt-2 flex items-center gap-3 text-xs", isAgent ? "text-primary-foreground/75" : "text-muted-foreground")}>
                    <span>{new Date(message.created_at).toLocaleString()}</span>
                    {runId && (
                      <Link className="inline-flex items-center gap-1 underline" href={`/runs/${runId}`} target="_blank">
                        View run <ExternalLink className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          {!conversation.isLoading && !messages.length && <div className="py-10 text-center text-sm text-muted-foreground">No messages in this conversation yet.</div>}
        </CardContent>
      </Card>
    </div>
  );
}
