import { renderHook, act } from "@testing-library/react";
import { describe, expect, vi, beforeEach, afterEach } from "vitest";

import { useSendConversationImageGeneration } from "./use-conversation-image-generations";

vi.mock("@/lib/i18n-context", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const mockSetPending = vi.fn();
vi.mock("@/lib/hooks/use-conversation-pending", () => ({
  useConversationPending: () => ({ setPending: mockSetPending }),
}));

const mockMutate = vi.fn();
vi.mock("swr", () => ({
  useSWRConfig: () => ({ mutate: mockMutate }),
}));

const mockStreamSSERequest = vi.fn(async () => Promise.resolve());
vi.mock("@/lib/bridge/sse", () => ({
  streamSSERequest: (...args: unknown[]) => mockStreamSSERequest(...args),
}));

describe("useSendConversationImageGeneration payload", () => {
  beforeEach(() => {
    mockStreamSSERequest.mockClear();
    mockMutate.mockReset();
    mockMutate.mockResolvedValue(undefined);
    mockSetPending.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const basePayload = {
    prompt: "hello image",
    model: "nano-banana-pro",
    n: 1,
    size: "1024x1024",
    quality: "auto" as const,
  };

  it("sends response_format=url by default", async () => {
    const { result } = renderHook(() => useSendConversationImageGeneration("conv-1"));

    await act(async () => {
      await result.current(basePayload);
    });

    expect(mockStreamSSERequest).toHaveBeenCalledTimes(1);
    const [, options] = mockStreamSSERequest.mock.calls[0];
    const body = JSON.parse((options as any).body);
    if (process.env.VITEST_SHOW_PAYLOAD) {
      // eslint-disable-next-line no-console
      console.log("[payload:on]", JSON.stringify(body));
    }
    expect(body.response_format).toBe("url");
  });

  it("omits response_format when toggle is off", async () => {
    const { result } = renderHook(() => useSendConversationImageGeneration("conv-1"));

    await act(async () => {
      await result.current({ ...basePayload, sendResponseFormat: false });
    });

    const [, options] = mockStreamSSERequest.mock.calls[0];
    const body = JSON.parse((options as any).body);
    if (process.env.VITEST_SHOW_PAYLOAD) {
      // eslint-disable-next-line no-console
      console.log("[payload:off]", JSON.stringify(body));
    }
    expect(body.response_format).toBeNull();
  });

  it("sends google search payload when enabled", async () => {
    const { result } = renderHook(() => useSendConversationImageGeneration("conv-1"));

    await act(async () => {
      await result.current({ ...basePayload, enableGoogleSearch: true });
    });

    const [, options] = mockStreamSSERequest.mock.calls[0];
    const body = JSON.parse((options as any).body);
    if (process.env.VITEST_SHOW_PAYLOAD) {
      // eslint-disable-next-line no-console
      console.log("[payload:google]", JSON.stringify(body));
    }
    expect(body.extra_body?.google?.tools?.[0]).toEqual({ googleSearch: {} });
    expect(body.extra_body?.google?.responseModalities).toEqual(["TEXT", "IMAGE"]);
    expect(body.extra_body?.openai?.tools?.[0]).toEqual({ google_search: {} });
  });
});
