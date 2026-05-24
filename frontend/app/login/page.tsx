"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { GitBranch, Loader2 } from "lucide-react";

import { api, getToken, setSession } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authEnabled, setAuthEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    if (getToken()) {
      router.replace("/");
      return;
    }
    api
      .authStatus()
      .then((status) => {
        if (!status.enabled) {
          // Auth disabled on backend — auto-issue local token and bounce home.
          api.login("anonymous", "").then((res) => {
            setSession(res.token, res.username);
            router.replace("/");
          });
          return;
        }
        setAuthEnabled(true);
      })
      .catch(() => setAuthEnabled(true));
  }, [router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.login(username.trim(), password);
      setSession(result.token, result.username);
      router.replace("/");
    } catch {
      setError("Invalid username or password.");
    } finally {
      setSubmitting(false);
    }
  }

  if (authEnabled === null) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-sm shadow-lg">
        <CardContent className="space-y-5 p-6">
          <div className="flex items-center gap-2">
            <GitBranch className="h-6 w-6 text-primary" />
            <div>
              <h1 className="text-lg font-semibold">Agent Mesh</h1>
              <p className="text-xs text-muted-foreground">Sign in to continue.</p>
            </div>
          </div>
          <form className="space-y-3" onSubmit={submit}>
            <label className="block space-y-1 text-sm">
              <span className="font-medium">Username</span>
              <Input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoFocus
                autoComplete="username"
                required
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="font-medium">Password</span>
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            {error && <p className="text-xs text-red-600">{error}</p>}
            <Button type="submit" className="w-full" disabled={submitting || !username.trim() || !password}>
              {submitting ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
