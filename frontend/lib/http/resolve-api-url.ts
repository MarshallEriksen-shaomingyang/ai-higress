export function resolveApiUrl(url: string, baseUrl: string): string {
  const trimmed = (url || "").trim();
  if (!trimmed) return trimmed;

  if (
    trimmed.startsWith("http://") ||
    trimmed.startsWith("https://") ||
    trimmed.startsWith("data:") ||
    trimmed.startsWith("blob:")
  ) {
    return trimmed;
  }

  const base = (baseUrl || "").trim().replace(/\/+$/, "");
  if (!base) return trimmed;

  if (trimmed.startsWith("/")) return `${base}${trimmed}`;
  return `${base}/${trimmed}`;
}

