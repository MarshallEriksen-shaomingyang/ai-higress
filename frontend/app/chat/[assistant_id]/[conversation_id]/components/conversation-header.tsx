"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { useSWRConfig } from "swr";
import { toast } from "sonner";

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
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";

import { useI18n } from "@/lib/i18n-context";
import { useChatLayoutStore } from "@/lib/stores/chat-layout-store";
import { useChatStore } from "@/lib/stores/chat-store";
import { useUserPreferencesStore } from "@/lib/stores/user-preferences-store";
import { useConversationComposer } from "@/lib/hooks/use-conversation-composer";
import { useAssistant } from "@/lib/swr/use-assistants";
import { useLogicalModels } from "@/lib/swr/use-logical-models";
import { useProjectChatSettings } from "@/lib/swr/use-project-chat-settings";
import { useSelectableChatModels } from "@/lib/swr/use-selectable-chat-models";
import { conversationService } from "@/http/conversation";

const PROJECT_INHERIT_SENTINEL = "__project__";

export function ConversationHeader({
  assistantId,
  conversationId,
  title,
  summaryText,
  summaryUpdatedAt,
}: {
  assistantId: string;
  conversationId: string;
  title: string | null | undefined;
  summaryText: string | null | undefined;
  summaryUpdatedAt: string | null | undefined;
}) {
  const { t } = useI18n();
  const { mutate } = useSWRConfig();
  const isImmersive = useChatLayoutStore((s) => s.isImmersive);
  const setIsImmersive = useChatLayoutStore((s) => s.setIsImmersive);
  const { mode, image, setImageParams } = useConversationComposer(conversationId);

  const {
    conversationModelOverrides,
    setConversationModelOverride,
    selectedProjectId,
    evalStreamingEnabled,
    setEvalStreamingEnabled,
  } = useChatStore();
  const {
    preferences,
    setPreferredChatModel,
    setPreferredImageModel,
  } = useUserPreferencesStore();

  const { assistant } = useAssistant(assistantId);
  const { settings: projectSettings } = useProjectChatSettings(selectedProjectId);
  const { models: logicalModels } = useLogicalModels(selectedProjectId);

  const currentOverride = conversationModelOverrides[conversationId] ?? null;

  const preferredChatModel =
    selectedProjectId ? preferences.preferredChatModelByProject[selectedProjectId] ?? null : null;
  const preferredImageModel =
    selectedProjectId ? preferences.preferredImageModelByProject[selectedProjectId] ?? null : null;

  const rawAssistantDefaultModel =
    assistant?.default_logical_model === PROJECT_INHERIT_SENTINEL
      ? projectSettings?.default_logical_model ?? null
      : assistant?.default_logical_model ?? null;
  const assistantDefaultModel =
    rawAssistantDefaultModel && rawAssistantDefaultModel !== "auto"
      ? rawAssistantDefaultModel
      : null;

  const { options: selectableModels, filterOptions } = useSelectableChatModels(
    selectedProjectId,
    {
      includeAuto: false,
      extraModels: [currentOverride, assistantDefaultModel ?? undefined],
    }
  );

  const isModelSelectable = useCallback(
    (model: string | null | undefined) => {
      if (!model) return false;
      return selectableModels.some((item) => item.value === model);
    },
    [selectableModels]
  );

  const preferredChatModelCandidate = useMemo(
    () => (isModelSelectable(preferredChatModel) ? preferredChatModel : null),
    [isModelSelectable, preferredChatModel]
  );

  const assistantDefaultModelCandidate = useMemo(
    () => (isModelSelectable(assistantDefaultModel) ? assistantDefaultModel : null),
    [assistantDefaultModel, isModelSelectable]
  );

  const resolvedDefaultModel = useMemo(() => {
    if (preferredChatModelCandidate) return preferredChatModelCandidate;
    if (assistantDefaultModelCandidate) return assistantDefaultModelCandidate;
    return selectableModels[0]?.value ?? "";
  }, [assistantDefaultModelCandidate, preferredChatModelCandidate, selectableModels]);

  const effectiveSelectedModel = currentOverride ?? resolvedDefaultModel;
  const [modelSearch, setModelSearch] = useState("");

  useEffect(() => {
    if (currentOverride) return;
    if (preferredChatModelCandidate) {
      setConversationModelOverride(conversationId, preferredChatModelCandidate);
      return;
    }
    if (!assistantDefaultModelCandidate && resolvedDefaultModel) {
      setConversationModelOverride(conversationId, resolvedDefaultModel);
    }
  }, [
    assistantDefaultModelCandidate,
    conversationId,
    currentOverride,
    preferredChatModelCandidate,
    resolvedDefaultModel,
    setConversationModelOverride,
  ]);

  const filteredModels = useMemo(() => {
    const models = filterOptions(modelSearch);
    if (!effectiveSelectedModel) return models;
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
    const preferred =
      preferredImageModel && imageModels.some((m) => m.value === preferredImageModel)
        ? preferredImageModel
        : null;
    if (preferred) {
      setImageParams({ model: preferred });
      return;
    }
    const first = imageModels[0];
    if (!first) return;
    setImageParams({ model: first.value });
  }, [image.model, imageModels, mode, preferredImageModel, setImageParams]);

  useEffect(() => {
    setModelSearch("");
  }, [mode]);

  const conversationPending =
    useChatStore((s) => s.conversationPending[conversationId]) ?? false;
  const hasTitle = !!(title && title.trim());
  const isTitlePending = !hasTitle && conversationPending;
  const displayTitle = hasTitle ? title!.trim() : t("chat.conversation.untitled");

  const [summaryOpen, setSummaryOpen] = useState(false);
  const [isEditingSummary, setIsEditingSummary] = useState(false);
  const [draftSummary, setDraftSummary] = useState("");
  const [savingSummary, setSavingSummary] = useState(false);

  useEffect(() => {
    if (!summaryOpen) return;
    setIsEditingSummary(false);
    setDraftSummary((summaryText ?? "").trim());
  }, [summaryOpen, summaryText]);

  const handleSaveSummary = useCallback(async () => {
    if (savingSummary) return;
    setSavingSummary(true);
    try {
      await conversationService.updateConversation(conversationId, { summary: draftSummary });
      const key = `/v1/conversations?assistant_id=${assistantId}&limit=50`;
      await mutate(key);
      toast.success(t("chat.conversation.summary_saved"));
      setIsEditingSummary(false);
    } catch (err: any) {
      console.error("save conversation summary failed", err);
      toast.error(t("chat.conversation.summary_save_failed"));
    } finally {
      setSavingSummary(false);
    }
  }, [assistantId, conversationId, draftSummary, mutate, savingSummary, t]);

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
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSummaryOpen(true)}
              className="h-8 rounded-full px-2 md:px-3 text-xs font-medium md:h-9 md:text-sm"
            >
              <span className="hidden sm:inline">{t("chat.conversation.summary")}</span>
              <span className="sm:hidden text-[10px]">摘要</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="sm:hidden">
            {t("chat.conversation.summary")}
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex items-center gap-1 md:gap-2 rounded-full border border-border/30 bg-muted/20 px-1.5 md:px-2.5 py-0.5 md:py-1 transition-colors hover:bg-muted/35">
              <span className="text-[10px] md:text-xs text-muted-foreground hidden md:inline">
                {t("chat.eval.streaming_label")}
              </span>
              <Switch
                checked={evalStreamingEnabled}
                onCheckedChange={setEvalStreamingEnabled}
                aria-label={t("chat.eval.streaming_label")}
                className="scale-75 md:scale-100"
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
              className="h-7 w-7 md:h-9 md:w-9"
            >
              {isImmersive ? (
                <Minimize2 className="h-3.5 w-3.5 md:h-4 md:w-4" />
              ) : (
                <Maximize2 className="h-3.5 w-3.5 md:h-4 md:w-4" />
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
        <div className="w-[120px] md:w-[220px]">
          {mode === "image" ? (
            <Select
              value={image.model}
              onValueChange={(value) => {
                setImageParams({ model: value });
                setPreferredImageModel(selectedProjectId, value);
              }}
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
              value={effectiveSelectedModel ?? ""}
              onValueChange={(value) => {
                setPreferredChatModel(selectedProjectId, value);
                const shouldClearOverride =
                  assistantDefaultModelCandidate && value === assistantDefaultModelCandidate;
                setConversationModelOverride(
                  conversationId,
                  shouldClearOverride ? null : value
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

      <Dialog open={summaryOpen} onOpenChange={setSummaryOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t("chat.conversation.summary")}</DialogTitle>
            <DialogDescription>
              {summaryUpdatedAt
                ? t("chat.conversation.summary_updated_at", { time: summaryUpdatedAt })
                : t("chat.conversation.summary_description")}
            </DialogDescription>
          </DialogHeader>

          {isEditingSummary ? (
            <Textarea
              value={draftSummary}
              onChange={(e) => setDraftSummary(e.target.value)}
              placeholder={t("chat.conversation.summary_placeholder")}
              className="min-h-[220px]"
            />
          ) : (
            <div className="rounded-md border bg-muted/20 px-3 py-2 text-sm whitespace-pre-wrap">
              {(summaryText ?? "").trim()
                ? (summaryText ?? "").trim()
                : t("chat.conversation.summary_empty")}
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-2">
            {isEditingSummary ? (
              <>
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsEditingSummary(false);
                    setDraftSummary((summaryText ?? "").trim());
                  }}
                  disabled={savingSummary}
                >
                  {t("chat.action.cancel")}
                </Button>
                <Button onClick={handleSaveSummary} disabled={savingSummary}>
                  {savingSummary ? t("chat.action.saving") : t("chat.action.save")}
                </Button>
              </>
            ) : (
              <>
                <Button variant="outline" onClick={() => setSummaryOpen(false)}>
                  {t("chat.action.close")}
                </Button>
                <Button onClick={() => setIsEditingSummary(true)}>
                  {t("chat.conversation.summary_edit")}
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
