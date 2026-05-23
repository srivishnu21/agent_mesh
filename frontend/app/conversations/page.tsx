"use client";

import { useQuery } from "@tanstack/react-query";
import { MessageSquareText } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";

function labelFor(conversation: Awaited<ReturnType<typeof api.listConversations>>[number]) {
  const user = conversation.telegram_user as { username?: string; first_name?: string } | null | undefined;
  if (user?.username) return `@${user.username}`;
  if (user?.first_name) return user.first_name;
  return conversation.external_id;
}

export default function ConversationsPage() {
  const conversations = useQuery({ queryKey: ["conversations"], queryFn: () => api.listConversations() });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Conversations</h1>
      <Card>
        <CardContent className="p-0">
          <Table>
            <THead>
              <TR>
                <TH>Channel</TH>
                <TH>Contact</TH>
                <TH>Last message</TH>
                <TH>Messages</TH>
                <TH>Updated</TH>
              </TR>
            </THead>
            <TBody>
              {conversations.isLoading &&
                Array.from({ length: 4 }).map((_, index) => (
                  <TR key={index}>
                    <TD colSpan={5}>
                      <Skeleton className="h-6 w-full" />
                    </TD>
                  </TR>
                ))}
              {conversations.data?.map((conversation) => (
                <TR key={conversation.id} className="hover:bg-muted/60">
                  <TD>
                    <Link href={`/conversations/${conversation.id}`}>
                      <Badge>{conversation.channel}</Badge>
                    </Link>
                  </TD>
                  <TD>
                    <Link className="block font-medium text-primary" href={`/conversations/${conversation.id}`}>
                      {labelFor(conversation)}
                    </Link>
                  </TD>
                  <TD className="max-w-xl truncate">{conversation.last_message_preview ?? "No messages yet"}</TD>
                  <TD>{conversation.message_count ?? 0}</TD>
                  <TD>{conversation.last_message_at ? new Date(conversation.last_message_at).toLocaleString() : new Date(conversation.created_at).toLocaleString()}</TD>
                </TR>
              ))}
              {!conversations.isLoading && !conversations.data?.length && (
                <TR>
                  <TD colSpan={5}>
                    <EmptyState icon={MessageSquareText} message="No conversations yet. Connect Telegram to get started." />
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
