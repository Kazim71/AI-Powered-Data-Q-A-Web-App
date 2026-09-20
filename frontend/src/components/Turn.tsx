import { ChevronRight, Loader2 } from "lucide-react";
import { ChartView } from "@/components/ChartView";
import { ResultTable } from "@/components/ResultTable";
import { Badge } from "@/components/ui/Badge";
import { StatusBanner } from "@/components/ui/StatusBanner";
import { pluralize } from "@/lib/format";
import type { Turn as TurnData } from "@/hooks/useWorkspace";

/**
 * One question-and-answer turn. Order follows docs/09's progressive
 * disclosure: answer → chart → table → SQL (collapsed) → what was used.
 * Every turn keeps this order regardless of how it turned out, so the eye
 * always knows where to look next.
 */
export function Turn({ turn }: { turn: TurnData }) {
  return (
    <div className="flex flex-col gap-3 animate-rise-in">
      <p className="text-sm text-text-muted">{turn.question}</p>

      {turn.status === "pending" && (
        <div className="flex items-center gap-2 text-sm text-text-muted">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Thinking through your data…
        </div>
      )}

      {turn.status === "error" && (
        <StatusBanner tone="error">{turn.error ?? "Something went wrong."}</StatusBanner>
      )}

      {turn.status === "done" && turn.response && <TurnResult response={turn.response} />}
    </div>
  );
}

function TurnResult({ response }: { response: NonNullable<TurnData["response"]> }) {
  const showChart = response.chart.type !== "table" && response.rows.length > 0;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-lg font-medium leading-snug">{response.answer}</p>

      {response.assumptions.length > 0 && (
        <ul className="flex flex-col gap-1">
          {response.assumptions.map((assumption) => (
            <li key={assumption} className="flex items-start gap-1.5 text-sm text-text-muted">
              <Badge tone="accent" className="mt-0.5 shrink-0">
                Assumption
              </Badge>
              <span>{assumption}</span>
            </li>
          ))}
        </ul>
      )}

      {response.repaired && (
        <StatusBanner tone="warning">
          The first query needed one correction before it ran.
        </StatusBanner>
      )}

      {response.truncated && (
        <StatusBanner tone="info">
          Showing the first {response.row_count.toLocaleString()} rows — the full result was
          larger.
        </StatusBanner>
      )}

      {showChart && <ChartView result={response} />}

      <details className="group" open={!showChart}>
        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm text-text-muted [&::-webkit-details-marker]:hidden">
          <ChevronRight
            className="h-3.5 w-3.5 transition-transform duration-150 group-open:rotate-90"
            aria-hidden
          />
          {pluralize(response.row_count, "row")}
          {showChart ? " · view as a table" : ""}
        </summary>
        <div className="mt-2">
          <ResultTable columns={response.columns} rows={response.rows} />
        </div>
      </details>

      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm text-text-muted [&::-webkit-details-marker]:hidden">
          <ChevronRight
            className="h-3.5 w-3.5 transition-transform duration-150 group-open:rotate-90"
            aria-hidden
          />
          SQL used
          <span className="font-data text-xs">({response.tables_used.join(", ")})</span>
        </summary>
        <pre className="mt-2 overflow-x-auto rounded-[var(--radius-sm)] bg-surface-sunken px-3 py-2.5 font-data text-xs leading-relaxed">
          {response.sql}
        </pre>
      </details>
    </div>
  );
}
