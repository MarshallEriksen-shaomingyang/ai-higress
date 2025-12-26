"use client";

import { useCallback, useMemo } from "react";
import { v4 as uuidv4 } from "uuid";
import { toast } from "sonner";

import { buildBridgeRequestFields } from "@/lib/chat/build-bridge-request";
import { composerModeCapabilities } from "@/lib/chat/composer-modes";
import type { ComposerSubmitPayload, ChatComposerSubmitPayload, ImageComposerSubmitPayload } from "@/lib/chat/composer-submit";
import { useI18n } from "@/lib/i18n-context";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSendMessage } from "@/lib/swr/use-messages";
import { useImageGenerations } from "@/lib/swr/use-image-generations";
import { useComposerTaskStore } from "@/lib/stores/composer-task-store";

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
  const chatStreamingEnabled = useChatStore((s) => s.chatStreamingEnabled);
  const setConversationModelPreset = useChatStore((s) => s.setConversationModelPreset);

  const sendMessage = useSendMessage(conversationId, assistantId, overrideLogicalModel);
  const { generateImage } = useImageGenerations();
  const addTask = useComposerTaskStore((s) => s.addTask);
  const updateTask = useComposerTaskStore((s) => s.updateTask);

  const sendChat = useCallback(
    async (payload: ChatComposerSubmitPayload) => {
      setConversationModelPreset(conversationId, payload.model_preset ?? null);
      const bridgeFields = buildBridgeRequestFields({
        conversationBridgeAgentIds: bridgeAgentIds,
        conversationBridgeToolSelections: bridgeToolSelections,
        defaultBridgeToolSelections,
      });

      await sendMessage(
        {
          content: payload.content,
          model_preset: payload.model_preset,
          ...bridgeFields,
        },
        {
          streaming:
            composerModeCapabilities.chat.supportsStreaming && chatStreamingEnabled,
        }
      );
    },
    [
      bridgeAgentIds,
      bridgeToolSelections,
      chatStreamingEnabled,
      conversationId,
      defaultBridgeToolSelections,
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

      const taskId = uuidv4();
      const createdAt = Date.now();

      addTask({
        id: taskId,
        conversationId,
        kind: "image_generation",
        status: "pending",
        prompt: trimmedPrompt,
        params: {
          model: payload.params.model,
          prompt: trimmedPrompt,
          n: payload.params.n,
          size: payload.params.size,
          response_format: "url",
        },
        createdAt,
      });

      try {
        const result = await generateImage({
          model: payload.params.model,
          prompt: trimmedPrompt,
          n: payload.params.n,
          size: payload.params.size,
          response_format: "url",
        });
        updateTask(taskId, { status: "success", result });
        toast.success(t("chat.image_gen.success"));
      } catch (error: any) {
        console.error("Image generation failed", error);
        updateTask(taskId, {
          status: "failed",
          error: error?.message || t("chat.image_gen.failed"),
        });
        toast.error(t("chat.image_gen.failed"));
      }
    },
    [addTask, conversationId, generateImage, t, updateTask]
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

