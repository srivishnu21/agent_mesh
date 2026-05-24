"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut, User } from "lucide-react";

import { USER_KEY, clearSession } from "@/lib/api-client";

export function SessionBadge() {
  const router = useRouter();
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setUsername(window.localStorage.getItem(USER_KEY));
  }, []);

  if (!username || username === "anonymous") return null;

  function signOut() {
    clearSession();
    router.replace("/login");
  }

  return (
    <div className="mt-6 border-t pt-4">
      <div className="flex items-center justify-between gap-2 px-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5 truncate">
          <User className="h-3.5 w-3.5" />
          <span className="truncate">{username}</span>
        </span>
        <button
          onClick={signOut}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Sign out"
        >
          <LogOut className="h-3.5 w-3.5" />
          Sign out
        </button>
      </div>
    </div>
  );
}
