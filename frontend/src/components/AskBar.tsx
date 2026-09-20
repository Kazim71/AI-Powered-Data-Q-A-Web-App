"use client";

import { useState } from "react";
import { ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function AskBar({
  disabled,
  isAsking,
  onSubmit,
}: {
  disabled: boolean;
  isAsking: boolean;
  onSubmit: (question: string) => void;
}) {
  const [value, setValue] = useState("");

  const submit = () => {
    const question = value.trim();
    if (!question || disabled || isAsking) return;
    onSubmit(question);
    setValue("");
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="flex items-center gap-2 rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 shadow-[var(--shadow-lift)]"
    >
      <label htmlFor="ask-input" className="sr-only">
        Ask a question about your data
      </label>
      <input
        id="ask-input"
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={disabled}
        placeholder={
          disabled
            ? "Upload a file to start asking questions"
            : "Ask a question about your data…"
        }
        className="min-h-11 flex-1 bg-transparent text-base outline-none placeholder:text-text-muted disabled:cursor-not-allowed"
      />
      <Button
        type="submit"
        disabled={disabled || isAsking || value.trim().length === 0}
        aria-label="Ask"
        className="h-11 w-11 shrink-0 rounded-[var(--radius-sm)] p-0"
      >
        <ArrowUp className="h-4 w-4" aria-hidden />
      </Button>
    </form>
  );
}
