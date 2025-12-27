import { describe, expect, it } from "vitest";

import { normalizeMessagesResponse } from "@/lib/normalizers/chat-normalizers";

describe("chat normalizers: messages shape", () => {
  it("normalizeMessagesResponse: 支持扁平化 message 字段", () => {
    const backend = {
      items: [
        {
          message_id: "msg-1",
          role: "user",
          content: { type: "text", text: "hi" },
          created_at: "2025-01-01T00:00:00Z",
          runs: [],
        },
      ],
      next_cursor: undefined,
    } as any;

    const normalized = normalizeMessagesResponse(backend, "conv-1");
    expect(normalized.items).toHaveLength(1);
    expect(normalized.items[0].message.message_id).toBe("msg-1");
    expect(normalized.items[0].message.conversation_id).toBe("conv-1");
    expect(normalized.items[0].message.content).toBe("hi");
  });

  it("normalizeMessagesResponse: 将 image_url 段落拼接为可渲染内容", () => {
    const backend = {
      items: [
        {
          message_id: "msg-2",
          role: "user",
          content: [
            { type: "text", text: "看看这张图" },
            { type: "image_url", image_url: { url: "data:image/png;base64,abc" } },
            { type: "text", text: "谢谢" },
          ],
          created_at: "2025-01-02T00:00:00Z",
          runs: [],
        },
      ],
      next_cursor: undefined,
    } as any;

    const normalized = normalizeMessagesResponse(backend, "conv-2");
    const content = normalized.items[0].message.content;
    expect(content).toContain("看看这张图");
    expect(content).toContain("data:image/png;base64,abc");
    expect(content).toContain("谢谢");
    expect(content.indexOf("看看这张图")).toBeLessThan(content.indexOf("谢谢"));
  });

  it("normalizeMessagesResponse: 支持仅包含 image_url 段的消息", () => {
    const backend = {
      items: [
        {
          message_id: "msg-3",
          role: "user",
          content: [{ type: "image_url", image_url: { url: "https://example.com/a.png" } }],
          created_at: "2025-01-03T00:00:00Z",
          runs: [],
        },
      ],
      next_cursor: undefined,
    } as any;

    const normalized = normalizeMessagesResponse(backend, "conv-3");
    expect(normalized.items[0].message.content.trim()).toBe("https://example.com/a.png");
  });

  it("normalizeMessagesResponse: 支持 image_generation 结构化消息", () => {
    const backend = {
      items: [
        {
          message_id: "msg-4",
          role: "assistant",
          content: {
            type: "image_generation",
            status: "succeeded",
            prompt: "a cat",
            params: {
              model: "gpt-image-1",
              prompt: "a cat",
              n: 1,
              size: "1024x1024",
              response_format: "url",
            },
            images: [{ url: "http://api.test/media/images/x?expires=1&sig=abc" }],
            created: 1700000000,
          },
          created_at: "2025-01-04T00:00:00Z",
          runs: [],
        },
      ],
      next_cursor: undefined,
    } as any;

    const normalized = normalizeMessagesResponse(backend, "conv-4");
    expect(normalized.items[0].message.image_generation?.type).toBe("image_generation");
    expect(normalized.items[0].message.image_generation?.status).toBe("succeeded");
    expect(normalized.items[0].message.image_generation?.images?.[0]?.url).toContain("/media/images/");
    expect(normalized.items[0].message.content).toContain("[图片]");
  });
});
