/**
 * Mirrors backend/app/models.py. Kept as a hand-written twin rather than a
 * generated client: the API surface is small and stable, and a generator
 * would be more ceremony than the four endpoints below justify.
 */

export type SemanticType =
  | "numeric"
  | "temporal"
  | "categorical"
  | "identifier"
  | "boolean"
  | "text";

export interface ColumnProfile {
  name: string;
  original_name: string;
  dtype: string;
  semantic_type: SemanticType;
  null_count: number;
  null_fraction: number;
  distinct_count: number;
  sample_values: unknown[];
  min_value: unknown;
  max_value: unknown;
  categories: unknown[] | null;
}

export interface TableProfile {
  name: string;
  source_file: string;
  sheet_name: string | null;
  row_count: number;
  columns: ColumnProfile[];
}

export interface JoinHint {
  left_table: string;
  left_column: string;
  right_table: string;
  right_column: string;
  overlap: number;
  confidence: "high" | "medium" | "low";
}

export interface SessionSchema {
  session_id: string;
  created_at: string;
  tables: TableProfile[];
  join_hints: JoinHint[];
}

export interface UploadedFileResult {
  filename: string;
  status: "ok" | "failed";
  tables: string[];
  error: string | null;
}

export interface UploadResponse {
  session_id: string;
  files: UploadedFileResult[];
  schema: SessionSchema;
}

export type ChartType = "kpi" | "line" | "bar" | "pie" | "scatter" | "table";

export interface ChartSpec {
  type: ChartType;
  x: string | null;
  y: string[];
  reason: string;
}

export interface AskResponse {
  answer: string;
  sql: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  chart: ChartSpec;
  tables_used: string[];
  repaired: boolean;
  assumptions: string[];
}

/** A structured API error, as returned by every backend error response. */
export interface ApiErrorBody {
  error: string;
  detail?: string | null;
}
