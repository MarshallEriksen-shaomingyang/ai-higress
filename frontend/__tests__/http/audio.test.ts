import { describe, it, expect, vi, beforeEach } from "vitest";

const post = vi.fn();

vi.mock("@/http/client", () => ({
  httpClient: {
    post: (...args: any[]) => post(...args),
  },
}));

import { audioService } from "@/http/audio";

describe("http: audioService.transcribeConversationAudio", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("应以 multipart 调用会话内 audio-transcriptions 并携带可选字段", async () => {
    post.mockResolvedValueOnce({ data: { text: "ok" } });

    const file = new File([new Blob(["a"], { type: "audio/wav" })], "a.wav", { type: "audio/wav" });
    const res = await audioService.transcribeConversationAudio("conv-1", file, {
      model: "stt-1",
      language: "zh-CN",
      prompt: "p",
    });

    expect(res).toEqual({ text: "ok" });
    expect(post).toHaveBeenCalledTimes(1);

    const [url, body, config] = post.mock.calls[0];
    expect(url).toBe("/v1/conversations/conv-1/audio-transcriptions");
    expect(body).toBeInstanceOf(FormData);
    expect(config?.headers?.["Content-Type"]).toBe("multipart/form-data");

    const entries = Array.from((body as FormData).entries());
    expect(entries).toEqual(
      expect.arrayContaining([
        ["model", "stt-1"],
        ["language", "zh-CN"],
        ["prompt", "p"],
      ])
    );
    const fileEntry = entries.find(([k]) => k === "file");
    expect(fileEntry).toBeTruthy();
    expect((fileEntry as any)[1]).toBeInstanceOf(File);
  });

  it("可选字段为空时不应写入 FormData", async () => {
    post.mockResolvedValueOnce({ data: { text: "ok" } });

    const file = new File([new Blob(["a"], { type: "audio/wav" })], "a.wav", { type: "audio/wav" });
    await audioService.transcribeConversationAudio("conv-1", file, {
      model: " ",
      language: "",
      prompt: null,
    });

    const [, body] = post.mock.calls[0];
    const keys = Array.from((body as FormData).keys());
    expect(keys).toContain("file");
    expect(keys).not.toContain("model");
    expect(keys).not.toContain("language");
    expect(keys).not.toContain("prompt");
  });
});

