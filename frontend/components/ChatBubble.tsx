"use client";

import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User } from "lucide-react";
import type { DisplayMessage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { SourceBadge } from "./SourceBadge";
import { SpeakButton } from "./SpeakButton";
import { TypingIndicator } from "./TypingIndicator";

export function ChatBubble({ message }: { message: DisplayMessage }) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={cn("flex w-full gap-3", isUser && "flex-row-reverse")}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-accent/20 text-accent" : "bg-accent-cyan/20 text-accent-cyan"
        )}
      >
        {isUser ? <User size={15} /> : <Bot size={15} />}
      </div>

      <div className={cn("flex max-w-[75%] flex-col gap-2", isUser && "items-end")}>
        <div
          className={cn(
            "shadow-soft rounded-2xl border px-4 py-2.5",
            isUser
              ? "border-accent/30 bg-accent/10 text-text"
              : "border-border bg-bg-surface text-text border-l-2 border-l-accent-cyan"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
          ) : message.pending ? (
            <TypingIndicator />
          ) : (
            <div className="prose-chat">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {!isUser && !message.pending && (
          <div className="flex flex-wrap items-center gap-1.5">
            <SpeakButton messageId={message.id} text={message.content} />
            {message.sources && message.sources.length > 0 && (
              <>
                {message.sources.map((source, i) => (
                  <SourceBadge key={`${source}-${i}`} source={source} />
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}
