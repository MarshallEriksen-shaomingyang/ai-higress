"use client";

import { MessageSquarePlus } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { useParams } from "next/navigation";
import { useAssistant } from "@/lib/swr/use-assistants";

/**
 * 助手会话列表页
 * 
 * 显示选中助手的会话列表提示
 */
export default function AssistantPage() {
  const { t } = useI18n();
  const params = useParams();
  const assistantId = params.assistant_id as string;

  const { assistant, isLoading } = useAssistant(assistantId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-2">
          <div className="text-muted-foreground">
            {t('chat.assistant.loading')}
          </div>
        </div>
      </div>
    );
  }

  if (!assistant) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-2">
          <div className="text-muted-foreground">
            {t('chat.errors.assistant_not_found')}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center space-y-4 max-w-md px-4">
        <div className="flex justify-center">
          <div className="rounded-full bg-muted p-6">
            <MessageSquarePlus className="h-12 w-12 text-muted-foreground" />
          </div>
        </div>
        
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold tracking-tight">
            {assistant.name}
          </h2>
          <p className="text-muted-foreground">
            {t('chat.conversation.select_prompt')}
          </p>
        </div>

        <div className="text-sm text-muted-foreground space-y-1">
          <p>👈 {t('chat.conversation.empty_description')}</p>
        </div>
      </div>
    </div>
  );
}
