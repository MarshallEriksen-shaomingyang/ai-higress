"use client";

import { memo, useCallback } from "react";

import { SlateChatInput } from "@/components/chat/slate-chat-input";
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
  const chatStreamingEnabled = useChatStore((s) => s.chatStreamingEnabled);

  const sendMessage = useSendMessage(conversationId, assistantId, overrideLogicalModel);
  const clearConversationMessages = useClearConversationMessages(assistantId);

  const handleSend = useCallback(
    async (payload: { content: string; model_preset?: Record<string, number> }) => {
      const effectiveSelections: Record<string, string[]> = { ...defaultBridgeToolSelections };
      Object.entries(bridgeToolSelections).forEach(([aid, tools]) => {
        if (Array.isArray(tools) && tools.length) {
          effectiveSelections[aid] = tools;
        }
      });
      const effectiveAgentIds = Object.entries(effectiveSelections)
        .filter(([, tools]) => Array.isArray(tools) && tools.length)
        .map(([aid]) => aid);

      await sendMessage({
        content: payload.content,
        model_preset: payload.model_preset,
        bridge_agent_ids: effectiveAgentIds.length ? effectiveAgentIds : undefined,
        bridge_tool_selections: effectiveAgentIds.length
          ? effectiveAgentIds.map((agentId) => ({
              agent_id: agentId,
              tool_names: effectiveSelections[agentId] ?? [],
            }))
          : undefined,
      }, { streaming: chatStreamingEnabled });
    },
    [sendMessage, bridgeToolSelections, defaultBridgeToolSelections, chatStreamingEnabled]
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
