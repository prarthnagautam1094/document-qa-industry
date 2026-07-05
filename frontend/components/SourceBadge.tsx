"use client";

import { FileText, Globe } from "lucide-react";
import { parseSource } from "@/lib/utils";

const WEB_SOURCE_PATTERN = /^https?:\/\//i;

/** Small citation pill for one source string returned by /chat/ask —
 * either a "filename (p. N)" document citation or a bare URL from a web
 * search result (see backend/services/rag_service.py's
 * ROUTE_BOTH/_web_source_label). A `source_type` of "both" means a
 * single answer's `sources` list can mix the two, so which icon/label to
 * render is decided per-badge from the string's own shape (a URL is
 * always a web source) rather than from the response-level source_type,
 * which only describes the overall routing decision. */
export function SourceBadge({ source }: { source: string }) {
  const isWebSource = WEB_SOURCE_PATTERN.test(source);

  if (isWebSource) {
    let label = source;
    try {
      label = new URL(source).hostname.replace(/^www\./, "");
    } catch {
      // Not a well-formed URL despite matching the pattern — fall back
      // to showing the raw string rather than crashing the badge.
    }

    return (
      <a
        href={source}
        target="_blank"
        rel="noopener noreferrer"
        title={source}
        className="inline-flex max-w-[220px] items-center gap-1.5 rounded-full border border-border bg-tint px-2.5 py-1 font-mono text-[11px] text-text-muted transition-colors hover:border-accent-cyan/50 hover:text-accent-cyan"
      >
        <Globe size={11} className="shrink-0" />
        <span className="truncate">{label}</span>
      </a>
    );
  }

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
