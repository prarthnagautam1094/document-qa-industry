"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { BarChart3, LogOut, MessageSquare, Sparkles, X } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import { UploadZone } from "./UploadZone";
import { DocumentList } from "./DocumentList";
import { ThemeToggle } from "./ThemeToggle";

const NAV_ITEMS = [
  { href: "/", label: "Chat", icon: MessageSquare },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
];

interface SidebarProps {
  mobileOpen: boolean;
  onClose: () => void;
}

/** Shows the signed-in user's email with a one-click sign-out — the only
 * account affordance in the app, so it lives at the bottom of the
 * sidebar rather than behind a dedicated settings page. */
function UserMenu() {
  const { user, signOut } = useAuth();

  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-bg-surface px-2.5 py-2">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent-cyan text-xs font-bold text-[#0B0E14]">
        {user?.email?.[0]?.toUpperCase() ?? "?"}
      </div>
      <p className="min-w-0 flex-1 truncate text-xs text-text" title={user?.email ?? undefined}>
        {user?.email}
      </p>
      <button
        onClick={() => signOut()}
        aria-label="Sign out"
        className="shrink-0 rounded-md p-1.5 text-text-muted transition-colors hover:bg-red-500/10 hover:text-red-400"
      >
        <LogOut size={14} />
      </button>
    </div>
  );
}

function SidebarContent() {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="flex items-center gap-2 px-1">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent-cyan">
          <Sparkles size={16} className="text-[#0B0E14]" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate bg-gradient-to-r from-accent to-accent-cyan bg-clip-text font-heading text-sm font-bold text-transparent">
            Document Q&amp;A
          </h1>
          <p className="truncate text-[11px] text-text-muted">Ask your documents anything</p>
        </div>
        <ThemeToggle />
      </div>

      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-accent/15 text-accent"
                  : "text-text-muted hover:bg-tint hover:text-text"
              )}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="h-px bg-border" />

      <UploadZone />

      <DocumentList />

      <UserMenu />

      <p className="text-center text-[10px] text-text-muted">
        Built by{" "}
        <a
          href="https://github.com/prarthnagautam1094"
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-text-muted transition-colors hover:text-accent-cyan"
        >
          Prarthna Gautam
        </a>
      </p>
    </div>
  );
}

export function Sidebar({ mobileOpen, onClose }: SidebarProps) {
  return (
    <>
      {/* Desktop: static column, always visible */}
      <aside className="hidden w-72 shrink-0 border-r border-border bg-bg-sidebar md:block">
        <SidebarContent />
      </aside>

      {/* Mobile: slide-in drawer with backdrop */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/60 md:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onClose}
            />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 w-72 border-r border-border bg-bg-sidebar md:hidden"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "tween", duration: 0.2 }}
            >
              <button
                onClick={onClose}
                aria-label="Close menu"
                className="absolute right-3 top-3 rounded-md p-1.5 text-text-muted hover:bg-tint hover:text-text"
              >
                <X size={18} />
              </button>
              <SidebarContent />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
