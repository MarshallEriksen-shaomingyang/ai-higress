"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useSWRConfig } from "swr";

import { SlateChatInput } from "@/components/chat/slate-chat-input";
import { useChatStore } from "@/lib/stores/chat-store";
import { useCreateConversation, useDeleteConversation } from "@/lib/swr/use-conversations";
import { useSendMessage } from "@/lib/swr/use-messages";

export function ConversationChatInput({
  conversationId,
  assistantId,
  overrideLogicalModel,
  disabled = false,
  className,
  onMcpAction,
}: {
  conversationId: string;
  assistantId: string;
  overrideLogicalModel?: string | null;
  disabled?: boolean;
  className?: string;
  onMcpAction?: () => void;
}) {
  const router = useRouter();
  const { mutate: globalMutate } = useSWRConfig();

  const selectedProjectId = useChatStore((s) => s.selectedProjectId);
  const setSelectedConversation = useChatStore((s) => s.setSelectedConversation);

  const setConversationModelOverride = useChatStore((s) => s.setConversationModelOverride);
  const setConversationBridgeAgentId = useChatStore((s) => s.setConversationBridgeAgentId);
  const setConversationBridgeActiveReqId = useChatStore((s) => s.setConversationBridgeActiveReqId);

  const bridgeAgentId = useChatStore((s) => s.conversationBridgeAgentIds[conversationId] ?? null);

  const sendMessage = useSendMessage(conversationId, assistantId, overrideLogicalModel);
  const deleteConversation = useDeleteConversation();
  const createConversation = useCreateConversation();

  const handleSend = useCallback(
    async (payload: { content: string; model_preset?: Record<string, number> }) => {
      await sendMessage({
        content: payload.content,
        model_preset: payload.model_preset,
        bridge_agent_id: bridgeAgentId || undefined,
      });
    },
    [sendMessage, bridgeAgentId]
  );

  const handleClearHistory = useCallback(async () => {
    if (!selectedProjectId) {
      throw new Error("Project not selected");
    }

    await deleteConversation(conversationId);

    setConversationModelOverride(conversationId, null);
    setConversationBridgeAgentId(conversationId, null);
    setConversationBridgeActiveReqId(conversationId, null);

    const newConversation = await createConversation({
      assistant_id: assistantId,
      project_id: selectedProjectId,
    });

    const messagesKey = `/v1/conversations/${conversationId}/messages?limit=50`;
    const listKey = `/v1/conversations?assistant_id=${assistantId}&limit=50`;

    await globalMutate(messagesKey, undefined, { revalidate: false });
    await globalMutate(listKey);

    setSelectedConversation(newConversation.conversation_id);
    router.push(`/chat/${assistantId}/${newConversation.conversation_id}`);
  }, [
    selectedProjectId,
    deleteConversation,
    conversationId,
    setConversationModelOverride,
    setConversationBridgeAgentId,
    setConversationBridgeActiveReqId,
    createConversation,
    assistantId,
    globalMutate,
    setSelectedConversation,
    router,
  ]);

  return (
    <SlateChatInput
      conversationId={conversationId}
      assistantId={assistantId}
      disabled={disabled}
      className={className}
      onSend={async ({ content, model_preset }) => handleSend({ content, model_preset })}
      onClearHistory={handleClearHistory}
      onMcpAction={onMcpAction}
    />
  );
}
