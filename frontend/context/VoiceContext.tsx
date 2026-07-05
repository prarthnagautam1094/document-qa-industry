"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useSpeechSynthesis } from "@/hooks/useSpeechSynthesis";

const AUTO_READ_STORAGE_KEY = "autoReadResponses";

interface VoiceContextValue {
  isSupported: boolean;
  /** The DisplayMessage.id currently being read aloud, or null if
   * nothing is speaking — lets each ChatBubble's speaker button know
   * whether *it* is the one active, since only one utterance can play
   * at a time app-wide. */
  speakingMessageId: string | null;
  toggleSpeak: (id: string, text: string) => void;
  autoReadEnabled: boolean;
  setAutoReadEnabled: (enabled: boolean) => void;
  speakIfAutoRead: (id: string, text: string) => void;
}

const VoiceContext = createContext<VoiceContextValue | null>(null);

/**
 * Owns the single browser-global SpeechSynthesis instance (see
 * useSpeechSynthesis — only one utterance can ever play at a time) and
 * the "auto-read new responses" preference, shared between the sidebar
 * toggle and every ChatBubble's speaker button, which live in different
 * parts of the tree and can't share plain component state directly.
 * Mounted once in AppShell, above both.
 */
export function VoiceProvider({ children }: { children: ReactNode }) {
  const { isSupported, speak, stop } = useSpeechSynthesis();
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const [autoReadEnabled, setAutoReadEnabledState] = useState(false);

  // Read the persisted preference on mount only (client-only storage —
  // the server-rendered default of `false` above matches what a fresh
  // client render shows before this effect runs, so there's no
  // hydration mismatch to guard against here). This genuinely needs an
  // effect (not a lazy useState initializer): computing it during render
  // would make the client's very first render diverge from the server-
  // rendered markup, which is the hydration mismatch this pattern avoids
  // by design — deferring the read to after mount is the fix, not a gap.
  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAutoReadEnabledState(window.localStorage.getItem(AUTO_READ_STORAGE_KEY) === "true");
    } catch {
      // localStorage can throw in private-browsing/disabled-storage
      // contexts — auto-read just stays off for this session.
    }
  }, []);

  const toggleSpeak = useCallback(
    (id: string, text: string) => {
      if (speakingMessageId === id) {
        stop();
        setSpeakingMessageId(null);
        return;
      }
      setSpeakingMessageId(id);
      // The functional updater only clears speakingMessageId if it still
      // points at *this* utterance's id — if the user has since clicked
      // a different bubble (or the auto-read hook started a newer one),
      // that later call already overwrote it, and this stale onEnd must
      // not clobber it back to null.
      speak(text, { onEnd: () => setSpeakingMessageId((current) => (current === id ? null : current)) });
    },
    [speakingMessageId, speak, stop]
  );

  const setAutoReadEnabled = useCallback((enabled: boolean) => {
    setAutoReadEnabledState(enabled);
    try {
      window.localStorage.setItem(AUTO_READ_STORAGE_KEY, String(enabled));
    } catch {
      // Same as above — the toggle still works for the current session,
      // it just won't persist across a refresh.
    }
  }, []);

  const speakIfAutoRead = useCallback(
    (id: string, text: string) => {
      if (!autoReadEnabled) return;
      setSpeakingMessageId(id);
      speak(text, { onEnd: () => setSpeakingMessageId((current) => (current === id ? null : current)) });
    },
    [autoReadEnabled, speak]
  );

  const value: VoiceContextValue = {
    isSupported,
    speakingMessageId,
    toggleSpeak,
    autoReadEnabled,
    setAutoReadEnabled,
    speakIfAutoRead,
  };

  return <VoiceContext.Provider value={value}>{children}</VoiceContext.Provider>;
}

export function useVoice(): VoiceContextValue {
  const ctx = useContext(VoiceContext);
  if (!ctx) {
    throw new Error("useVoice must be used within VoiceProvider");
  }
  return ctx;
}
