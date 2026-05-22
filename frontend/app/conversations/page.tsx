"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";

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
                <TH>External ID</TH>
                <TH>Agent</TH>
                <TH>Created</TH>
              </TR>
            </THead>
            <TBody>
              {conversations.data?.map((conversation) => (
                <TR key={conversation.id}>
                  <TD><Badge>{conversation.channel}</Badge></TD>
                  <TD>{conversation.external_id}</TD>
                  <TD>{conversation.agent_id}</TD>
                  <TD>{new Date(conversation.created_at).toLocaleString()}</TD>
                </TR>
              ))}
              {!conversations.data?.length && (
                <TR>
                  <TD colSpan={4} className="py-8 text-center text-muted-foreground">No conversations yet.</TD>
                </TR>
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
