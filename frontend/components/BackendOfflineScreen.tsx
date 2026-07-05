"use client";

import { motion } from "framer-motion";
import { RefreshCw, ServerCrash } from "lucide-react";
import { getApiUrl } from "@/lib/api";

/** Full-page takeover shown whenever the backend is unreachable — shown
 * instead of a half-functional UI (empty document list, chat input that
 * would just error on submit) so the failure mode is obvious rather than
 * looking like a bug. */
export function BackendOfflineScreen({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-4 bg-bg-page px-6 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.25 }}
        className="flex h-16 w-16 items-center justify-center rounded-2xl border border-border bg-bg-surface text-red-400"
      >
        <ServerCrash size={28} />
      </motion.div>
      <div className="max-w-sm">
        <h1 className="font-heading text-lg font-bold text-text">Backend not connected</h1>
        <p className="mt-2 text-sm text-text-muted">
          Couldn&apos;t reach the API at{" "}
          <code className="rounded bg-tint px-1.5 py-0.5 font-mono text-xs text-accent-cyan">
            {getApiUrl()}
          </code>
          . Make sure the FastAPI backend is running, then try again.
        </p>
      </div>
      <button
        onClick={onRetry}
        className="mt-2 flex items-center gap-2 rounded-lg bg-gradient-to-r from-accent to-accent-cyan px-4 py-2 text-sm font-medium text-[#0B0E14] transition-opacity hover:opacity-90"
      >
        <RefreshCw size={15} />
        Retry connection
      </button>
    </div>
  );
}
