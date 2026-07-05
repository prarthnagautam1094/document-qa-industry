"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FileText, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useAppState } from "@/context/AppStateContext";
import { ApiError } from "@/lib/api";
import { ConfirmDialog } from "./ConfirmDialog";

/** Document list with per-item and "clear all" delete, both gated behind
 * a confirmation dialog — deleting a document also drops its vectors
 * from the store, so this is a destructive, non-undoable action. */
export function DocumentList() {
  const { documents, documentsLoading, removeDocument } = useAppState();
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [pendingClearAll, setPendingClearAll] = useState(false);
  const [deletingFilename, setDeletingFilename] = useState<string | null>(null);
  const [isClearingAll, setIsClearingAll] = useState(false);

  const handleConfirmDelete = async () => {
    if (!pendingDelete) return;
    const filename = pendingDelete;
    setPendingDelete(null);
    setDeletingFilename(filename);
    try {
      await removeDocument(filename);
      toast.success(`Removed "${filename}".`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : `Could not remove "${filename}".`);
    } finally {
      setDeletingFilename(null);
    }
  };

  const handleClearAll = async () => {
    setPendingClearAll(false);
    setIsClearingAll(true);
    const names = documents.map((d) => d.filename);
    let failures = 0;
    for (const name of names) {
      try {
        await removeDocument(name);
      } catch {
        failures += 1;
      }
    }
    setIsClearingAll(false);
    if (failures === 0) {
      toast.success("Cleared all documents.");
    } else {
      toast.error(`Cleared ${names.length - failures} of ${names.length} documents.`);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-heading text-xs font-bold uppercase tracking-wider text-text-muted">
          Documents{documents.length > 0 && ` (${documents.length})`}
        </h2>
        {documents.length > 0 && (
          <button
            onClick={() => setPendingClearAll(true)}
            disabled={isClearingAll}
            className="text-xs font-medium text-text-muted transition-colors hover:text-red-400 disabled:opacity-50"
          >
            Clear all
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {documentsLoading && documents.length === 0 ? (
          <div className="space-y-2">
            {[0, 1].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-lg bg-tint" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border px-3 py-6 text-center">
            <FileText size={20} className="mx-auto mb-2 text-text-muted" />
            <p className="text-xs text-text-muted">No documents uploaded yet.</p>
          </div>
        ) : (
          <ul className="space-y-1.5">
            <AnimatePresence initial={false}>
              {documents.map((doc) => (
                <motion.li
                  key={doc.filename}
                  layout
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex items-center gap-2 rounded-lg border border-border bg-bg-surface px-2.5 py-2"
                >
                  <FileText size={15} className="shrink-0 text-accent-cyan" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-text" title={doc.filename}>
                      {doc.filename}
                    </p>
                    <p className="text-xs text-text-muted">{doc.chunk_count} chunks</p>
                  </div>
                  <button
                    onClick={() => setPendingDelete(doc.filename)}
                    disabled={deletingFilename === doc.filename}
                    aria-label={`Delete ${doc.filename}`}
                    className="shrink-0 rounded-md p-1.5 text-text-muted transition-colors hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50"
                  >
                    <Trash2 size={14} />
                  </button>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete document?"
        description={`"${pendingDelete}" and all of its indexed content will be permanently removed.`}
        confirmLabel="Delete"
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
      <ConfirmDialog
        open={pendingClearAll}
        title="Clear all documents?"
        description={`This will permanently remove all ${documents.length} uploaded document(s).`}
        confirmLabel="Clear all"
        onConfirm={handleClearAll}
        onCancel={() => setPendingClearAll(false)}
      />
    </div>
  );
}
