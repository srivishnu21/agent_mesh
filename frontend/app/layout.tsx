import type { Metadata } from "next";
import Link from "next/link";
import { Activity, Bot, GitBranch, LayoutDashboard, MessageSquare, Settings, Workflow } from "lucide-react";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Agent Mesh",
  description: "AI agent orchestration contract scaffold"
};

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/workflows", label: "Workflows", icon: Workflow },
  { href: "/runs", label: "Runs", icon: Activity },
  { href: "/conversations", label: "Conversations", icon: MessageSquare },
  { href: "/settings", label: "Settings", icon: Settings }
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="grid min-h-screen grid-cols-[240px_1fr]">
            <aside className="border-r bg-card px-3 py-4">
              <div className="mb-6 flex items-center gap-2 px-2 text-lg font-semibold">
                <GitBranch className="h-5 w-5 text-primary" />
                Agent Mesh
              </div>
              <nav className="space-y-1">
                {nav.map((item) => (
                  <Link key={item.href} href={item.href} className="flex items-center gap-2 rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground">
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                ))}
              </nav>
            </aside>
            <main className="min-w-0 p-6">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
