/**
 * SlateChatInput 组件测试
 */

import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SlateChatInput } from "../slate-chat-input";
import { useUserPreferencesStore } from "@/lib/stores/user-preferences-store";
import { useChatModelParametersStore } from "@/lib/stores/chat-model-parameters-store";

// Mock i18n
vi.mock("@/lib/i18n-context", () => ({
  useI18n: () => ({
    t: (key: string) => key,
    language: "zh",
  }),
}));

describe("SlateChatInput", () => {
  beforeEach(() => {
    localStorage.clear();
    useUserPreferencesStore.setState({
      preferences: {
        sendShortcut: "ctrl-enter",
        preferredChatModelByProject: {},
        preferredImageModelByProject: {},
        preferredTtsModelByProject: {},
        preferredTtsVoiceByProject: {},
        preferredTtsFormatByProject: {},
        preferredTtsSpeedByProject: {},
        speechModeEnabledByProject: {},
        selectedVoiceAudioByProject: {},
      },
    });
    useChatModelParametersStore.getState().reset();
  });

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
    const sendButton = screen.getByRole("button", { name: "chat.message.send" });
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
    expect(editor).toHaveAttribute("aria-disabled", "true");
  });

  it("点击清空历史应弹出确认框并触发回调", async () => {
    const onClearHistory = vi.fn().mockResolvedValue(undefined);

    render(
      <SlateChatInput
        conversationId="test-conv-123"
        onClearHistory={onClearHistory}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: "chat.message.clear_history" })
    );

    expect(
      screen.getByText("chat.message.clear_history_confirm")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "chat.action.confirm" }));

    await waitFor(() => expect(onClearHistory).toHaveBeenCalledTimes(1));
  });

  it("在 Enter 模式下按 Enter 应发送消息", async () => {
    useUserPreferencesStore.setState({
      preferences: {
        sendShortcut: "enter",
        preferredChatModelByProject: {},
        preferredImageModelByProject: {},
        preferredTtsModelByProject: {},
        preferredTtsVoiceByProject: {},
        preferredTtsFormatByProject: {},
        preferredTtsSpeedByProject: {},
        speechModeEnabledByProject: {},
        selectedVoiceAudioByProject: {},
      },
    });
    const onSend = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <SlateChatInput
        conversationId="test-conv-123"
        onSend={onSend}
      />
    );

    const editor = screen.getByRole("textbox");
    await user.click(editor);
    await user.type(editor, "hello");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));
  });

  it("在 Ctrl+Enter 模式下 Enter 不发送而 Ctrl+Enter 发送", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <SlateChatInput
        conversationId="test-conv-123"
        onSend={onSend}
      />
    );

    const editor = screen.getByRole("textbox");
    await user.click(editor);
    await user.type(editor, "hello");

    await user.keyboard("{Enter}");
    expect(onSend).not.toHaveBeenCalled();

    await user.keyboard("{Control>}{Enter}{/Control}");
    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));
  });
});
