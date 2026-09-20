import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { UploadItem } from "@/hooks/useWorkspace";

export function UploadProgressList({
  uploads,
  progress,
}: {
  uploads: UploadItem[];
  progress: number | null;
}) {
  if (uploads.length === 0) return null;

  return (
    <div className="flex flex-col gap-1.5">
      {progress !== null && (
        <div className="mb-1 h-1 w-full overflow-hidden rounded-full bg-border">
          <div
            className="h-full bg-primary transition-[width] duration-150 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
      {uploads.map((upload) => (
        <div
          key={upload.filename}
          className="flex items-start gap-2 rounded-[var(--radius-sm)] border border-border bg-surface px-3 py-2 text-sm animate-rise-in"
        >
          <StatusIcon status={upload.status} />
          <div className="min-w-0 flex-1">
            <p className="truncate font-data">{upload.filename}</p>
            {upload.status === "failed" && upload.error && (
              <p className="mt-0.5 text-xs text-error">{upload.error}</p>
            )}
            {upload.status === "ok" && upload.tables && upload.tables.length > 0 && (
              <p className="mt-0.5 text-xs text-text-muted">
                → {upload.tables.join(", ")}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function StatusIcon({ status }: { status: UploadItem["status"] }) {
  if (status === "uploading")
    return (
      <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-text-muted" aria-hidden />
    );
  if (status === "ok")
    return <CheckCircle2 className={cn("mt-0.5 h-4 w-4 shrink-0 text-success")} aria-hidden />;
  return <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-error" aria-hidden />;
}
