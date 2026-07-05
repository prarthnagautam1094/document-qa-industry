"use client";

import { useCallback, useRef, useState } from "react";
import { motion } from "framer-motion";
import { UploadCloud } from "lucide-react";
import { toast } from "sonner";
import { useAppState } from "@/context/AppStateContext";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Drag-and-drop (or click-to-browse) PDF upload zone. Accepts multiple
 * files in one request and surfaces the backend's per-file results —
 * one bad PDF in a batch doesn't fail the whole thing, so the toast
 * reflects that (a "3 of 4 uploaded" partial-success case, not just
 * pass/fail). */
export function UploadZone() {
  const { uploadDocuments } = useAppState();
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const doUpload = useCallback(
    async (fileList: FileList | File[]) => {
      const files = Array.from(fileList);
      if (files.length === 0) return;

      setIsUploading(true);
      try {
        const response = await uploadDocuments(files);
        const succeeded = response.results.filter((r) => r.status === "success");
        const failed = response.results.filter((r) => r.status === "failed");

        if (succeeded.length > 0) {
          toast.success(
            succeeded.length === 1
              ? `Uploaded "${succeeded[0].filename}" (${succeeded[0].chunk_count} chunks).`
              : `Uploaded ${succeeded.length} of ${response.results.length} files (${response.total_chunks} chunks total).`
          );
        }
        for (const failure of failed) {
          toast.error(`"${failure.filename}" failed: ${failure.detail ?? "Unknown error."}`);
        }
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
      } finally {
        setIsUploading(false);
      }
    },
    [uploadDocuments]
  );

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files) void doUpload(e.target.files);
          e.target.value = "";
        }}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          if (e.dataTransfer.files) void doUpload(e.dataTransfer.files);
        }}
        disabled={isUploading}
        className={cn(
          "relative flex w-full flex-col items-center justify-center gap-1.5 overflow-hidden rounded-xl border border-dashed px-4 py-6 text-center transition-colors",
          isDragging
            ? "border-accent-cyan bg-accent-cyan/5"
            : "border-border bg-bg-surface hover:border-accent-cyan/60",
          isUploading && "cursor-wait opacity-80"
        )}
      >
        <UploadCloud size={22} className={isDragging ? "text-accent-cyan" : "text-text-muted"} />
        <span className="text-sm font-medium text-text">
          {isUploading ? "Uploading…" : "Drop PDFs here or click to browse"}
        </span>
        <span className="text-xs text-text-muted">Multiple files supported</span>

        {isUploading && (
          <div className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden bg-border">
            <motion.div
              className="h-full w-1/3 bg-gradient-to-r from-accent to-accent-cyan"
              animate={{ x: ["-100%", "300%"] }}
              transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>
        )}
      </button>
    </div>
  );
}
