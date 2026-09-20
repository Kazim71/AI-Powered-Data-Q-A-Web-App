import { ChevronRight, Link2 } from "lucide-react";
import { SemanticTypeBadge } from "@/components/ui/Badge";
import { pluralize } from "@/lib/format";
import type { SessionSchema } from "@/lib/types";

/**
 * The schema browser: tables, their columns with semantic-type badges, and
 * the relationships inferred between files. Shared between the desktop
 * sidebar and the mobile bottom sheet (docs/09 §Layout) so the two never
 * drift apart.
 */
export function SchemaContent({ schema }: { schema: SessionSchema }) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-muted">
          {pluralize(schema.tables.length, "table")}
        </h2>
        <div className="mt-2 flex flex-col gap-2">
          {schema.tables.map((table, i) => (
            <details
              key={table.name}
              open={i === 0}
              className="group rounded-[var(--radius-md)] border border-border bg-surface"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2.5 [&::-webkit-details-marker]:hidden">
                <span className="min-w-0">
                  <span className="block truncate font-data text-sm">{table.name}</span>
                  <span className="block truncate text-xs text-text-muted">
                    {table.source_file}
                    {table.sheet_name ? ` · ${table.sheet_name}` : ""} ·{" "}
                    {pluralize(table.row_count, "row")}
                  </span>
                </span>
                <ChevronRight
                  className="h-4 w-4 shrink-0 text-text-muted transition-transform duration-150 group-open:rotate-90"
                  aria-hidden
                />
              </summary>
              <ul className="border-t border-border px-3 py-2">
                {table.columns.map((column) => (
                  <li
                    key={column.name}
                    className="flex items-center justify-between gap-3 py-1.5 text-sm"
                  >
                    <span className="truncate font-data" title={column.original_name}>
                      {column.name}
                    </span>
                    <SemanticTypeBadge type={column.semantic_type} />
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </div>
      </div>

      {schema.join_hints.length > 0 && (
        <div>
          <h2 className="text-xs font-medium uppercase tracking-wide text-text-muted">
            {pluralize(schema.join_hints.length, "relationship")} found
          </h2>
          <ul className="mt-2 flex flex-col gap-1.5">
            {schema.join_hints.map((hint) => (
              <li
                key={`${hint.left_table}.${hint.left_column}-${hint.right_table}.${hint.right_column}`}
                className="flex items-start gap-2 rounded-[var(--radius-sm)] bg-surface-sunken px-2.5 py-2 text-xs"
              >
                <Link2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted" aria-hidden />
                <span className="font-data leading-relaxed">
                  {hint.left_table}.{hint.left_column} = {hint.right_table}.
                  {hint.right_column}
                  <span className="ml-1.5 font-sans text-text-muted">
                    ({Math.round(hint.overlap * 100)}% match)
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
