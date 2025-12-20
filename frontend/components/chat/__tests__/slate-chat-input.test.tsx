/**
 * SlateChatInput 组件测试
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SlateChatInput } from "../slate-chat-input";

// Mock i18n
vi.mock("@/lib/i18n-context", () => ({
  useI18n: () => ({
    t: (key: string) => key,
    language: "zh",
  }),
}));

describe("SlateChatInput", () => {
  it("应该正确渲染组件", () => {
    render(
      <SlateChatInput
        conversationId="test-conv-123"
        assistantId="test-asst-456"
      />
    );

    // 检查输入框是否存在
    const editor = screen.getByRole("textbox");
    expect(editor).toBeDefined();
  });

  it("应该显示发送按钮", () => {
    render(
      <SlateChatInput
        conversationId="test-conv-123"
      />
    );

    // 检查发送按钮
    const sendButton = screen.getByRole("button", { name: /send/i });
    expect(sendButton).toBeDefined();
  });

  it("禁用状态下应该禁用所有交互", () => {
    render(
      <SlateChatInput
        conversationId="test-conv-123"
        disabled={true}
      />
    );

    const editor = screen.getByRole("textbox");
    expect(editor).toHaveProperty("disabled", true);
  });
});
