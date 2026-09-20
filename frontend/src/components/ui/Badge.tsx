import { cn } from "@/lib/utils";
import type { SemanticType } from "@/lib/types";

// Semantic-type colour mapping: a controlled, small set (docs/09 §Colour),
// re-used everywhere a column's type needs to be legible at a glance —
// the schema sidebar, and result-table headers.
const SEMANTIC_TYPE_LABEL: Record<SemanticType, string> = {
  identifier: "id",
  numeric: "num",
  temporal: "date",
  categorical: "cat",
  boolean: "bool",
  text: "text",
};

const SEMANTIC_TYPE_DOT: Record<SemanticType, string> = {
  identifier: "bg-text-muted",
  numeric: "bg-primary",
  temporal: "bg-info",
  categorical: "bg-accent",
  boolean: "bg-success",
  text: "bg-border",
};

export function SemanticTypeBadge({ type }: { type: SemanticType }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-text-muted">
      <span
        className={cn("h-1.5 w-1.5 rounded-full shrink-0", SEMANTIC_TYPE_DOT[type])}
        aria-hidden
      />
      <span className="font-data uppercase tracking-wide">
        {SEMANTIC_TYPE_LABEL[type]}
      </span>
    </span>
  );
}

type Tone = "success" | "warning" | "error" | "info" | "accent";

const TONE_CLASSES: Record<Tone, string> = {
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  error: "bg-error/10 text-error",
  info: "bg-info/10 text-info",
  accent: "bg-accent/10 text-accent",
};

export function Badge({
  tone = "info",
  children,
  className,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[var(--radius-sm)] px-2 py-0.5 text-xs font-medium",
        TONE_CLASSES[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
