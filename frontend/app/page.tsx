"use client";

import { FileText } from "lucide-react";
import { useAppState } from "@/context/AppStateContext";
import { ChatInterface } from "@/components/ChatInterface";
import { PageHeader } from "@/components/PageHeader";

export default function ChatPage() {
  const { documents } = useAppState();

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        title="Chat"
        subtitle="Ask questions grounded in your own documents"
        right={
          <div className="hidden items-center gap-1.5 rounded-full border border-border bg-bg-surface px-3 py-1 text-xs text-text-muted sm:flex">
            <FileText size={12} />
            {documents.length} document{documents.length === 1 ? "" : "s"} loaded
          </div>
        }
      />
      <div className="min-h-0 flex-1">
        <ChatInterface />
      </div>
    </div>
  );
}
