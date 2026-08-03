"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { DataVintageStrip } from "@/components/ui/DataVintageStrip";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { useAuth } from "@/components/AuthProvider";
import { canAccess, permissionForPath } from "@/lib/roles";
import { LoadingState } from "@/components/ui/LoadingState";

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { loading, isAuthenticated, role, homePath } = useAuth();
  const isLogin = pathname === "/login";
  const isChatFocus = pathname === "/assistant" || pathname === "/chat";

  useEffect(() => {
    if (loading || isLogin) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    const permission = permissionForPath(pathname);
    if (permission && !canAccess(role, permission)) {
      router.replace(homePath);
    }
  }, [loading, isAuthenticated, isLogin, pathname, role, homePath, router]);

  if (isLogin) {
    return <>{children}</>;
  }

  if (loading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100">
        <LoadingState message="Loading workspace…" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-100">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <DataVintageStrip />
        <div className="flex-1 flex min-h-0 overflow-hidden">
          {!isChatFocus && (
            <main className="flex-1 p-5 lg:p-6 overflow-auto min-w-0">
              <div className="animate-fade-in max-w-6xl mx-auto space-y-6">{children}</div>
            </main>
          )}
          <ChatPanel fullWidth={isChatFocus} />
        </div>
      </div>
    </div>
  );
}
