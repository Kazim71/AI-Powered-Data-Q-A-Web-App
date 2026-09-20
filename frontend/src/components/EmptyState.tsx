import { UploadZone } from "@/components/UploadZone";
import { UploadProgressList } from "@/components/UploadProgressList";
import { StatusBanner } from "@/components/ui/StatusBanner";
import type { UploadItem } from "@/hooks/useWorkspace";

/** The first thing every user sees. No marketing copy, no hero — just what
 * the tool does and where to start, per docs/09 §What that means. */
export function EmptyState({
  uploads,
  uploadProgress,
  connectionError,
  onFilesSelected,
}: {
  uploads: UploadItem[];
  uploadProgress: number | null;
  connectionError: string | null;
  onFilesSelected: (files: File[]) => void;
}) {
  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-6 py-16">
      <div>
        <h1 className="text-xl font-semibold">Ask questions about your data</h1>
        <p className="mt-1.5 text-sm text-text-muted">
          Upload one or more CSV or Excel files, then ask what you want to know in plain
          English — totals, averages, filters, comparisons, trends across all of them.
        </p>
      </div>

      {connectionError && (
        <StatusBanner tone="error">
          {connectionError}
          <span className="block text-xs text-text-muted mt-0.5">
            Once it&rsquo;s reachable, try uploading again.
          </span>
        </StatusBanner>
      )}

      <UploadZone onFilesSelected={onFilesSelected} />
      <p className="-mt-3 text-xs text-text-muted">
        CSV, TSV or Excel (.xlsx, .xls) · up to 50 MB per file · up to 10 files per session
      </p>
      <UploadProgressList uploads={uploads} progress={uploadProgress} />
    </div>
  );
}
