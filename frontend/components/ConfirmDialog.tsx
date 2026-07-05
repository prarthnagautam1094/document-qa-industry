"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Generic confirm/cancel modal — used before any destructive action
 * (deleting a document, clearing all documents) so a misclick can't
 * silently wipe data. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = true,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onCancel}
        >
          <motion.div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
            className="shadow-elevated w-full max-w-sm rounded-2xl border border-border bg-bg-surface p-5"
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 8 }}
            transition={{ duration: 0.15 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-3">
              <div
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
                  destructive ? "bg-red-500/15 text-red-400" : "bg-accent/15 text-accent"
                )}
              >
                <AlertTriangle size={18} />
              </div>
              <div className="min-w-0">
                <h2 id="confirm-dialog-title" className="font-heading text-base font-bold text-text">
                  {title}
                </h2>
                <p className="mt-1 text-sm text-text-muted">{description}</p>
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={onCancel}
                className="rounded-lg border border-border px-3.5 py-1.5 text-sm font-medium text-text transition-colors hover:bg-tint"
              >
                {cancelLabel}
              </button>
              <button
                onClick={onConfirm}
                className={cn(
                  "rounded-lg px-3.5 py-1.5 text-sm font-medium text-white transition-colors",
                  destructive ? "bg-red-500 hover:bg-red-400" : "bg-accent hover:bg-accent-cyan hover:text-[#0B0E14]"
                )}
              >
                {confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
