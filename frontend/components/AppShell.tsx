"use client";

/**
 * Created by Prarthna Gautam (https://github.com/prarthnagautam1094) — 2026.
 * Part of the Document Q&A project.
 */

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Menu, Loader2 } from "lucide-react";
import { Toaster } from "sonner";
import { AppStateProvider, useAppState } from "@/context/AppStateContext";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ThemeProvider, useTheme } from "@/context/ThemeContext";
import { Sidebar } from "./Sidebar";
import { BackendOfflineScreen } from "./BackendOfflineScreen";

function ShellInner({ children }: { children: React.ReactNode }) {
  const { backendStatus, retryBackendCheck } = useAppState();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  if (backendStatus === "checking") {
    return (
      <div className="flex h-full w-full items-center justify-center bg-bg-page">
        <Loader2 size={24} className="animate-spin text-accent" />
      </div>
    );
  }

  if (backendStatus === "offline") {
    return <BackendOfflineScreen onRetry={retryBackendCheck} />;
  }

  return (
    <div className="flex h-full">
      <button
        onClick={() => setMobileSidebarOpen(true)}
        aria-label="Open menu"
        className="shadow-soft fixed left-4 top-4 z-30 flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-bg-surface text-text md:hidden"
      >
        <Menu size={18} />
      </button>

      <Sidebar mobileOpen={mobileSidebarOpen} onClose={() => setMobileSidebarOpen(false)} />

      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </div>
  );
}

/**
 * Gates every route except /login behind an authenticated Supabase
 * session. /login renders standalone (no sidebar/backend-status
 * takeover) since a signed-out visitor has nothing in the main app to
 * see yet. AppStateProvider — which immediately calls the
 * now-authentication-required /documents endpoint — is mounted only
 * once a session actually exists, so signed-out visitors never fire a
 * doomed, 401-bound request against it.
 */
function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user && pathname !== "/login") {
      router.replace("/login");
    } else if (user && pathname === "/login") {
      router.replace("/");
    }
  }, [loading, user, pathname, router]);

  if (pathname === "/login") {
    return <>{children}</>;
  }

  if (loading || !user) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-bg-page">
        <Loader2 size={24} className="animate-spin text-accent" />
      </div>
    );
  }

  return (
    <AppStateProvider>
      <ShellInner>{children}</ShellInner>
    </AppStateProvider>
  );
}

/** Sonner's own `theme` prop controls colors it draws itself (icons,
 * default fallback styling); toastOptions.style covers the rest. Split
 * into its own component so it can read the current theme via context
 * without ShellInner (which gates on backend status) needing to know
 * about theming at all. */
function ThemedToaster() {
  const { theme } = useTheme();
  return (
    <Toaster
      theme={theme}
      position="top-right"
      richColors
      toastOptions={{
        style: {
          background: "var(--color-bg-surface)",
          border: "1px solid var(--color-border)",
          color: "var(--color-text)",
        },
      }}
    />
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AuthGate>{children}</AuthGate>
        <ThemedToaster />
      </AuthProvider>
    </ThemeProvider>
  );
}
