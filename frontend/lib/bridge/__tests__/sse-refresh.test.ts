import { describe, it, expect, vi, afterEach } from "vitest";

const refreshAccessTokenMock = vi.fn<[], Promise<string>>().mockResolvedValue("NEW");

vi.mock("@/http/client", () => ({
  API_BASE_URL: "http://api.test",
  refreshAccessToken: refreshAccessTokenMock,
}));

const tokenManagerMock = {
  getAccessToken: vi.fn(() => "OLD"),
  getRefreshToken: vi.fn(() => "true"),
};

vi.mock("@/lib/auth/token-manager", () => ({
  tokenManager: tokenManagerMock,
}));

import { streamSSERequest } from "@/lib/bridge/sse";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("streamSSERequest", () => {
  it("refreshes and retries once on 401", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"x":1}\n\n'));
        controller.close();
      },
    });

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(body, { status: 200 }));

    vi.stubGlobal("fetch", fetchMock);

    const messages: Array<{ event: string; data: string }> = [];
    const controller = new AbortController();

    await streamSSERequest(
      "/v1/sse",
      { method: "GET" },
      (msg) => messages.push(msg),
      controller.signal
    );

    expect(messages).toEqual([{ event: "message", data: '{"x":1}' }]);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0][0])).toBe("http://api.test/v1/sse");
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://api.test/v1/sse");

    const firstInit = fetchMock.mock.calls[0][1] as RequestInit;
    expect(firstInit.headers).toMatchObject({ Authorization: "Bearer OLD" });

    const retryInit = fetchMock.mock.calls[1][1] as RequestInit;
    expect(retryInit.headers).toMatchObject({ Authorization: "Bearer NEW" });

    expect(refreshAccessTokenMock).toHaveBeenCalledTimes(1);
  });
});

