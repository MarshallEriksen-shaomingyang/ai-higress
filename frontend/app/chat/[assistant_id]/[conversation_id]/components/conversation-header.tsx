"use client";

import { useEffect, useMemo, useState } from "react";
import { Maximize2, Minimize2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";

import { useI18n } from "@/lib/i18n-context";
import { useChatLayoutStore } from "@/lib/stores/chat-layout-store";
import { useChatStore } from "@/lib/stores/chat-store";
import { useConversationComposer } from "@/lib/hooks/use-conversation-composer";
import { useAssistant } from "@/lib/swr/use-assistants";
import { useLogicalModels } from "@/lib/swr/use-logical-models";
import { useProjectChatSettings } from "@/lib/swr/use-project-chat-settings";
import { useSelectableChatModels } from "@/lib/swr/use-selectable-chat-models";

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
  const isImmersive = useChatLayoutStore((s) => s.isImmersive);
  const setIsImmersive = useChatLayoutStore((s) => s.setIsImmersive);
  const { mode, image, setImageParams } = useConversationComposer(conversationId);

  const {
    conversationModelOverrides,
    setConversationModelOverride,
    selectedProjectId,
    evalStreamingEnabled,
    setEvalStreamingEnabled,
    chatStreamingEnabled,
    setChatStreamingEnabled,
  } = useChatStore();

  const { assistant } = useAssistant(assistantId);
  const { settings: projectSettings } = useProjectChatSettings(selectedProjectId);
  const { models: logicalModels } = useLogicalModels(selectedProjectId);

  const currentOverride = conversationModelOverrides[conversationId] ?? null;

  const effectiveAssistantDefaultModel =
    assistant?.default_logical_model === PROJECT_INHERIT_SENTINEL
      ? projectSettings?.default_logical_model || "auto"
      : assistant?.default_logical_model || "auto";

  const effectiveSelectedModel = currentOverride ?? effectiveAssistantDefaultModel;

  const { filterOptions } = useSelectableChatModels(
    selectedProjectId,
    {
      extraModels: [currentOverride, effectiveAssistantDefaultModel],
    }
  );
  const [modelSearch, setModelSearch] = useState("");

  const filteredModels = useMemo(() => {
    const models = filterOptions(modelSearch);
    if (models.some((model) => model.value === effectiveSelectedModel)) return models;
    return [{ value: effectiveSelectedModel, label: effectiveSelectedModel }, ...models];
  }, [effectiveSelectedModel, filterOptions, modelSearch]);

  const imageModels = useMemo(() => {
    return logicalModels
      .filter((m) => m.enabled)
      .map((m) => ({
        value: m.logical_id,
        label: m.display_name || m.logical_id,
      }));
  }, [logicalModels]);

  const filteredImageModels = useMemo(() => {
    const needle = modelSearch.trim().toLowerCase();
    const options = needle
      ? imageModels.filter((m) => m.label.toLowerCase().includes(needle))
      : imageModels;
    if (!image.model) return options;
    if (options.some((m) => m.value === image.model)) return options;
    return [{ value: image.model, label: image.model }, ...options];
  }, [image.model, imageModels, modelSearch]);

  useEffect(() => {
    if (mode !== "image") return;
    if (!imageModels.length) return;
    const selected = image.model;
    const valid = selected && imageModels.some((m) => m.value === selected);
    if (valid) return;
    const first = imageModels[0];
    if (!first) return;
    setImageParams({ model: first.value });
  }, [image.model, imageModels, mode, setImageParams]);

  useEffect(() => {
    setModelSearch("");
  }, [mode]);

  const conversationPending =
    useChatStore((s) => s.conversationPending[conversationId]) ?? false;
  const hasTitle = !!(title && title.trim());
  const isTitlePending = !hasTitle && conversationPending;
  const displayTitle = hasTitle ? title!.trim() : t("chat.conversation.untitled");

  return (
    <div className="flex items-center justify-between gap-2 md:gap-3 border-b border-border/20 bg-background px-3 md:px-4 py-2 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium flex items-center gap-2">
          {isTitlePending ? (
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-32" />
              <span className="text-[11px] text-muted-foreground animate-pulse">
                {t("chat.message.loading")}
              </span>
            </div>
          ) : (
            displayTitle
          )}
        </div>
      </div>

      <div className="flex items-center gap-1 md:gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex items-center gap-2 rounded-full border border-border/30 bg-muted/20 px-2.5 py-1 transition-colors hover:bg-muted/35">
              <span className="text-xs text-muted-foreground hidden md:inline">
                {t("chat.message.streaming_label")}
              </span>
              <Switch
                checked={chatStreamingEnabled}
                onCheckedChange={setChatStreamingEnabled}
                aria-label={t("chat.message.streaming_label")}
              />
            </div>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            {t("chat.message.streaming_tooltip")}
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex items-center gap-2 rounded-full border border-border/30 bg-muted/20 px-2.5 py-1 transition-colors hover:bg-muted/35">
              <span className="text-xs text-muted-foreground hidden md:inline">
                {t("chat.eval.streaming_label")}
              </span>
              <Switch
                checked={evalStreamingEnabled}
                onCheckedChange={setEvalStreamingEnabled}
                aria-label={t("chat.eval.streaming_label")}
              />
            </div>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            {t("chat.eval.streaming_tooltip")}
          </TooltipContent>
        </Tooltip>

        {/* 沉浸模式按钮 */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsImmersive(!isImmersive)}
              className="h-8 w-8 md:h-9 md:w-9"
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

        {/* 模型选择器 - 移动端缩小 */}
        <div className="w-[140px] md:w-[220px]">
          {mode === "image" ? (
            <Select
              value={image.model}
              onValueChange={(value) => setImageParams({ model: value })}
              onOpenChange={(open) => {
                if (!open) setModelSearch("");
              }}
              disabled={!imageModels.length}
            >
              <SelectTrigger className="h-8 rounded-full border-border/40 bg-muted/20 px-3 text-xs font-medium shadow-sm transition-colors hover:bg-muted/35 focus:ring-1 focus:ring-ring/30 focus:ring-offset-0 md:h-9 md:text-sm">
                <SelectValue placeholder={t("chat.image_gen.select_model")} />
              </SelectTrigger>
              <SelectContent>
                <div className="p-2 pb-1">
                  <Input
                    value={modelSearch}
                    onChange={(event) => setModelSearch(event.target.value)}
                    placeholder={t("chat.model.search_placeholder")}
                    className="h-9"
                  />
                </div>
                {filteredImageModels.map((model) => (
                  <SelectItem key={model.value} value={model.value} textValue={model.label}>
                    {model.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Select
              value={effectiveSelectedModel}
              onValueChange={(value) => {
                setConversationModelOverride(
                  conversationId,
                  value === effectiveAssistantDefaultModel ? null : value
                );
              }}
              onOpenChange={(open) => {
                if (!open) setModelSearch("");
              }}
            >
              <SelectTrigger className="h-8 rounded-full border-border/40 bg-muted/20 px-3 text-xs font-medium shadow-sm transition-colors hover:bg-muted/35 focus:ring-1 focus:ring-ring/30 focus:ring-offset-0 md:h-9 md:text-sm">
                <SelectValue placeholder={t("chat.header.model_placeholder")} />
              </SelectTrigger>
              <SelectContent>
                <div className="p-2 pb-1">
                  <Input
                    value={modelSearch}
                    onChange={(event) => setModelSearch(event.target.value)}
                    placeholder={t("chat.model.search_placeholder")}
                    className="h-9"
                  />
                </div>
                {filteredModels.map((model) => (
                  <SelectItem key={model.value} value={model.value} textValue={model.label}>
                    {model.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      </div>
    </div>
  );
}
