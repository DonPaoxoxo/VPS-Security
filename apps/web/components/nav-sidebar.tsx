"use client";

import {
  Activity,
  AlertTriangle,
  FileSearch,
  Gauge,
  Globe,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Network,
  Server,
  Settings,
  ShieldAlert,
  FileText,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/cn";

const NAV_ITEMS = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/servers", label: "Servers", icon: Server },
  { href: "/aapanel", label: "aaPanel Monitoring", icon: Network },
  { href: "/domains", label: "Domain Inventory", icon: Globe },
  { href: "/domains?type=wordpress", label: "WordPress Sites", icon: Globe },
  { href: "/domains?type=static", label: "Static Websites", icon: Globe },
  { href: "/performance", label: "Performance Monitoring", icon: Gauge },
  { href: "/security", label: "Security Center", icon: ShieldAlert },
  { href: "/ip-investigation", label: "IP Investigation", icon: FileSearch },
  { href: "/file-integrity", label: "File Integrity", icon: FileText },
  { href: "/login-activity", label: "Login Activity", icon: KeyRound },
  { href: "/incidents", label: "Incidents & Alerts", icon: AlertTriangle },
  { href: "/activity", label: "Activity History", icon: Activity },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function NavSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="flex h-screen w-60 flex-col border-r border-card-border bg-card">
      <div className="px-4 py-5">
        <p className="text-sm font-semibold tracking-tight">Server Security Center</p>
        {user && <p className="mt-0.5 truncate text-xs text-muted-foreground">{user.email}</p>}
      </div>
      <nav className="scrollbar-thin flex-1 overflow-y-auto px-2">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href.split("?")[0];
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "mb-0.5 flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                isActive ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-card-border p-2">
        <button
          onClick={() => logout()}
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <LogOut className="h-4 w-4" />
          Log out
        </button>
      </div>
    </aside>
  );
}
