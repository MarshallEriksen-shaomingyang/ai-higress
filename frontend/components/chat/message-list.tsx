"use client";

import { memo, useEffect, useRef, useState, useMemo, useCallback } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useSWRConfig } from "swr";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { MessageItem } from "./message-item";
import { ErrorAlert } from "./error-alert";
import { AddComparisonDialog } from "./add-comparison-dialog";
import { ConversationPendingIndicator } from "./conversation-pending-indicator";
import { ChatWelcomeContent } from "./chat-welcome-content";
import { AssistantImageGenerationMessageItem } from "@/components/chat/assistant-image-generation-message-item";
import { useI18n } from "@/lib/i18n-context";
import { useErrorDisplay } from "@/lib/errors/error-display";
import { useMessages } from "@/lib/swr/use-messages";
import { useDeleteConversation } from "@/lib/swr/use-conversations";
import { useCachePreloader } from "@/lib/swr/cache";
import { messageService } from "@/http/message";
import { conversationService } from "@/http/conversation";
import { useAuth } from "@/components/providers/auth-provider";
import { useAssistant } from "@/lib/swr/use-assistants";
import { useLogicalModels } from "@/lib/swr/use-logical-models";
import { buildComparisonPayload, buildRegeneratePayload } from "@/lib/chat/payload-builder";
import { useChatStore } from "@/lib/stores/chat-store";
import { useConversationPending } from "@/lib/hooks/use-conversation-pending";
import { useComposerTaskStore } from "@/lib/stores/composer-task-store";
import type { ComposerTask } from "@/lib/chat/composer-tasks";
import { ComposerTaskMessageItem } from "@/components/chat/composer-task-message-item";
import {
  useChatComparisonStore,
  type ComparisonVariant,
} from "@/lib/stores/chat-comparison-store";
import type { Message, RunSummary } from "@/lib/api-types";
import { useBridgeAgents } from "@/lib/swr/use-bridge";

const isValidUuid = (value: string) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);

export interface MessageListProps {
  assistantId: string;
  conversationId: string;
  onViewDetails?: (runId: string) => void;
  onTriggerEval?: (messageId: string, runId: string) => void;
  showEvalButton?: boolean;
  overrideLogicalModel?: string | null;
  disabledActions?: boolean;
}

type RenderItem =
  | { type: 'message'; key: string; message: Message; runs?: RunSummary[]; runSourceMessageId?: string; timestamp: number }
  | { type: 'composer-task'; key: string; role: 'user' | 'assistant'; task: ComposerTask; timestamp: number };

