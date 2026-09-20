import { AlertTriangle, Info, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "info" | "warning" | "error" | "success";

const TONE_STYLES: Record<Tone, { icon: typeof Info; classes: string }> = {
  info: { icon: Info, classes: "bg-info/10 text-info" },
  warning: { icon: AlertTriangle, classes: "bg-warning/10 text-warning" },
  error: { icon: XCircle, classes: "bg-error/10 text-error" },
  success: { icon: CheckCircle2, classes: "bg-success/10 text-success" },
};

/** A single-line, icon-led notice — used for cold start, session expiry,
 * partial upload failure, a repaired query. Never a modal, never a toast
 * that disappears on its own: these are facts the user should be able to
 * re-read. */
export function StatusBanner({
  tone,
  children,
  className,
}: {
  tone: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  const { icon: Icon, classes } = TONE_STYLES[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "flex items-start gap-2 rounded-[var(--radius-sm)] px-3 py-2 text-sm",
        classes,
        className
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}
