"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { LoadingState } from "@/components/ui/LoadingState";

export default function HomePage() {
  const { loading, isAuthenticated, homePath } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(isAuthenticated ? homePath : "/login");
  }, [loading, isAuthenticated, homePath, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <LoadingState message="Loading…" />
    </div>
  );
}
