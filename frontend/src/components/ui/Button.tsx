import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

// One clear hierarchy: primary (the single active call to action at a time),
// secondary (bordered, for a parallel but lesser action), ghost (text-only,
// for a collapse/expand toggle). No pill shapes, no gradients, no glow.
const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-primary text-primary-contrast hover:opacity-90 disabled:opacity-40",
  secondary:
    "border border-border bg-surface text-text hover:bg-surface-sunken disabled:opacity-40",
  ghost: "text-text-muted hover:text-text disabled:opacity-40",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[var(--radius-sm)]",
        "px-3.5 py-2 text-sm font-medium transition-colors duration-150",
        "disabled:cursor-not-allowed",
        VARIANT_CLASSES[variant],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";
