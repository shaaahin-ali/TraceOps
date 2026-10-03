"use client";

/**
 * Navbar Component
 * =================
 * Shared navigation bar for all authenticated pages.
 *
 * Features:
 * - RootTrace brand + logo
 * - Navigation links (Dashboard, Approvals, Evaluation)
 * - User display name + role badge
 * - Logout button
 * - Active page highlighting
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  BarChart2,
  CheckSquare,
  LogOut,
  Shield,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard", icon: Activity },
  { href: "/approvals", label: "Approvals", icon: CheckSquare },
  { href: "/evaluation", label: "Evaluation", icon: BarChart2 },
];

const ROLE_COLORS: Record<string, string> = {
  ADMIN: "#a855f7",
  SRE: "#3b82f6",
  USER: "#94a3b8",
};

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  return (
    <nav
      className="border-b"
      style={{
        background: "var(--bg-secondary)",
        borderColor: "var(--border)",
      }}
    >
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Brand */}
        <Link
          href="/dashboard"
          className="flex items-center gap-2 no-underline"
        >
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center glow-blue"
            style={{ background: "linear-gradient(135deg, #1d4ed8, #7c3aed)" }}
          >
            <Shield className="w-4 h-4 text-white" />
          </div>
          <span
            className="font-bold text-base tracking-tight text-gradient"
            style={{ fontFamily: "Inter, sans-serif" }}
          >
            RootTrace
          </span>
        </Link>

        {/* Nav links */}
        <div className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map(({ href, label, icon: Icon }) => {
            const isActive = pathname === href || pathname?.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all"
                style={{
                  color: isActive ? "var(--accent-blue)" : "var(--text-muted)",
                  background: isActive ? "rgba(59,130,246,0.1)" : "transparent",
                }}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </Link>
            );
          })}
        </div>

        {/* User section */}
        <div className="flex items-center gap-3">
          {user && (
            <div className="flex items-center gap-2">
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                {user.name}
              </span>
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded-full"
                style={{
                  color: ROLE_COLORS[user.role] ?? "#94a3b8",
                  background: `${ROLE_COLORS[user.role] ?? "#94a3b8"}22`,
                  border: `1px solid ${ROLE_COLORS[user.role] ?? "#94a3b8"}44`,
                }}
              >
                {user.role}
              </span>
            </div>
          )}
          <button
            onClick={logout}
            title="Sign out"
            className="flex items-center gap-1 text-xs px-2 py-1.5 rounded-md transition-all"
            style={{ color: "var(--text-muted)" }}
            onMouseOver={(e) =>
              ((e.currentTarget as HTMLButtonElement).style.color = "var(--accent-red)")
            }
            onMouseOut={(e) =>
              ((e.currentTarget as HTMLButtonElement).style.color = "var(--text-muted)")
            }
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </div>
    </nav>
  );
}
