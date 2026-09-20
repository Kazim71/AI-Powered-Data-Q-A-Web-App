"use client";

import { useState } from "react";
import { Database, Plus, RotateCcw, X } from "lucide-react";
import { AskBar } from "@/components/AskBar";
import { DataSheet } from "@/components/DataSheet";
import { EmptyState } from "@/components/EmptyState";
import { SchemaSidebar } from "@/components/SchemaSidebar";
import { Turn } from "@/components/Turn";
import { UploadProgressList } from "@/components/UploadProgressList";
import { UploadZone } from "@/components/UploadZone";
import { Button } from "@/components/ui/Button";
import { StatusBanner } from "@/components/ui/StatusBanner";
import { useWorkspace } from "@/hooks/useWorkspace";

export default function Home() {
  const workspace = useWorkspace();
  const [dataSheetOpen, setDataSheetOpen] = useState(false);
  const [addFilesOpen, setAddFilesOpen] = useState(false);

  if (workspace.sessionExpired) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-4 px-4 text-center">
        <StatusBanner tone="warning">
          This session has expired. Your uploaded files are no longer available — start a new
          session to continue.
        </StatusBanner>
        <Button variant="secondary" onClick={workspace.reset}>
          Start a new session
        </Button>
      </main>
    );
  }

  if (!workspace.hasData) {
    return (
      <main className="min-h-dvh px-4">
        <EmptyState
          uploads={workspace.uploads}
          uploadProgress={workspace.uploadProgress}
          connectionError={workspace.connectionError}
          onFilesSelected={workspace.handleFilesSelected}
        />
      </main>
    );
  }

  return (
    <div className="flex h-dvh flex-col md:flex-row">
      <SchemaSidebar schema={workspace.schema} />
      <DataSheet
        schema={workspace.schema}
        open={dataSheetOpen}
        onClose={() => setDataSheetOpen(false)}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border px-4 py-3 md:px-6">
          <p className="text-sm font-medium">Data Q&A</p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setDataSheetOpen(true)}
              className="flex h-9 items-center gap-1.5 rounded-[var(--radius-sm)] border border-border px-3 text-sm md:hidden"
            >
              <Database className="h-3.5 w-3.5" aria-hidden />
              Data
            </button>
            <button
              onClick={workspace.reset}
              className="flex h-9 items-center gap-1.5 rounded-[var(--radius-sm)] px-2 text-sm text-text-muted hover:bg-surface-sunken hover:text-text"
              title="Start a new session — this session's files stay uploaded until it expires"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden />
              <span className="hidden sm:inline">New session</span>
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-5 md:px-6">
          <div className="mx-auto flex max-w-3xl flex-col gap-6">
            {workspace.coldStart && (
              <StatusBanner tone="info">
                The server is waking up from being idle — this can take up to a minute on the
                free tier. Your question is still in progress.
              </StatusBanner>
            )}

            <div>
              <button
                onClick={() => setAddFilesOpen((v) => !v)}
                className="flex h-9 items-center gap-1.5 text-sm text-text-muted hover:text-text"
              >
                {addFilesOpen ? (
                  <X className="h-3.5 w-3.5" aria-hidden />
                ) : (
                  <Plus className="h-3.5 w-3.5" aria-hidden />
                )}
                {addFilesOpen ? "Cancel" : "Add more files"}
              </button>
              {addFilesOpen && (
                <div className="mt-2">
                  <UploadZone onFilesSelected={workspace.handleFilesSelected} />
                </div>
              )}
              <div className="mt-2">
                <UploadProgressList
                  uploads={workspace.uploads}
                  progress={workspace.uploadProgress}
                />
              </div>
            </div>

            {workspace.turns.length === 0 ? (
              <p className="py-8 text-center text-sm text-text-muted">
                Your files are ready. Ask a question below to get started.
              </p>
            ) : (
              <div className="flex flex-col gap-8">
                {workspace.turns.map((turn, i) => (
                  <div
                    key={turn.id}
                    className={i > 0 ? "border-t border-border pt-8" : undefined}
                  >
                    <Turn turn={turn} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-border bg-bg px-4 py-3 md:px-6">
          <div className="mx-auto max-w-3xl">
            <AskBar
              disabled={!workspace.hasData}
              isAsking={workspace.isAsking}
              onSubmit={workspace.submitQuestion}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
