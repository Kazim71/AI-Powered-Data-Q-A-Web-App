"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { SchemaContent } from "@/components/SchemaContent";
import type { SessionSchema } from "@/lib/types";

/** Mobile equivalent of the desktop schema sidebar (docs/09 §Mobile): a
 * bottom sheet so the ask bar and the latest turn keep the full screen. */
export function DataSheet({
  schema,
  open,
  onClose,
}: {
  schema: SessionSchema | null;
  open: boolean;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 md:hidden">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Uploaded data"
        tabIndex={-1}
        className="absolute inset-x-0 bottom-0 max-h-[75vh] overflow-y-auto rounded-t-[var(--radius-md)] border-t border-border bg-surface p-4 pb-8 shadow-lg outline-none"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium">Your data</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-[var(--radius-sm)] p-1.5 text-text-muted hover:bg-surface-sunken"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        {schema && schema.tables.length > 0 ? (
          <SchemaContent schema={schema} />
        ) : (
          <p className="py-6 text-center text-sm text-text-muted">
            Upload a file to see its tables and columns here.
          </p>
        )}
      </div>
    </div>
  );
}
