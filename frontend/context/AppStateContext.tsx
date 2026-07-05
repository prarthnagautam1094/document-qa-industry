"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  ApiError,
  checkHealth,
  deleteDocument as apiDeleteDocument,
  listDocuments,
  uploadDocuments as apiUploadDocuments,
} from "@/lib/api";
import type { DocumentInfo, UploadResponse } from "@/lib/types";

export type BackendStatus = "checking" | "online" | "offline";

interface AppStateValue {
  backendStatus: BackendStatus;
  retryBackendCheck: () => void;
  documents: DocumentInfo[];
  documentsLoading: boolean;
  documentsError: string | null;
  refreshDocuments: () => Promise<void>;
  uploadDocuments: (files: File[]) => Promise<UploadResponse>;
  removeDocument: (filename: string) => Promise<void>;
}

const AppStateContext = createContext<AppStateValue | null>(null);

/**
 * Owns backend connectivity and the document list — both are needed by
 * the sidebar (upload/list/delete) and the chat page (to gate the input
 * on "at least one document uploaded" and to show the global
 * backend-not-connected state), which live on either side of the
 * app/layout.tsx boundary and can't share props directly. Mounted once
 * in AppShell, above both.
 */
export function AppStateProvider({ children }: { children: ReactNode }) {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsError, setDocumentsError] = useState<string | null>(null);

  const checkBackend = useCallback(async (): Promise<BackendStatus> => {
    try {
      await checkHealth();
      setBackendStatus("online");
      return "online";
    } catch {
      setBackendStatus("offline");
      return "offline";
    }
  }, []);

  const refreshDocuments = useCallback(async () => {
    setDocumentsLoading(true);
    setDocumentsError(null);
    try {
      const res = await listDocuments();
      setDocuments(res.documents);
      setBackendStatus("online");
    } catch (err) {
      if (err instanceof ApiError && err.kind === "network") {
        setBackendStatus("offline");
      } else {
        setDocumentsError(err instanceof Error ? err.message : "Failed to load documents.");
      }
    } finally {
      setDocumentsLoading(false);
    }
  }, []);

  // Initial check on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const status = await checkBackend();
      if (!cancelled && status === "online") {
        await refreshDocuments();
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Ongoing polling: fast while offline (to notice recovery quickly),
  // slower while online (to notice a mid-session backend crash without
  // hammering it). Refreshes the document list right when we transition
  // from offline back to online.
  useEffect(() => {
    const intervalMs = backendStatus === "offline" ? 5000 : 15000;
    const interval = setInterval(async () => {
      const wasOffline = backendStatus === "offline";
      const status = await checkBackend();
      if (wasOffline && status === "online") {
        await refreshDocuments();
      }
    }, intervalMs);
    return () => clearInterval(interval);
  }, [backendStatus, checkBackend, refreshDocuments]);

  const uploadDocuments = useCallback(
    async (files: File[]) => {
      const result = await apiUploadDocuments(files);
      await refreshDocuments();
      return result;
    },
    [refreshDocuments]
  );

  const removeDocument = useCallback(
    async (filename: string) => {
      await apiDeleteDocument(filename);
      await refreshDocuments();
    },
    [refreshDocuments]
  );

  const value: AppStateValue = {
    backendStatus,
    retryBackendCheck: () => {
      checkBackend().then((status) => {
        if (status === "online") refreshDocuments();
      });
    },
    documents,
    documentsLoading,
    documentsError,
    refreshDocuments,
    uploadDocuments,
    removeDocument,
  };

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateValue {
  const ctx = useContext(AppStateContext);
  if (!ctx) {
    throw new Error("useAppState must be used within AppStateProvider");
  }
  return ctx;
}
