import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind class lists, letting later classes win over conflicting earlier ones. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface ParsedSource {
  filename: string;
  page: string | null;
  raw: string;
}

const SOURCE_PATTERN = /^(.*)\s\(p\.\s*(.+)\)$/;

/**
 * Parse the backend's "filename (p. N)" citation strings into structured
 * {filename, page} for nicer badge rendering. Falls back to showing the
 * raw string as the filename if it doesn't match the expected shape —
 * the backend's format is a display convention, not a contract, so a
 * future wording change here should degrade gracefully instead of
 * crashing the citation badges.
 */
export function parseSource(raw: string): ParsedSource {
  const match = raw.match(SOURCE_PATTERN);
  if (!match) {
    return { filename: raw, page: null, raw };
  }
  return { filename: match[1], page: match[2], raw };
}

export function formatTimestamp(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}
