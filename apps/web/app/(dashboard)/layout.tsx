"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { NavSidebar } from "@/components/nav-sidebar";
import { useAuth } from "@/lib/auth-context";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return <div className="flex h-screen items-center justify-center text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="flex">
      <NavSidebar />
      <main className="scrollbar-thin h-screen flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  );
}
