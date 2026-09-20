"use client";

import { useCallback, useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { cn } from "@/lib/utils";

const ACCEPTED = ".csv,.tsv,.txt,.xlsx,.xls,.xlsm";

export function UploadZone({
  onFilesSelected,
  disabled,
}: {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;
      onFilesSelected(Array.from(fileList));
    },
    [onFilesSelected]
  );

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label="Upload CSV or Excel files"
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if (!disabled && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragging(false);
        if (!disabled) handleFiles(e.dataTransfer.files);
      }}
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-[var(--radius-md)]",
        "border-2 border-dashed px-6 py-14 text-center transition-colors duration-150",
        "cursor-pointer select-none",
        isDragging
          ? "border-primary bg-primary/5"
          : "border-border bg-surface hover:border-text-muted",
        disabled && "cursor-not-allowed opacity-50"
      )}
    >
      <UploadCloud className="h-6 w-6 text-text-muted" aria-hidden />
      <div>
        <p className="text-base font-medium">Drop CSV or Excel files here</p>
        <p className="mt-1 text-sm text-text-muted">
          or click to browse — you can add more than one at a time
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED}
        className="sr-only"
        disabled={disabled}
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = ""; // allow re-selecting the same file later
        }}
      />
    </div>
  );
}
