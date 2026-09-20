"use client";

import { useCallback, useState } from "react";
import { ApiError, ask, createSession, getSchema, uploadFiles } from "@/lib/api";
import type { AskResponse, SessionSchema } from "@/lib/types";

export interface UploadItem {
  filename: string;
  status: "uploading" | "ok" | "failed";
  error?: string | null;
  tables?: string[];
}

export interface Turn {
  id: string;
  question: string;
  status: "pending" | "done" | "error";
  response?: AskResponse;
  error?: string;
}

let turnCounter = 0;

export function useWorkspace() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [schema, setSchema] = useState<SessionSchema | null>(null);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [coldStart, setColdStart] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [isAsking, setIsAsking] = useState(false);

  const ensureSession = useCallback(async (): Promise<string> => {
    if (sessionId) return sessionId;
    const { session_id } = await createSession();
    setSessionId(session_id);
    return session_id;
  }, [sessionId]);

  const handleFilesSelected = useCallback(
    async (files: File[]) => {
      setSessionExpired(false);
      setConnectionError(null);
      let sid: string;
      try {
        sid = await ensureSession();
      } catch (err) {
        // Creating a session can only fail because the backend is
        // unreachable or misconfigured — there is no existing session that
        // could have "expired" yet. Labelling this as expiry would send the
        // user to "start a new session," which fails the exact same way.
        setConnectionError(
          err instanceof ApiError
            ? err.message
            : "Could not reach the backend. Is it running?"
        );
        return;
      }

      // All files in a batch upload as one HTTP request, so progress is
      // necessarily aggregate (one number for the whole request body) —
      // each file's individual outcome (ok/failed) only exists once the
      // server responds, and is shown then. See docs/09 for the states
      // this is meant to cover.
      setUploads((prev) => [
        ...prev,
        ...files.map((f) => ({ filename: f.name, status: "uploading" as const })),
      ]);
      setUploadProgress(0);

      try {
        const result = await uploadFiles(sid, files, (loaded, total) => {
          setUploadProgress(total > 0 ? Math.round((loaded / total) * 100) : null);
        });
        setSchema(result.schema);
        setUploads((prev) =>
          prev.map((u) => {
            const match = result.files.find((f) => f.filename === u.filename);
            if (!match) return u;
            return {
              filename: u.filename,
              status: match.status,
              error: match.error,
              tables: match.tables,
            };
          })
        );
      } catch (err) {
        // A 404 here means the session genuinely existed and is now gone
        // (expired server-side) — a real expiry, unlike the createSession
        // failure above. Anything else (network failure, 5xx) just failed
        // this upload; mark the affected files failed rather than nuking
        // the whole workspace over what might be transient.
        if (err instanceof ApiError && err.status === 404) {
          setSessionExpired(true);
          setUploads((prev) =>
            prev.filter(
              (u) => !(files.some((f) => f.name === u.filename) && u.status === "uploading")
            )
          );
          return;
        }
        const message = err instanceof ApiError ? err.message : "Upload failed";
        setUploads((prev) =>
          prev.map((u) =>
            files.some((f) => f.name === u.filename) && u.status === "uploading"
              ? { ...u, status: "failed", error: message }
              : u
          )
        );
      } finally {
        setUploadProgress(null);
      }
    },
    [ensureSession]
  );

  const refreshSchema = useCallback(async () => {
    if (!sessionId) return;
    try {
      setSchema(await getSchema(sessionId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setSessionExpired(true);
    }
  }, [sessionId]);

  const submitQuestion = useCallback(
    async (question: string) => {
      if (!sessionId) return;
      const id = `turn-${++turnCounter}`;
      setTurns((prev) => [...prev, { id, question, status: "pending" }]);
      setIsAsking(true);
      setColdStart(false);

      try {
        const response = await ask(sessionId, question, {
          onSlow: () => setColdStart(true),
        });
        setTurns((prev) =>
          prev.map((t) => (t.id === id ? { ...t, status: "done", response } : t))
        );
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setSessionExpired(true);
          setTurns((prev) => prev.filter((t) => t.id !== id));
          return;
        }
        const message = err instanceof ApiError ? err.message : "Something went wrong.";
        setTurns((prev) =>
          prev.map((t) => (t.id === id ? { ...t, status: "error", error: message } : t))
        );
      } finally {
        setIsAsking(false);
        setColdStart(false);
      }
    },
    [sessionId]
  );

  const reset = useCallback(() => {
    setSessionId(null);
    setSchema(null);
    setUploads([]);
    setUploadProgress(null);
    setTurns([]);
    setColdStart(false);
    setSessionExpired(false);
    setConnectionError(null);
    setIsAsking(false);
  }, []);

  return {
    sessionId,
    schema,
    uploads,
    uploadProgress,
    turns,
    coldStart,
    sessionExpired,
    connectionError,
    isAsking,
    handleFilesSelected,
    submitQuestion,
    refreshSchema,
    reset,
    dismissConnectionError: () => setConnectionError(null),
    hasData: !!schema && schema.tables.length > 0,
  };
}
