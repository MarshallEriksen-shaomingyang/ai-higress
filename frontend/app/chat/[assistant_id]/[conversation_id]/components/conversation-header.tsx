"use client";

import { useMemo, useState } from "react";
import { Pencil } from "lucide-react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { useI18n } from "@/lib/i18n-context";
import { useChatStore } from "@/lib/stores/chat-store";
import { useAssistant } from "@/lib/swr/use-assistants";
import { useLogicalModels } from "@/lib/swr/use-logical-models";
import { useUpdateConversation } from "@/lib/swr/use-conversations";
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
  const { mutate } = useSWRConfig();

  const updateConversation = useUpdateConversation();
  const { assistant } = useAssistant(assistantId);
  const { models } = useLogicalModels();

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

  const [renameOpen, setRenameOpen] = useState(false);
  const [draftTitle, setDraftTitle] = useState(title || "");

  const displayTitle = (title || "").trim() || t("chat.conversation.untitled");

  const handleRename = async () => {
    try {
      const newTitle = draftTitle.trim();
      await updateConversation(conversationId, { title: newTitle || undefined });

      // refresh conversations list cache (used by sidebar and this page)
      const qs = new URLSearchParams();
      qs.set("assistant_id", assistantId);
      qs.set("limit", "50");
      await mutate(`/v1/conversations?${qs.toString()}`);

      toast.success(t("chat.conversation.renamed"));
      setRenameOpen(false);
    } catch (error) {
      console.error("Failed to rename conversation:", error);
      toast.error(t("chat.conversation.rename_failed"));
    }
  };

  return (
    <>
      <div className="flex items-center justify-between gap-3 border-b bg-background px-4 py-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{displayTitle}</div>
          <div className="truncate text-xs text-muted-foreground">
            {t("chat.header.model_label")}:{" "}
            {currentOverride || effectiveAssistantDefaultModel}
          </div>
        </div>

        <div className="flex items-center gap-2">
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

          <Button
            variant="ghost"
            size="icon"
            aria-label={t("chat.conversation.rename")}
            onClick={() => {
              setDraftTitle(title || "");
              setRenameOpen(true);
            }}
          >
            <Pencil className="size-4" />
          </Button>
        </div>
      </div>

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent aria-describedby="rename-conversation-dialog-description">
          <DialogHeader>
            <DialogTitle>{t("chat.conversation.rename")}</DialogTitle>
            <DialogDescription id="rename-conversation-dialog-description">
              {t("chat.conversation.rename_description")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Input
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              placeholder={t("chat.conversation.rename_placeholder")}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameOpen(false)}>
              {t("chat.action.cancel")}
            </Button>
            <Button onClick={handleRename}>{t("chat.action.save")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
