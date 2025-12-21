"use client";

import { useEffect } from "react";

type BodyScrollLockProps = {
  enabled?: boolean;
};

export function BodyScrollLock({ enabled = true }: BodyScrollLockProps) {
  useEffect(() => {
    if (!enabled) return;

    const html = document.documentElement;
    const body = document.body;

    const htmlOverflow = html.style.overflow;
    const bodyOverflow = body.style.overflow;

    html.style.overflow = "hidden";
    body.style.overflow = "hidden";

    return () => {
      html.style.overflow = htmlOverflow;
      body.style.overflow = bodyOverflow;
    };
  }, [enabled]);

  return null;
}

