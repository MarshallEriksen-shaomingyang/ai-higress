"use client";

import { useMemo } from "react";
import { Maximize2, Minimize2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import { useI18n } from "@/lib/i18n-context";
import { useChatLayoutStore } from "@/lib/stores/chat-layout-store";
import { useChatStore } from "@/lib/stores/chat-store";
import { useAssistant } from "@/lib/swr/use-assistants";
import { useLogicalModels } from "@/lib/swr/use-logical-models";
import { useProjectChatSettings } from "@/lib/swr/use-project-chat-settings";

const INHERIT_VALUE = "__inherit__";
const PROJECT_INHERIT_SENTINEL = "__project__";

export function ConversationHeader({
  assistantId,
  conversationId,
  title,
}: {
  assistantId: string;
  conversationId: string;
  title: string | null | undefined;
}) {
  const { t } = useI18n();
  const { assistant } = useAssistant(assistantId);
  const { models } = useLogicalModels();

  const isImmersive = useChatLayoutStore((s) => s.isImmersive);
  const setIsImmersive = useChatLayoutStore((s) => s.setIsImmersive);

  const {
    conversationModelOverrides,
    setConversationModelOverride,
    selectedProjectId,
  } = useChatStore();

  const { settings: projectSettings } = useProjectChatSettings(selectedProjectId);

  const currentOverride = conversationModelOverrides[conversationId] ?? null;
  const selectedValue = currentOverride ?? INHERIT_VALUE;

  const effectiveAssistantDefaultModel =
    assistant?.default_logical_model === PROJECT_INHERIT_SENTINEL
      ? projectSettings?.default_logical_model || "auto"
      : assistant?.default_logical_model || "auto";

  const availableModels = useMemo(() => {
    const modelSet = new Set<string>();
    modelSet.add("auto");

    for (const model of models) {
      if (!model.enabled) continue;
      if (!model.capabilities?.includes("chat")) continue;
      modelSet.add(model.logical_id);
    }

    // Ensure current override is selectable even if filtered out
    if (currentOverride) modelSet.add(currentOverride);
    if (effectiveAssistantDefaultModel) modelSet.add(effectiveAssistantDefaultModel);

    return ["auto", ...Array.from(modelSet).filter((m) => m !== "auto").sort()];
  }, [models, currentOverride, effectiveAssistantDefaultModel]);

  const displayTitle = (title || "").trim() || t("chat.conversation.untitled");

  return (
    <div className="flex items-center justify-between gap-3 border-b bg-background px-4 py-2">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{displayTitle}</div>
        <div className="truncate text-xs text-muted-foreground">
          {t("chat.header.model_label")}:{" "}
          {currentOverride || effectiveAssistantDefaultModel}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsImmersive(!isImmersive)}
              className="h-9 w-9"
            >
              {isImmersive ? (
                <Minimize2 className="h-4 w-4" />
              ) : (
                <Maximize2 className="h-4 w-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            {isImmersive
              ? t("chat.action.exit_immersive")
              : t("chat.action.enter_immersive")}
          </TooltipContent>
        </Tooltip>
        <div className="w-[220px]">
          <Select
            value={selectedValue}
            onValueChange={(value) => {
              if (value === INHERIT_VALUE) {
                setConversationModelOverride(conversationId, null);
              } else {
                setConversationModelOverride(conversationId, value);
              }
            }}
          >
            <SelectTrigger className="h-9">
              <SelectValue placeholder={t("chat.header.model_placeholder")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={INHERIT_VALUE}>
                {t("chat.header.model_inherit")}
                {effectiveAssistantDefaultModel
                  ? ` (${effectiveAssistantDefaultModel})`
                  : ""}
              </SelectItem>
              {availableModels.map((model) => (
                <SelectItem key={model} value={model}>
                  {model}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
