"use client";

import { ErrorContent } from "@/components/error/error-content";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body>
        <ErrorContent error={error} reset={reset} />
      </body>
    </html>
  );
}