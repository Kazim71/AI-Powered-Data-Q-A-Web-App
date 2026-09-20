import { cn } from "@/lib/utils";
import { formatCellValue, isNumeric } from "@/lib/format";

/** Scrolls within itself — never the page, per docs/09 §Mobile. Numbers are
 * right-aligned and set in the mono face with tabular figures so a column of
 * values actually lines up; text stays left-aligned and in the UI face. */
export function ResultTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: unknown[][];
}) {
  if (rows.length === 0) {
    return <p className="py-6 text-center text-sm text-text-muted">No rows returned.</p>;
  }

  return (
    <div className="max-h-80 overflow-auto rounded-[var(--radius-sm)] border border-border">
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 bg-surface-sunken">
          <tr>
            {columns.map((column) => (
              <th
                key={column}
                scope="col"
                className="border-b border-border px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-text-muted"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className={rowIndex % 2 === 1 ? "bg-surface-sunken/50" : undefined}
            >
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className={cn(
                    "border-b border-border px-3 py-1.5 font-data",
                    isNumeric(cell) ? "text-right" : "text-left"
                  )}
                >
                  {formatCellValue(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
