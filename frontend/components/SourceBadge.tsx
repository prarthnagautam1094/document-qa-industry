"use client";

import { FileText } from "lucide-react";
import { parseSource } from "@/lib/utils";

/** Small citation pill for one "filename (p. N)" source string returned
 * by /chat/ask — parsed into filename + page for cleaner display, with
 * a title attribute carrying the full raw string so it's never lost even
 * if the badge itself truncates a long filename. */
export function SourceBadge({ source }: { source: string }) {
  const { filename, page } = parseSource(source);

  return (
    <span
      title={source}
      className="inline-flex max-w-[220px] items-center gap-1.5 rounded-full border border-border bg-tint px-2.5 py-1 font-mono text-[11px] text-text-muted transition-colors hover:border-accent-cyan/50 hover:text-accent-cyan"
    >
      <FileText size={11} className="shrink-0" />
      <span className="truncate">{filename}</span>
      {page && <span className="shrink-0 text-text-muted/70">p.{page}</span>}
    </span>
  );
}
