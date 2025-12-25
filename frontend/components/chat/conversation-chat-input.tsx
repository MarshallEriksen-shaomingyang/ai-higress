"use client";

import { memo, useCallback } from "react";

import { SlateChatInput } from "@/components/chat/slate-chat-input";
import { buildBridgeRequestFields } from "@/lib/chat/build-bridge-request";
import { useChatStore } from "@/lib/stores/chat-store";
import { useClearConversationMessages, useSendMessage } from "@/lib/swr/use-messages";

export const ConversationChatInput = memo(function ConversationChatInput({
  conversationId,
  assistantId,
  overrideLogicalModel,
  disabled = false,
  className,
}: {
  conversationId: string;
  assistantId: string;
  overrideLogicalModel?: string | null;
  disabled?: boolean;
  className?: string;
}) {
  const bridgeToolSelections =
    useChatStore((s) => s.conversationBridgeToolSelections[conversationId]) ?? {};
  const defaultBridgeToolSelections =
    useChatStore((s) => s.defaultBridgeToolSelections) ?? {};
  const bridgeAgentIds =
    useChatStore((s) => s.conversationBridgeAgentIds[conversationId]) ?? [];
  const chatStreamingEnabled = useChatStore((s) => s.chatStreamingEnabled);
  const setConversationModelPreset = useChatStore((s) => s.setConversationModelPreset);

  const sendMessage = useSendMessage(conversationId, assistantId, overrideLogicalModel);
  const clearConversationMessages = useClearConversationMessages(assistantId);

  const handleSend = useCallback(
    async (payload: { content: string; model_preset?: Record<string, number> }) => {
      setConversationModelPreset(conversationId, payload.model_preset ?? null);
      const bridgeFields = buildBridgeRequestFields({
        conversationBridgeAgentIds: bridgeAgentIds,
        conversationBridgeToolSelections: bridgeToolSelections,
        defaultBridgeToolSelections,
      });

      await sendMessage({
        content: payload.content,
        model_preset: payload.model_preset,
        ...bridgeFields,
      }, { streaming: chatStreamingEnabled });
    },
    [
      conversationId,
      sendMessage,
      bridgeAgentIds,
      bridgeToolSelections,
      defaultBridgeToolSelections,
      chatStreamingEnabled,
      setConversationModelPreset,
    ]
  );

  const handleClearHistory = useCallback(async () => {
    await clearConversationMessages(conversationId);
  }, [
    clearConversationMessages,
    conversationId,
  ]);

  const handleSlateSend = useCallback(
    async (payload: {
      content: string;
      images: string[];
      model_preset?: Record<string, number>;
      parameters: any;
    }) => handleSend({ content: payload.content, model_preset: payload.model_preset }),
    [handleSend]
  );

  return (
    <SlateChatInput
      conversationId={conversationId}
      assistantId={assistantId}
      disabled={disabled}
      className={className}
      onSend={handleSlateSend}
      onClearHistory={handleClearHistory}
    />
  );
});
