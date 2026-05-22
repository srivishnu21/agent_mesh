"use client";

import { useEffect } from "react";

import { wsRunUrl } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function RunDetailPage({ params }: { params: { id: string } }) {
  useEffect(() => {
    const socket = new WebSocket(wsRunUrl(params.id));
    socket.onmessage = (event) => console.log("run event", JSON.parse(event.data));
    return () => socket.close();
  }, [params.id]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Run {params.id}</h1>
      <Card>
        <CardHeader>
          <CardTitle>Live run view</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">Connected to the run WebSocket. Stub heartbeat events are logged in the browser console.</CardContent>
      </Card>
    </div>
  );
}
