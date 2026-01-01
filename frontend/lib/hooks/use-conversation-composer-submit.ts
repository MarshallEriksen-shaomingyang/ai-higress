"use client";

import { useCallback, useMemo } from "react";
import { toast } from "sonner";

import { buildChatPayload } from "@/lib/chat/payload-builder";
import type { ComposerSubmitPayload, ChatComposerSubmitPayload, ImageComposerSubmitPayload } from "@/lib/chat/composer-submit";
import { useI18n } from "@/lib/i18n-context";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSendMessage } from "@/lib/swr/use-messages";
import { useSendConversationImageGeneration } from "@/lib/swr/use-conversation-image-generations";
import { useBridgeAgents } from "@/lib/swr/use-bridge";

export function useConversationComposerSubmit({
  conversationId,
  assistantId,
  overrideLogicalModel,
}: {
  conversationId: string;
  assistantId: string;
  overrideLogicalModel?: string | null;
}) {
  const { t } = useI18n();
  const projectId = useChatStore((s) => s.selectedProjectId);
  const bridgeToolSelections =
    useChatStore((s) => s.conversationBridgeToolSelections[conversationId]) ?? {};
  const defaultBridgeToolSelections =
    useChatStore((s) => s.defaultBridgeToolSelections) ?? {};
  const bridgeAgentIds =
    useChatStore((s) => s.conversationBridgeAgentIds[conversationId]) ?? [];
  const setConversationModelPreset = useChatStore((s) => s.setConversationModelPreset);
  const { agents: bridgeAgents } = useBridgeAgents();

  const availableBridgeAgentIds = useMemo(() => {
    const ids = new Set<string>();
    for (const agent of bridgeAgents || []) {
      const id = typeof agent.agent_id === "string" ? agent.agent_id.trim() : "";
      if (id) ids.add(id);
    }
    return ids;
  }, [bridgeAgents]);

  const sendMessage = useSendMessage(conversationId, assistantId, overrideLogicalModel);
  const sendImageGeneration = useSendConversationImageGeneration(conversationId);

  const sendChat = useCallback(
    async (payload: ChatComposerSubmitPayload) => {
      setConversationModelPreset(conversationId, payload.model_preset ?? null);
      const request = buildChatPayload({
        content: payload.content,
        inputAudio: payload.input_audio ?? null,
        modelPreset: payload.model_preset ?? null,
        overrideLogicalModel: overrideLogicalModel ?? null,
        bridgeState: {
          conversationBridgeAgentIds: bridgeAgentIds,
          conversationBridgeToolSelections: bridgeToolSelections,
          defaultBridgeToolSelections,
        },
        availableBridgeAgentIds,
      });

      await sendMessage(request);
    },
    [
      bridgeAgentIds,
      bridgeToolSelections,
      availableBridgeAgentIds,
      conversationId,
      defaultBridgeToolSelections,
      overrideLogicalModel,
      sendMessage,
      setConversationModelPreset,
    ]
  );

  const sendImage = useCallback(
    async (payload: ImageComposerSubmitPayload) => {
      const trimmedPrompt = payload.prompt.trim();
      if (!trimmedPrompt) return;
      if (!payload.params.model) {
        toast.error(t("chat.image_gen.select_model"));
        return;
      }

      try {
        await sendImageGeneration({
          model: payload.params.model,
          prompt: trimmedPrompt,
          n: payload.params.n,
          size: payload.params.size,
          quality: payload.params.quality,
          enableGoogleSearch: payload.params.enableGoogleSearch,
          sendResponseFormat: payload.params.sendResponseFormat,
        });
        toast.success(t("chat.image_gen.success"));
      } catch (error: any) {
        console.error("Image generation failed", error);
        toast.error(t("chat.image_gen.failed"));
      }
    },
    [conversationId, sendImageGeneration, t]
  );

  const senders = useMemo(
    () => ({
      chat: sendChat,
      image: sendImage,
    }),
    [sendChat, sendImage]
  );

  const submit = useCallback(
    async (payload: ComposerSubmitPayload) => {
      if (payload.mode === "chat") {
        return await senders.chat(payload);
      }
      if (payload.mode === "image") {
        return await senders.image(payload);
      }
    },
    [senders]
  );

  return {
    projectId,
    submit,
  };
}
