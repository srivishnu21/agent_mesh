import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <Card>
        <CardHeader>
          <CardTitle>Coming soon: live stats</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">Run volume, task completion, token usage, and channel activity will land here.</CardContent>
      </Card>
    </div>
  );
}
