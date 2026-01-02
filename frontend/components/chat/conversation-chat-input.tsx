"use client";

import { memo, useCallback } from "react";

import { SlateChatInput, type ImageGenParams } from "@/components/chat/slate-chat-input";
import { useClearConversationMessages } from "@/lib/swr/use-messages";
import { cn } from "@/lib/utils";
import { useConversationComposer } from "@/lib/hooks/use-conversation-composer";
import { useConversationComposerSubmit } from "@/lib/hooks/use-conversation-composer-submit";

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
  const { mode, image, setMode, setImageParams } = useConversationComposer(conversationId);
  const { projectId, submit } = useConversationComposerSubmit({
    conversationId,
    assistantId,
    overrideLogicalModel,
  });
  const clearConversationMessages = useClearConversationMessages(assistantId);

  const handleClearHistory = useCallback(async () => {
    await clearConversationMessages(conversationId);
  }, [
    clearConversationMessages,
    conversationId,
  ]);

  const handleImageGenParamsChange = useCallback(
    (params: ImageGenParams) => setImageParams(params),
    [setImageParams]
  );

  return (
    <div className="h-full flex flex-col">
      <div className="min-h-0 flex-1">
        <SlateChatInput
          conversationId={conversationId}
          assistantId={assistantId}
          projectId={projectId}
          disabled={disabled}
          className={cn("h-full", className)}
          onSubmit={submit}
          onClearHistory={handleClearHistory}
          mode={mode}
          onModeChange={setMode}
          imageGenParams={image}
          onImageGenParamsChange={handleImageGenParamsChange}
          hideModeSwitcher={false}
          imageSettingsShowModelSelect={false}
        />
      </div>
    </div>
  );
});
