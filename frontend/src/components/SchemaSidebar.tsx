import { Database } from "lucide-react";
import { SchemaContent } from "@/components/SchemaContent";
import type { SessionSchema } from "@/lib/types";

export function SchemaSidebar({ schema }: { schema: SessionSchema | null }) {
  return (
    <aside
      aria-label="Uploaded data"
      className="hidden w-72 shrink-0 overflow-y-auto border-r border-border bg-surface px-4 py-5 md:block"
    >
      {schema && schema.tables.length > 0 ? (
        <SchemaContent schema={schema} />
      ) : (
        <div className="flex flex-col items-center gap-2 px-2 py-10 text-center text-sm text-text-muted">
          <Database className="h-5 w-5" aria-hidden />
          <p>Upload a file to see its tables and columns here.</p>
        </div>
      )}
    </aside>
  );
}
