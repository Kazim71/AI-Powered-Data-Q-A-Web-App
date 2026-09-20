/** Formatting for values that came back from DuckDB via the API as `unknown`. */

const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

export function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return numberFormatter.format(value);
  return String(value);
}

export function isNumeric(value: unknown): boolean {
  return typeof value === "number";
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function pluralize(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

/** Recharts wants an array of {column: value} records; the API returns rows
 * as parallel arrays (a more compact wire format). Converted once at the
 * chart boundary rather than changing the API shape for one consumer. */
export function toRecords(
  columns: string[],
  rows: unknown[][]
): Record<string, unknown>[] {
  return rows.map((row) =>
    Object.fromEntries(columns.map((column, i) => [column, row[i]]))
  );
}
