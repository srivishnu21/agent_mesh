import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>Environment</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">Provider keys, channel settings, and guardrail defaults will be configured here later.</CardContent>
      </Card>
    </div>
  );
}
