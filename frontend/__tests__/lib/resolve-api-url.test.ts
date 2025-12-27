import { describe, it, expect } from "vitest";

import { resolveApiUrl } from "@/lib/http/resolve-api-url";

describe("lib: resolve-api-url", () => {
  it("keeps absolute urls untouched", () => {
    expect(resolveApiUrl("https://example.com/a", "http://api.test")).toBe(
      "https://example.com/a"
    );
    expect(resolveApiUrl("http://example.com/a", "http://api.test")).toBe(
      "http://example.com/a"
    );
    expect(resolveApiUrl("data:image/png;base64,abc", "http://api.test")).toBe(
      "data:image/png;base64,abc"
    );
    expect(resolveApiUrl("blob:https://example.com/id", "http://api.test")).toBe(
      "blob:https://example.com/id"
    );
  });

  it("prefixes relative urls with api base", () => {
    expect(resolveApiUrl("/v1/sse", "http://api.test")).toBe("http://api.test/v1/sse");
    expect(resolveApiUrl("v1/sse", "http://api.test")).toBe("http://api.test/v1/sse");
    expect(resolveApiUrl("/media/images/x?sig=1", "http://api.test/")).toBe(
      "http://api.test/media/images/x?sig=1"
    );
  });

  it("returns original if api base missing", () => {
    expect(resolveApiUrl("/v1/sse", "")).toBe("/v1/sse");
  });
});

