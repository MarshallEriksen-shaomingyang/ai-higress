"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type Suffix = {
  path: string;
  description: string;
};

type TypewriterSuffixesProps = {
  suffixes: Suffix[];
  typeSpeed?: number;
  holdDuration?: number;
  gapDuration?: number;
};

export function TypewriterSuffixes({
  suffixes,
  typeSpeed = 70,
  holdDuration = 1200,
  gapDuration = 300,
}: TypewriterSuffixesProps) {
  const signature = useMemo(
    () => suffixes.map((suffix) => `${suffix.path}::${suffix.description}`).join("|"),
    [suffixes],
  );
  const normalizedSuffixes = useMemo(() => suffixes, [signature]);

  const [currentIndex, setCurrentIndex] = useState(0);
  const [typed, setTyped] = useState("");
  const [phase, setPhase] = useState<"typing" | "hold">("typing");

  useEffect(() => {
    setCurrentIndex(0);
    setTyped("");
    setPhase("typing");
  }, [signature]);

  useEffect(() => {
    if (!normalizedSuffixes.length) return;
    const current = normalizedSuffixes[currentIndex % normalizedSuffixes.length];
    let timer: ReturnType<typeof setTimeout>;

    if (phase === "typing") {
      if (typed.length < current.path.length) {
        timer = setTimeout(() => {
          setTyped(current.path.slice(0, typed.length + 1));
        }, typeSpeed);
      } else {
        timer = setTimeout(() => setPhase("hold"), holdDuration);
      }
    } else {
      timer = setTimeout(() => {
        const nextIndex = (currentIndex + 1) % normalizedSuffixes.length;
        setCurrentIndex(nextIndex);
        setTyped("");
        setPhase("typing");
      }, gapDuration);
    }

    return () => clearTimeout(timer);
  }, [normalizedSuffixes, currentIndex, typed, phase, typeSpeed, holdDuration, gapDuration]);

  if (!normalizedSuffixes.length) {
    return null;
  }

  const current = normalizedSuffixes[currentIndex % normalizedSuffixes.length];

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge
          variant="outline"
          className="px-3 py-2 font-mono text-xs md:text-sm min-w-[11rem] justify-center"
        >
          <span aria-live="polite">{typed || "\u00a0"}</span>
          <span
            className="ml-1 inline-block w-0.5 h-4 bg-muted-foreground animate-pulse"
            aria-hidden="true"
          />
        </Badge>
      </TooltipTrigger>
      <TooltipContent>
        <p className="max-w-xs text-xs">{current.description}</p>
      </TooltipContent>
    </Tooltip>
  );
}
