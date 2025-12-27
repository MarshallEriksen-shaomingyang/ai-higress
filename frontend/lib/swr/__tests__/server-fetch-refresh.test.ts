import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const cookiesFn = vi.fn();
vi.mock("next/headers", () => ({
  cookies: cookiesFn,
}));

import { serverFetch } from "../server-fetch";
import { REQUEST_TITLE_HEADER_NAME, REQUEST_TITLE_HEADER_VALUE } from "@/config/headers";

describe("serverFetch (SSR) refresh retry", () => {
  const originalApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
  });

  afterEach(() => {
    process.env.NEXT_PUBLIC_API_BASE_URL = originalApiBaseUrl;
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("refreshes and retries once on 401 when refresh_token cookie exists", async () => {
    cookiesFn.mockResolvedValue({
      get: (name: string) => {
        if (name === "access_token") return { value: "OLD" };
        if (name === "refresh_token") return { value: "RT" };
        return undefined;
      },
    });

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: "NEW" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "content-type": "application/json" },
        })
      );

    vi.stubGlobal("fetch", fetchMock);

    const result = await serverFetch<{ ok: boolean }>("/v1/anything");
    expect(result).toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledTimes(3);

    expect(String(fetchMock.mock.calls[0][0])).toBe("http://api.test/v1/anything");
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://api.test/auth/refresh");
    expect(String(fetchMock.mock.calls[2][0])).toBe("http://api.test/v1/anything");

    const firstInit = fetchMock.mock.calls[0][1] as RequestInit;
    expect(firstInit.headers).toMatchObject({
      [REQUEST_TITLE_HEADER_NAME]: REQUEST_TITLE_HEADER_VALUE,
    });

    const refreshInit = fetchMock.mock.calls[1][1] as RequestInit;
    expect(refreshInit.method).toBe("POST");
    expect(refreshInit.headers).toMatchObject({
      [REQUEST_TITLE_HEADER_NAME]: REQUEST_TITLE_HEADER_VALUE,
      Cookie: "refresh_token=RT",
    });

    const retryInit = fetchMock.mock.calls[2][1] as RequestInit;
    expect(retryInit.headers).toMatchObject({
      Authorization: "Bearer NEW",
      [REQUEST_TITLE_HEADER_NAME]: REQUEST_TITLE_HEADER_VALUE,
    });
  });

  it("does not attempt refresh when refresh_token cookie is missing", async () => {
    cookiesFn.mockResolvedValue({
      get: (name: string) => {
        if (name === "access_token") return { value: "OLD" };
        return undefined;
      },
    });

    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(null, { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await serverFetch("/v1/anything");
    expect(result).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
