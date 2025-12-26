"use client";

import { memo, useCallback, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { toast } from "sonner";

import { SlateChatInput, type ImageGenParams } from "@/components/chat/slate-chat-input";
import { buildBridgeRequestFields } from "@/lib/chat/build-bridge-request";
import { useChatStore } from "@/lib/stores/chat-store";
import { useClearConversationMessages, useSendMessage } from "@/lib/swr/use-messages";
import { useImageGenerations } from "@/lib/swr/use-image-generations";
import { useImageGenStore } from "@/lib/stores/image-generation-store";
import type { ComposerMode } from "@/components/chat/chat-input/chat-toolbar";
import { useI18n } from "@/lib/i18n-context";

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
  const { t } = useI18n();
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

  // Image Generation State
  const [mode, setMode] = useState<ComposerMode>("chat");
  const [imageGenParams, setImageGenParams] = useState<ImageGenParams>({
    model: "",
    size: "1024x1024",
    n: 1,
  });

  const { generateImage } = useImageGenerations();
  const addImageGenTask = useImageGenStore((s) => s.addTask);
  const updateImageGenTask = useImageGenStore((s) => s.updateTask);

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

  const handleImageSend = useCallback(
    async (payload: { prompt: string; params: ImageGenParams }) => {
      const taskId = uuidv4();
      const createdAt = Date.now();

      addImageGenTask({
        id: taskId,
        conversationId,
        status: "pending",
        prompt: payload.prompt,
        params: {
          model: payload.params.model,
          prompt: payload.prompt,
          n: payload.params.n,
          size: payload.params.size,
        },
        createdAt,
      });

      try {
        const result = await generateImage({
          model: payload.params.model,
          prompt: payload.prompt,
          n: payload.params.n,
          size: payload.params.size,
        });
        updateImageGenTask(taskId, { status: "success", result });
        toast.success(t("chat.image_gen.success"));
      } catch (error: any) {
        console.error("Image generation failed", error);
        updateImageGenTask(taskId, {
          status: "failed",
          error: error?.message || t("chat.image_gen.failed"),
        });
        toast.error(t("chat.image_gen.failed"));
      }
    },
    [conversationId, addImageGenTask, updateImageGenTask, generateImage, t]
  );

  return (
    <SlateChatInput
      conversationId={conversationId}
      assistantId={assistantId}
      disabled={disabled}
      className={className}
      onSend={handleSlateSend}
      onClearHistory={handleClearHistory}
      mode={mode}
      onModeChange={setMode}
      imageGenParams={imageGenParams}
      onImageGenParamsChange={setImageGenParams}
      onImageSend={handleImageSend}
    />
  );
});
