"use client";

import { useEffect, useMemo, useState } from "react";
import { useThrottleFn } from "ahooks";
import { Search, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface SidebarSearchInputProps {
  value: string;
  onValueChange: (value: string) => void;
  placeholder: string;
  ariaLabel: string;
  clearAriaLabel: string;
  disabled?: boolean;
  className?: string;
}

export function SidebarSearchInput({
  value,
  onValueChange,
  placeholder,
  ariaLabel,
  clearAriaLabel,
  disabled = false,
  className,
}: SidebarSearchInputProps) {
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  const { run: throttledSet, cancel } = useThrottleFn(
    (next: string) => onValueChange(next),
    { wait: 200 }
  );

  useEffect(() => cancel, [cancel]);

  const hasValue = useMemo(() => draft.trim().length > 0, [draft]);

  return (
    <div className={cn("relative", className)}>
      <Search
        className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
        aria-hidden="true"
      />
      <Input
        value={draft}
        onChange={(e) => {
          const next = e.target.value;
          setDraft(next);
          throttledSet(next);
        }}
        placeholder={placeholder}
        aria-label={ariaLabel}
        disabled={disabled}
        className={cn("pl-9 pr-9", disabled ? "opacity-70" : undefined)}
      />

      {!disabled && hasValue ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
          onClick={() => {
            cancel();
            setDraft("");
            onValueChange("");
          }}
          aria-label={clearAriaLabel}
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </Button>
      ) : null}
    </div>
  );
}