export const MessageList = memo(function MessageList({
  assistantId,
  conversationId,
  onViewDetails,
  onTriggerEval,
  showEvalButton = true,
  overrideLogicalModel: _overrideLogicalModel = null,
  disabledActions = false,
}: MessageListProps) {
  const { t, language } = useI18n();
  const router = useRouter();
  const { mutate: globalMutate } = useSWRConfig();
  const { user } = useAuth();
  const { assistant } = useAssistant(assistantId);
  const projectId = assistant?.project_id ?? null;
  const { models } = useLogicalModels(projectId);
  const { showError } = useErrorDisplay();
  const { preloadData } = useCachePreloader();
  const setSelectedConversation = useChatStore((s) => s.setSelectedConversation);
  const isPendingResponse =
    useChatStore((s) => s.conversationPending[conversationId]) ?? false;
  const { runWithPending } = useConversationPending();
  const bridgeAgentIds = useChatStore((s) => s.conversationBridgeAgentIds[conversationId]) ?? [];
  const bridgeToolSelections = useChatStore((s) => s.conversationBridgeToolSelections[conversationId]) ?? {};
  const defaultBridgeToolSelections = useChatStore((s) => s.defaultBridgeToolSelections) ?? {};
  const lastModelPreset = useChatStore((s) => s.conversationModelPresets[conversationId]);

  const { agents: bridgeAgents } = useBridgeAgents();
  const availableBridgeAgentIds = useMemo(() => {
    const ids = new Set<string>();
    for (const agent of bridgeAgents || []) {
      const id = typeof agent.agent_id === "string" ? agent.agent_id.trim() : "";
      if (id) ids.add(id);
    }
    return ids;
  }, [bridgeAgents]);

  const deleteConversation = useDeleteConversation();

  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);
  const [regenerateMessageDialogOpen, setRegenerateMessageDialogOpen] =
    useState(false);
  const [regenerateTarget, setRegenerateTarget] = useState<{ 
    assistantMessageId: string;
    sourceUserMessageId?: string;
  } | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isDeletingConversation, setIsDeletingConversation] = useState(false);
  const [deletingMessageId, setDeletingMessageId] = useState<string | null>(null);
  const [deleteMessageDialogOpen, setDeleteMessageDialogOpen] = useState(false);
  const [deleteMessageTarget, setDeleteMessageTarget] = useState<string | null>(null);
  const [regenErrorById, setRegenErrorById] = useState<Record<string, string>>({});
  const [cursor, setCursor] = useState<string | undefined>();
  const [allMessages, setAllMessages] = useState<
    Array<{ message: Message; run?: RunSummary; runs?: RunSummary[] }>
  >([]);
  const parentRef = useRef<HTMLDivElement>(null);
  const variantsByKey = useChatComparisonStore((s) => s.variantsByKey);
  const addVariant = useChatComparisonStore((s) => s.addVariant);
  const updateVariant = useChatComparisonStore((s) => s.updateVariant);

  const [compareDialogOpen, setCompareDialogOpen] = useState(false);
  const [compareBusy, setCompareBusy] = useState(false);
  const [compareSelectedModel, setCompareSelectedModel] = useState<string | null>(
    null
  );
  const [compareTarget, setCompareTarget] = useState<{ 
    assistantMessageId: string;
    sourceUserMessageId: string;
    baselineModel?: string;
  } | null>(null);

  const composerTasks = useComposerTaskStore((s) => s.tasks);
  const tasksForConversation = useMemo(
    () => composerTasks.filter((t) => t.conversationId === conversationId),
    [composerTasks, conversationId]
  );

  useEffect(() => {
    setCursor(undefined);
    setAllMessages([]);
  }, [conversationId]);

  const { messages, nextCursor, isLoading, isError, error, mutate: mutateMessages } = useMessages(
    conversationId,
    { cursor, limit: 50 }
  );

  useEffect(() => {
    if (nextCursor && !isLoading) {
      const nextPageKey = {
        url: `/v1/conversations/${conversationId}/messages`,
        params: { cursor: nextCursor, limit: 50 },
      };
      
      preloadData(
        JSON.stringify(nextPageKey),
        () => messageService.getMessages(conversationId, {
          cursor: nextCursor,
          limit: 50,
        })
      );
    }
  }, [nextCursor, conversationId, isLoading, preloadData]);

  useEffect(() => {
    if (messages.length > 0) {
      setAllMessages((prev) => {
        if (!cursor) {
          if (prev.length === 0) return messages;

          const prevContentMap = new Map(
            prev.map((item) => [item.message.message_id, item.message.content])
          );

          return messages.map((item) => {
            const existingContent = prevContentMap.get(item.message.message_id);
            const nextContent = (item.message.content || "").trim();

            if (
              item.message.role === "assistant" &&
              !nextContent &&
              existingContent
            ) {
              return {
                ...item,
                message: { ...item.message, content: existingContent },
              };
            }

            return item;
          });
        }
        return [...prev, ...messages];
      });
    }
  }, [messages, cursor]);

  useEffect(() => {
    if (isLoading || isError) return;
    if (messages.length !== 0) return;

    if (cursor) {
      setCursor(undefined);
    }
    setAllMessages([]);
  }, [cursor, isError, isLoading, messages.length]);

  const displayMessages = useMemo(() => {
    return [...allMessages].reverse();
  }, [allMessages]);

  const availableModels = useMemo(() => {
    const modelSet = new Set<string>();

    for (const model of models) {
      if (!model.enabled) continue;
      if (!model.capabilities?.includes("chat")) continue;
      modelSet.add(model.logical_id);
    }

    return Array.from(modelSet).sort();
  }, [models]);

  const displayRows = useMemo(() => {
    const rows: Array<{ 
      message: Message;
      runs: RunSummary[];
      runSourceMessageId?: string;
    }> = [];

    let lastUserMessageId: string | undefined;
    let lastUserRuns: RunSummary[] = [];

    for (const item of displayMessages) {
      if (item.message.role === "user") {
        lastUserMessageId = item.message.message_id;
        lastUserRuns = (item.runs && item.runs.length ? item.runs : item.run ? [item.run] : []);
        rows.push({ message: item.message, runs: [] });
        continue;
      }

      rows.push({
        message: item.message,
        runs: lastUserRuns,
        runSourceMessageId: lastUserMessageId,
      });
      lastUserRuns = [];
    }

    return rows;
  }, [displayMessages]);

  const renderRows = useMemo(() => {
    if (!isPendingResponse) return displayRows;
    return displayRows.filter(
      (row) =>
        row.message.role !== "assistant" ||
        row.message.message_id === regeneratingId ||
        (row.message.content || "").trim().length > 0
    );
  }, [displayRows, isPendingResponse, regeneratingId]);

  const latestAssistantMessageId = useMemo(() => {
    for (let idx = renderRows.length - 1; idx >= 0; idx -= 1) {
      const row = renderRows[idx];
      if (row?.message.role === "assistant") {
        return row.message.message_id;
      }
    }
    return null;
  }, [renderRows]);

  // Combine standard messages with composer tasks
  const finalRenderItems = useMemo(() => {
    const items: RenderItem[] = [];

    // Add standard messages
    for (const row of renderRows) {
      items.push({
        type: 'message',
        key: row.message.message_id,
        message: row.message,
        runs: row.runs,
        runSourceMessageId: row.runSourceMessageId,
        timestamp: new Date(row.message.created_at).getTime(),
      });
    }

    for (const task of tasksForConversation) {
      // User prompt fake message
      items.push({
        type: 'composer-task',
        key: `${task.kind}:${task.id}:user`,
        role: 'user',
        task,
        timestamp: task.createdAt,
      });
      // Assistant result
      items.push({
        type: 'composer-task',
        key: `${task.kind}:${task.id}:assistant`,
        role: 'assistant',
        task,
        timestamp: task.createdAt + 1, // ensure it appears after user prompt
      });
    }

    return items.sort((a, b) => a.timestamp - b.timestamp);
  }, [renderRows, tasksForConversation]);

  const handleRegenerate = useCallback(
    async (assistantMessageId: string, _sourceUserMessageId?: string) => {
      if (!isValidUuid(assistantMessageId)) {
        const message = t("chat.message.retry_failed");
        toast.error(message);
        setRegenErrorById((prev) => ({ ...prev, [assistantMessageId]: message }));
        return;
      }

      setRegeneratingId(assistantMessageId);
      setRegenErrorById((prev) => {
        const next = { ...prev };
        delete next[assistantMessageId];
        return next;
      });
      try {
        setAllMessages((prev) =>
          prev.map((item) => {
            if (item.message.message_id !== assistantMessageId) return item;
            if (item.message.role !== "assistant") return item;
            return {
              ...item,
              message: { ...item.message, content: "" },
            };
          })
        );
        await runWithPending(
          conversationId,
          async () => {
            const regeneratePayload = buildRegeneratePayload({
              modelPreset: lastModelPreset ?? null,
              overrideLogicalModel: _overrideLogicalModel ?? null,
              bridgeState: {
                conversationBridgeAgentIds: bridgeAgentIds,
                conversationBridgeToolSelections: bridgeToolSelections,
                defaultBridgeToolSelections,
              },
              availableBridgeAgentIds,
            });
            await messageService.regenerateMessage(assistantMessageId, regeneratePayload);
            await mutateMessages();
          },
          { minDurationMs: 250 }
        );
      } catch (error) {
        console.error("Failed to regenerate message", error);
        const message =
          (error as any)?.message && typeof (error as any).message === "string"
            ? (error as any).message
            : t("chat.message.retry_failed");
        setRegenErrorById((prev) => ({ ...prev, [assistantMessageId]: message }));
      } finally {
        setRegeneratingId(null);
      }
    },
    [
      conversationId,
      mutateMessages,
      runWithPending,
      t,
      _overrideLogicalModel,
      bridgeAgentIds,
      bridgeToolSelections,
      defaultBridgeToolSelections,
      lastModelPreset,
      availableBridgeAgentIds,
    ]
  );

  const openRegenerateDialog = useCallback(
    (assistantMessageId: string, sourceUserMessageId?: string) => {
      if (!isValidUuid(assistantMessageId)) {
        const message = t("chat.message.retry_failed");
        toast.error(message);
        setRegenErrorById((prev) => ({ ...prev, [assistantMessageId]: message }));
        return;
      }
      setRegenerateTarget({ assistantMessageId, sourceUserMessageId });
      setRegenerateMessageDialogOpen(true);
    },
    [t]
  );

  const handleDeleteMessage = useCallback(
    async (messageId: string) => {
      setDeletingMessageId(messageId);
      try {
        await messageService.deleteMessage(messageId);
        await mutateMessages();
      } catch (error) {
        console.error("Failed to delete message", error);
      } finally {
        setDeletingMessageId(null);
        setDeleteMessageDialogOpen(false);
        setDeleteMessageTarget(null);
      }
    },
    [mutateMessages]
  );

  const confirmDeleteConversation = useCallback(async () => {
    setIsDeletingConversation(true);
    try {
      await deleteConversation(conversationId);
      setSelectedConversation(null);
      toast.success(t("chat.conversation.deleted"));

      const conversationsKey = `/v1/conversations?assistant_id=${assistantId}&limit=50`;
      await globalMutate(conversationsKey);
      await globalMutate(
        `/v1/conversations/${conversationId}/messages?limit=50`,
        undefined,
        { revalidate: false }
      );

      router.push(`/chat/${assistantId}`);
    } catch (error) {
      showError(error, { context: t("chat.conversation.delete") });
    } finally {
      setIsDeletingConversation(false);
      setDeleteDialogOpen(false);
    }
  }, [
    assistantId,
    conversationId,
    deleteConversation,
    globalMutate,
    router,
    setSelectedConversation,
    showError,
    t,
  ]);

  const buildComparisonPrompt = useCallback(
    (sourceUserMessageId: string) => {
      const idx = displayMessages.findIndex(
        (item) =>
          item.message.message_id === sourceUserMessageId &&
          item.message.role === "user"
      );
      if (idx === -1) return null;

      const roleLabel =
        language === "zh"
          ? { user: "用户", assistant: "助手" }
          : { user: "User", assistant: "Assistant" };

      const instruction =
        language === "zh"
          ? "请基于以下对话内容，回答最后一条用户消息。"
          : "Based on the conversation below, answer the last user message.";

      const lines: string[] = [];
      for (let i = 0; i <= idx; i += 1) {
        const row = displayMessages[i];
        const msg = row?.message;
        if (!msg) continue;
        if (msg.role !== "user" && msg.role !== "assistant") continue;
        const label = msg.role === "user" ? roleLabel.user : roleLabel.assistant;
        lines.push(`${label}: ${msg.content}`);
      }

      const maxChars = 18_000;
      const sep = "\n\n";
      let remaining = maxChars - instruction.length - sep.length;
      if (remaining <= 0) return instruction;

      const selected: string[] = [];
      for (let i = lines.length - 1; i >= 0; i -= 1) {
        const line = lines[i] ?? "";
        const needed = line.length + (selected.length ? sep.length : 0);
        if (needed > remaining) {
          if (selected.length === 0 && remaining > 20) {
            selected.unshift(line.slice(-remaining));
          }
          break;
        }
        selected.unshift(line);
        remaining -= needed;
      }

      return `${instruction}${sep}${selected.join(sep)}`.trim();
    },
    [displayMessages, language]
  );

  const openCompareDialog = useCallback(
    (assistantMessageId: string, sourceUserMessageId: string, baselineModel?: string) => {
      setCompareTarget({ assistantMessageId, sourceUserMessageId, baselineModel });
      const preferred =
        availableModels.find((m) => m !== baselineModel) ?? availableModels[0] ?? null;
      setCompareSelectedModel(preferred);
      setCompareDialogOpen(true);
    },
    [availableModels]
  );

  const handleConfirmComparison = useCallback(async () => {
    if (!compareTarget || !compareSelectedModel) return;

    const prompt = buildComparisonPrompt(compareTarget.sourceUserMessageId);
    if (!prompt) {
      showError(new Error("Missing source message for comparison"), {
        context: t("chat.message.add_comparison_failed"),
      });
      return;
    }
    const projectId = assistant?.project_id;
    if (!projectId) {
      showError(new Error("Missing assistant project_id for comparison"), {
        context: t("chat.message.add_comparison_failed"),
      });
      return;
    }

    const key = `${conversationId}:${compareTarget.assistantMessageId}`;
    const variantId = `cmp-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const createdAt = new Date().toISOString();
    const baseVariant: ComparisonVariant = {
      id: variantId,
      model: compareSelectedModel,
      status: "running",
      created_at: createdAt,
    };

    addVariant(key, baseVariant);
    setCompareDialogOpen(false);
    setCompareBusy(true);

    try {
      const tempConversation = await conversationService.createConversation({
        assistant_id: assistantId,
        project_id: projectId,
        title: undefined,
      });

      try {
        await messageService.sendMessage(tempConversation.conversation_id, {
          ...buildComparisonPayload({
            content: prompt,
            overrideLogicalModel: compareSelectedModel,
            modelPreset: lastModelPreset ?? null,
            bridgeState: {
              conversationBridgeAgentIds: bridgeAgentIds,
              conversationBridgeToolSelections: bridgeToolSelections,
              defaultBridgeToolSelections,
            },
            availableBridgeAgentIds,
          }),
        });

        const tempMessages = await messageService.getMessages(
          tempConversation.conversation_id,
          { limit: 10 }
        );
        const assistantMsg = tempMessages.items.find(
          (it) =>
            it.message.role === "assistant" &&
            typeof it.message.content === "string" &&
            it.message.content.trim().length > 0
        )?.message;

        const content = assistantMsg?.content?.trim() || "";
        if (!content) {
          updateVariant(key, variantId, {
            status: "failed",
            error_message: t("chat.message.add_comparison_empty"),
          });
          return;
        }

        updateVariant(key, variantId, { status: "succeeded", content });
      } finally {
        await conversationService
          .deleteConversation(tempConversation.conversation_id)
          .catch(() => undefined);
      }
    } catch (error) {
      updateVariant(key, variantId, {
        status: "failed",
        error_message: t("chat.message.add_comparison_failed"),
      });
      showError(error, { context: t("chat.message.add_comparison_failed") });
    } finally {
      setCompareBusy(false);
    }
  }, [
    addVariant,
    buildComparisonPrompt,
    compareSelectedModel,
    compareTarget,
    conversationId,
    assistant?.project_id,
    assistantId,
    bridgeAgentIds,
    bridgeToolSelections,
    defaultBridgeToolSelections,
    lastModelPreset,
    availableBridgeAgentIds,
    showError,
    t,
    updateVariant,
  ]);

  const rowVirtualizer = useVirtualizer({
    count: finalRenderItems.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 100,
    overscan: 5,
  });

  const loadMore = () => {
    if (nextCursor && !isLoading) {
      setCursor(nextCursor);
    }
  };

  const scrollToBottom = () => {
    if (parentRef.current) {
      parentRef.current.scrollTop = parentRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    if (!isLoading && finalRenderItems.length > 0 && !cursor) {
      setTimeout(scrollToBottom, 100);
    }
  }, [isLoading, finalRenderItems.length, cursor]);

  if (!isLoading && finalRenderItems.length === 0) {
    return (
      <div className="h-full overflow-y-auto" role="status" aria-live="polite">
        <ChatWelcomeContent />
      </div>
    );
  }

  if (isError) {
    return (
      <div 
        className="flex flex-col items-center justify-center h-full text-center p-8"
        role="alert"
        aria-live="assertive"
      >
        <ErrorAlert error={error} className="mb-4 max-w-md" />
        <Button 
          variant="outline" 
          size="sm" 
          onClick={() => setCursor(undefined)}
          aria-label={t("chat.action.retry_load_messages")}
        >
          {t("chat.action.retry")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" role="region" aria-label={t("chat.message.list_label")}>
      {nextCursor && (
        <div className="flex justify-center p-4 border-b">
          <Button
            variant="outline"
            size="sm"
            onClick={loadMore}
            disabled={isLoading}
            aria-label={isLoading ? t("chat.message.loading") : t("chat.message.load_more")}
          >
            {isLoading ? (
              <>
                <Loader2 className="size-4 animate-spin mr-2" aria-hidden="true" />
                {t("chat.message.loading")}
              </>
            ) : (
              t("chat.message.load_more")
            )}
          </Button>
        </div>
      )}

      <div
        ref={parentRef}
        className="flex-1 overflow-y-auto py-6"
        role="log"
        aria-live="polite"
        aria-atomic="false"
        aria-relevant="additions"
        style={{
          contain: "strict",
        }}
      >
        <div className="mx-auto w-full max-w-3xl px-4">
          <div
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              width: "100%",
              position: "relative",
            }}
          >
            {rowVirtualizer.getVirtualItems().map((virtualItem) => {
              const item = finalRenderItems[virtualItem.index];
              if (!item) return null;

              if (item.type === 'message') {
                const isAssistantImageGen =
                  item.message.role === "assistant" && !!item.message.image_generation;
                return (
                  <div
                    key={virtualItem.key}
                    data-index={virtualItem.index}
                    ref={rowVirtualizer.measureElement}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${virtualItem.start}px)`,
                    }}
                  >
                    <div className="pb-6">
                      {isAssistantImageGen ? (
                        <AssistantImageGenerationMessageItem message={item.message} />
                      ) : (
                        <MessageItem
                          message={item.message}
                          runs={item.runs}
                          runSourceMessageId={item.runSourceMessageId}
                          userAvatarUrl={user?.avatar ?? null}
                          userDisplayName={user?.display_name ?? user?.username ?? null}
                          onViewDetails={onViewDetails}
                          onTriggerEval={onTriggerEval}
                          showEvalButton={showEvalButton}
                          comparisonVariants={
                            variantsByKey[`${conversationId}:${item.message.message_id}`] ?? []
                          }
                          onAddComparison={(_, sourceUserMessageId) =>
                            openCompareDialog(
                              item.message.message_id,
                              sourceUserMessageId,
                              item.runs?.[0]?.requested_logical_model
                            )
                          }
                          isLatestAssistant={item.message.message_id === latestAssistantMessageId}
                          onRegenerate={
                            isValidUuid(item.message.message_id) ? openRegenerateDialog : undefined
                          }
                          isRegenerating={regeneratingId === item.message.message_id}
                          onDeleteMessage={
                            item.message.message_id === latestAssistantMessageId
                              ? () => {
                                  setDeleteMessageTarget(item.message.message_id);
                                  setDeleteMessageDialogOpen(true);
                                }
                              : undefined
                          }
                          isDeletingMessage={deletingMessageId === item.message.message_id}
                          disableActions={disabledActions || isLoading}
                          errorMessage={regenErrorById[item.message.message_id] ?? null}
                          enableTypewriter
                          typewriterKey={`${item.message.conversation_id}:${item.message.created_at}`}
                        />
                      )}
                    </div>
                  </div>
                );
              } else {
                return (
                  <div
                    key={virtualItem.key}
                    data-index={virtualItem.index}
                    ref={rowVirtualizer.measureElement}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${virtualItem.start}px)`,
                    }}
                  >
                    <div className="pb-6">
                      <ComposerTaskMessageItem
                        role={item.role}
                        task={item.task}
                        user={user}
                      />
                    </div>
                  </div>
                );
              }
            })}
          </div>
        </div>
      </div>

      {isLoading && finalRenderItems.length === 0 && (
        <div 
          className="flex items-center justify-center h-full"
          role="status"
          aria-live="polite"
        >
          <Loader2 className="size-6 animate-spin text-muted-foreground" aria-hidden="true" />
          <span className="ml-2 text-muted-foreground">
            {t("chat.message.loading")}
          </span>
        </div>
      )}

      <ConversationPendingIndicator conversationId={conversationId} />

      <AddComparisonDialog
        open={compareDialogOpen}
        onOpenChange={(open) => {
          if (!open) setCompareTarget(null);
          setCompareDialogOpen(open);
        }}
        availableModels={availableModels}
        selectedModel={compareSelectedModel}
        onSelectedModelChange={setCompareSelectedModel}
        onConfirm={() => void handleConfirmComparison()}
        isBusy={compareBusy}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("chat.conversation.delete")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("chat.conversation.delete_confirm")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeletingConversation}>
              {t("chat.action.cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => void confirmDeleteConversation()}
              disabled={isDeletingConversation}
            >
              {isDeletingConversation ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                t("chat.action.confirm")
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={regenerateMessageDialogOpen}
        onOpenChange={(open) => {
          setRegenerateMessageDialogOpen(open);
          if (!open) setRegenerateTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("chat.message.regenerate")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("chat.message.regenerate_confirm")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={regeneratingId !== null}>
              {t("chat.action.cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={regeneratingId !== null || !regenerateTarget}
              onClick={() => {
                if (regenerateTarget) {
                  void handleRegenerate(
                    regenerateTarget.assistantMessageId,
                    regenerateTarget.sourceUserMessageId
                  );
                }
              }}
            >
              {t("chat.action.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={deleteMessageDialogOpen} onOpenChange={setDeleteMessageDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("chat.message.delete")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("chat.message.delete_confirm")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              disabled={deletingMessageId !== null}
              onClick={() => setDeleteMessageDialogOpen(false)}
            >
              {t("chat.action.cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={deletingMessageId !== null || !deleteMessageTarget}
              onClick={() => {
                if (deleteMessageTarget) {
                  void handleDeleteMessage(deleteMessageTarget);
                }
              }}
            >
              {deletingMessageId ? <Loader2 className="size-4 animate-spin" /> : t("chat.action.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
});
