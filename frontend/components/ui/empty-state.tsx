import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";

export function EmptyState({
  icon: Icon,
  message,
  action,
  onAction
}: {
  icon: LucideIcon;
  message: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-center text-sm text-muted-foreground">
      <Icon className="h-8 w-8 text-muted-foreground" />
      <div>{message}</div>
      {action && onAction && (
        <Button onClick={onAction} className="h-8">
          {action}
        </Button>
      )}
    </div>
  );
}
