"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Toaster } from "sonner";

import { getToken } from "@/lib/api-client";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const onLoginPage = pathname?.startsWith("/login");
    const hasToken = !!getToken();
    if (!hasToken && !onLoginPage) {
      router.replace("/login");
      return;
    }
    if (hasToken && onLoginPage) {
      router.replace("/");
      return;
    }
    setReady(true);
  }, [pathname, router]);

  if (!ready) {
    return null;
  }

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster richColors />
    </QueryClientProvider>
  );
}
