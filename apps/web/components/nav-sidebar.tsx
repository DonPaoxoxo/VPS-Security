"use client";

import {
  Activity,
  AlertTriangle,
  ChevronsLeft,
  ChevronsRight,
  FileSearch,
  FileText,
  Gauge,
  Globe,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Network,
  Search,
  Server,
  Settings,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { ThemeToggle } from "@/components/ui/theme-toggle";
import { useAuth } from "@/lib/auth-context";
import { useCommandPalette } from "@/lib/command-palette-context";
import { cn } from "@/lib/cn";
import { useSidebar } from "@/lib/sidebar-context";

export const NAV_SECTIONS = [
  {
    label: "Monitoring",
    items: [
      { href: "/overview", label: "Overview", icon: LayoutDashboard },
      { href: "/servers", label: "Servers", icon: Server },
      { href: "/aapanel", label: "aaPanel Monitoring", icon: Network },
      { href: "/performance", label: "Performance", icon: Gauge },
    ],
  },
  {
    label: "Websites",
    items: [
      { href: "/domains", label: "Domain Inventory", icon: Globe },
      { href: "/domains?type=wordpress", label: "WordPress Sites", icon: Globe },
      { href: "/domains?type=static", label: "Static Websites", icon: Globe },
    ],
  },
  {
    label: "Security",
    items: [
      { href: "/security", label: "Security Center", icon: ShieldAlert },
      { href: "/ip-investigation", label: "IP Investigation", icon: FileSearch },
      { href: "/file-integrity", label: "File Integrity", icon: FileText },
      { href: "/login-activity", label: "Login Activity", icon: KeyRound },
      { href: "/incidents", label: "Incidents & Alerts", icon: AlertTriangle },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/activity", label: "Activity History", icon: Activity },
      { href: "/reports", label: "Reports", icon: FileText },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function NavSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { setOpen } = useCommandPalette();
  const { collapsed, toggleCollapsed } = useSidebar();

  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : "?";
  const isMac = typeof navigator !== "undefined" && /Mac/.test(navigator.platform);

  return (
    <aside
      className={cn(
        "flex h-screen shrink-0 flex-col border-r border-card-border bg-card transition-[width] duration-200",
        collapsed ? "w-[68px]" : "w-64"
      )}
    >
      <div className={cn("flex items-center gap-2.5 px-5 py-5", collapsed && "justify-center px-0")}>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent/15 text-accent">
          <ShieldCheck className="h-4 w-4" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight text-foreground">Server Security Center</p>
          </div>
        )}
      </div>

      <div className={cn("px-3 pb-3", collapsed && "px-2")}>
        <button
          onClick={() => setOpen(true)}
          title="Search (Ctrl/⌘ K)"
          className={cn(
            "flex w-full items-center gap-2 rounded-md border border-card-border bg-background text-sm text-muted-foreground transition-colors hover:border-surface-border hover:text-foreground",
            collapsed ? "justify-center px-0 py-2" : "px-3 py-2"
          )}
        >
          <Search className="h-3.5 w-3.5 shrink-0" />
          {!collapsed && (
            <>
              <span className="flex-1 text-left">Search…</span>
              <kbd className="shrink-0 rounded border border-card-border bg-card px-1.5 py-0.5 text-[10px]">
                {isMac ? "⌘K" : "Ctrl K"}
              </kbd>
            </>
          )}
        </button>
      </div>

      <nav className={cn("scrollbar-thin flex-1 overflow-y-auto pb-4", collapsed ? "px-2" : "px-3")}>
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="mb-4">
            {!collapsed && (
              <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                {section.label}
              </p>
            )}
            {section.items.map((item) => {
              const isActive = pathname === item.href.split("?")[0];
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  title={collapsed ? item.label : undefined}
                  className={cn(
                    "group relative mb-0.5 flex items-center gap-2.5 rounded-md text-sm transition-colors",
                    collapsed ? "justify-center px-0 py-2" : "px-3 py-2",
                    isActive
                      ? "bg-accent/10 font-medium text-accent"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  {isActive && (
                    <span
                      className={cn(
                        "absolute top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-accent",
                        collapsed ? "left-0.5" : "left-0"
                      )}
                    />
                  )}
                  <item.icon className="h-4 w-4 shrink-0" />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className={cn("border-t border-card-border p-3", collapsed && "px-2")}>
        <div
          className={cn(
            "flex items-center gap-2.5 rounded-md py-1.5",
            collapsed ? "flex-col px-0" : "px-2"
          )}
        >
          <div
            title={collapsed ? user?.email : undefined}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-foreground"
          >
            {initials}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-foreground">{user?.display_name || "Owner"}</p>
              <p className="truncate text-[11px] text-muted-foreground">{user?.email}</p>
            </div>
          )}
          <div className={cn("flex items-center gap-1", collapsed && "mt-1")}>
            <ThemeToggle />
            <button
              onClick={() => logout()}
              title="Log out"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>

        <button
          onClick={toggleCollapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "mt-2 flex w-full items-center gap-2 rounded-md py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
            collapsed ? "justify-center px-0" : "px-2"
          )}
        >
          {collapsed ? <ChevronsRight className="h-3.5 w-3.5" /> : <ChevronsLeft className="h-3.5 w-3.5" />}
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
