"use client";

import { memo, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { toast } from "sonner";

import { SlateChatInput, type ImageGenParams } from "@/components/chat/slate-chat-input";
import { buildBridgeRequestFields } from "@/lib/chat/build-bridge-request";
import { useChatStore } from "@/lib/stores/chat-store";
import { useClearConversationMessages, useSendMessage } from "@/lib/swr/use-messages";
import { useImageGenerations } from "@/lib/swr/use-image-generations";
import { useImageGenStore } from "@/lib/stores/image-generation-store";
import { useI18n } from "@/lib/i18n-context";
import { ChatModeButtons } from "@/components/chat/chat-mode-buttons";
import { cn } from "@/lib/utils";
import { useConversationComposer } from "@/lib/hooks/use-conversation-composer";

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
  const projectId = useChatStore((s) => s.selectedProjectId);
  const { mode, image, setMode, setImageParams } = useConversationComposer(conversationId);
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

  const handleImageGenParamsChange = useCallback(
    (params: ImageGenParams) => setImageParams(params),
    [setImageParams]
  );

  const handleImageSend = useCallback(
    async (payload: { prompt: string; params: ImageGenParams }) => {
      const trimmedPrompt = payload.prompt.trim();
      if (!trimmedPrompt) return;
      if (!payload.params.model) {
        toast.error(t("chat.image_gen.select_model"));
        return;
      }

      const taskId = uuidv4();
      const createdAt = Date.now();

      addImageGenTask({
        id: taskId,
        conversationId,
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
    <div className="h-full flex flex-col">
      <div className="px-4 pt-3">
        <ChatModeButtons
          mode={mode}
          onModeChange={setMode}
          disabled={disabled}
          className="mb-2"
        />
      </div>
      <div className="min-h-0 flex-1">
        <SlateChatInput
          conversationId={conversationId}
          assistantId={assistantId}
          projectId={projectId}
          disabled={disabled}
          className={cn("h-full", className)}
          onSend={handleSlateSend}
          onClearHistory={handleClearHistory}
          mode={mode}
          onModeChange={setMode}
          imageGenParams={image}
          onImageGenParamsChange={handleImageGenParamsChange}
          onImageSend={handleImageSend}
          hideModeSwitcher={true}
          imageSettingsShowModelSelect={false}
        />
      </div>
    </div>
  );
});
