import { cn } from "@/lib/utils";

const colors: Record<string, string> = {
  pending: "border-slate-200 bg-slate-50 text-slate-700",
  running: "border-blue-200 bg-blue-50 text-blue-700",
  completed: "border-emerald-200 bg-emerald-50 text-emerald-700",
  failed: "border-red-200 bg-red-50 text-red-700"
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium", colors[status] ?? colors.pending)}>
      {status === "running" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-600" />}
      {status}
    </span>
  );
}
