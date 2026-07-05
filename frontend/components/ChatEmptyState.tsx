"use client";

import { motion } from "framer-motion";
import { FileUp, Sparkles } from "lucide-react";

/** Shown in the main chat area before the first message — replaces what
 * would otherwise be a large empty void with a clear next step, which
 * differs depending on whether a document has been uploaded yet. */
export function ChatEmptyState({ hasDocuments }: { hasDocuments: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center"
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-accent/20 to-accent-cyan/20 text-accent-cyan">
        {hasDocuments ? <Sparkles size={26} /> : <FileUp size={26} />}
      </div>
      <div className="max-w-sm">
        <h2 className="font-heading text-lg font-bold text-text">
          {hasDocuments ? "Ask your first question" : "Upload a document to get started"}
        </h2>
        <p className="mt-2 text-sm text-text-muted">
          {hasDocuments
            ? "Ask anything grounded in the documents you've uploaded — answers include citations back to the source."
            : "Drop a PDF into the sidebar, then come back here to ask questions grounded in its content."}
        </p>
      </div>
    </motion.div>
  );
}
