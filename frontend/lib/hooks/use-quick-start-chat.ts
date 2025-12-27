import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";

import { useChatLayoutStore } from "@/lib/stores/chat-layout-store";
import { useChatStore } from "@/lib/stores/chat-store";
import { useCreateConversation } from "@/lib/swr/use-conversations";
import { useSendMessageToConversation } from "@/lib/swr/use-messages";
import type { ModelParameters } from "@/components/chat/slate-chat-input";

export interface UseQuickStartChatOptions {
  assistantId: string | null;
  onSuccess?: (conversationId: string) => void;
}

export function useQuickStartChat({ assistantId, onSuccess }: UseQuickStartChatOptions) {
  const router = useRouter();
  const { selectedProjectId, setSelectedAssistant, setSelectedConversation } = useChatStore();
  const setActiveTab = useChatLayoutStore((s) => s.setActiveTab);

  const createConversation = useCreateConversation();
  const sendMessage = useSendMessageToConversation(assistantId);

  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSend = useCallback(
    async (payload: {
      content: string;
      images: string[];
      model_preset?: Record<string, number>;
      parameters: ModelParameters;
    }) => {
      if (isSubmitting || !selectedProjectId || !assistantId) {
        return;
      }

      const trimmed = payload.content.trim();
      if (!trimmed && payload.images.length === 0) return;

      setIsSubmitting(true);
      try {
        const conversation = await createConversation({
          project_id: selectedProjectId,
          assistant_id: assistantId,
        });

        await sendMessage(conversation.conversation_id, {
          content: trimmed,
        });

        setSelectedAssistant(assistantId);
        setSelectedConversation(conversation.conversation_id);
        setActiveTab("conversations");

        if (onSuccess) {
          onSuccess(conversation.conversation_id);
        } else {
          router.push(`/chat/${assistantId}/${conversation.conversation_id}`);
        }
      } catch (error) {
        console.error("Quick start chat failed:", error);
      } finally {
        setIsSubmitting(false);
      }
    },
    [
      isSubmitting,
      selectedProjectId,
      assistantId,
      createConversation,
      sendMessage,
      setSelectedAssistant,
      setSelectedConversation,
      setActiveTab,
      onSuccess,
      router,
    ]
  );

  return {
    handleSend,
    isSubmitting,
    canSubmit: !!selectedProjectId && !!assistantId,
  };
}
