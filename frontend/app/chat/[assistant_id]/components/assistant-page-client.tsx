"use client";

import { MessageSquarePlus } from "lucide-react";

import { useAssistant } from "@/lib/swr/use-assistants";
import { useI18n } from "@/lib/i18n-context";

export function AssistantPageClient({ assistantId }: { assistantId: string }) {
  const { t } = useI18n();
  const { assistant, isLoading } = useAssistant(assistantId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-2">
          <div className="text-muted-foreground">
            {t("chat.assistant.loading")}
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
            {t("chat.errors.assistant_not_found")}
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
            {t("chat.conversation.select_prompt")}
          </p>
        </div>

        <div className="text-sm text-muted-foreground space-y-1">
          <p>👈 {t("chat.conversation.empty_description")}</p>
        </div>
      </div>
    </div>
  );
}

