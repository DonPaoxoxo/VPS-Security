"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { CommandPalette } from "@/components/command-palette";
import { NavSidebar } from "@/components/nav-sidebar";
import { useAuth } from "@/lib/auth-context";
import { CommandPaletteProvider } from "@/lib/command-palette-context";
import { SidebarProvider } from "@/lib/sidebar-context";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-accent" />
      </div>
    );
  }

  return (
    <SidebarProvider>
      <CommandPaletteProvider>
        <div className="flex">
          <NavSidebar />
          <main className="scrollbar-thin h-screen flex-1 overflow-y-auto bg-background p-8">
            <div className="mx-auto max-w-[1600px]">{children}</div>
          </main>
        </div>
        <CommandPalette />
      </CommandPaletteProvider>
    </SidebarProvider>
  );
}
