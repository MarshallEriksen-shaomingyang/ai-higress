"use client";

import dynamic from "next/dynamic";
import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import type { Layout } from "react-resizable-panels";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { useAuth } from "@/components/providers/auth-provider";
import { ConversationChatInput } from "@/components/chat/conversation-chat-input";
import { MessageList } from "@/components/chat/message-list";
import { cn } from "@/lib/utils";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { useI18n } from "@/lib/i18n-context";
import { useChatLayoutStore } from "@/lib/stores/chat-layout-store";
import { useChatStore } from "@/lib/stores/chat-store";
import type { ChallengerRun, EvalExplanation, EvalResponse } from "@/lib/api-types";
import { useConversationFromList } from "@/lib/swr/use-conversations";
import { useCreateEval } from "@/lib/swr/use-evals";
import { ConversationHeader } from "./conversation-header";
import { streamSSERequest, type SSEMessage } from "@/lib/bridge/sse";

const EvalPanel = dynamic(
  () =>
    import("@/components/chat/eval-panel").then((mod) => ({
      default: mod.EvalPanel,
    })),
  {
    loading: () => (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    ),
    ssr: false,
  }
);

export function ConversationPageClient({
  assistantId,
  conversationId,
}: {
  assistantId: string;
  conversationId: string;
}) {
  const { t } = useI18n();
  const { user } = useAuth();
  const { mutate: globalMutate } = useSWRConfig();

  const conversation = useConversationFromList(conversationId, assistantId);
  const selectedProjectId = useChatStore((s) => s.selectedProjectId);
  const setSelectedAssistant = useChatStore((s) => s.setSelectedAssistant);
  const setSelectedConversation = useChatStore((s) => s.setSelectedConversation);
  const activeEvalId = useChatStore((s) => s.activeEvalId);
  const setActiveEval = useChatStore((s) => s.setActiveEval);
  const evalStreamingEnabled = useChatStore((s) => s.evalStreamingEnabled);
  const overrideLogicalModel = useChatStore(
    (s) => s.conversationModelOverrides[conversationId] ?? null
  );
  const setChatVerticalLayout = useChatLayoutStore(
    (s) => s.setChatVerticalLayout
  );
  const createEval = useCreateEval();

  const isImmersive = useChatLayoutStore((s) => s.isImmersive);
  const setIsImmersive = useChatLayoutStore((s) => s.setIsImmersive);

  // 同步 URL 中的 assistantId 和 conversationId 到全局状态
  useEffect(() => {
    setSelectedAssistant(assistantId);
    setSelectedConversation(conversationId);
  }, [assistantId, conversationId, setSelectedAssistant, setSelectedConversation]);

  useEffect(() => {
    if (!isImmersive) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key !== "Escape") return;
      setIsImmersive(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isImmersive, setIsImmersive]);

  const evalStreamControllerRef = useRef<AbortController | null>(null);
  useEffect(() => {
    return () => {
      evalStreamControllerRef.current?.abort();
      evalStreamControllerRef.current = null;
    };
  }, []);

  const defaultVerticalLayout = useMemo(() => {
    const storedVerticalLayout =
      useChatLayoutStore.getState().chatVerticalLayout;
    if (!storedVerticalLayout) return undefined;

    const isValid =
      storedVerticalLayout &&
      typeof storedVerticalLayout === "object" &&
      "message-list" in storedVerticalLayout &&
      "message-input" in storedVerticalLayout &&
      Object.keys(storedVerticalLayout).length === 2;

    return isValid ? storedVerticalLayout : undefined;
  }, []);

  const verticalLayoutDebounceTimerRef = useRef<number | null>(null);
  const pendingVerticalLayoutRef = useRef<Layout | null>(null);

  const handleVerticalLayoutChange = useCallback(
    (layout: Layout) => {
      pendingVerticalLayoutRef.current = layout;
      if (verticalLayoutDebounceTimerRef.current !== null) {
        window.clearTimeout(verticalLayoutDebounceTimerRef.current);
      }
      verticalLayoutDebounceTimerRef.current = window.setTimeout(() => {
        if (pendingVerticalLayoutRef.current) {
          setChatVerticalLayout(pendingVerticalLayoutRef.current);
        }
      }, 200);
    },
    [setChatVerticalLayout]
  );

  useEffect(() => {
    return () => {
      if (verticalLayoutDebounceTimerRef.current !== null) {
        window.clearTimeout(verticalLayoutDebounceTimerRef.current);
      }
      if (pendingVerticalLayoutRef.current) {
        setChatVerticalLayout(pendingVerticalLayoutRef.current);
      }
    };
  }, [setChatVerticalLayout]);

  const handleTriggerEval = useCallback(async (
    messageId: string,
    baselineRunId: string
  ) => {
    if (!user || !selectedProjectId) return;

    try {
      if (!evalStreamingEnabled) {
        const result = await createEval({
          project_id: selectedProjectId,
          assistant_id: assistantId,
          conversation_id: conversationId,
          message_id: messageId,
          baseline_run_id: baselineRunId,
        });

        setActiveEval(result.eval_id);
        toast.success(t("chat.eval.trigger_success"));
        return;
      }

      evalStreamControllerRef.current?.abort();
      const controller = new AbortController();
      evalStreamControllerRef.current = controller;
      let streamedEvalId: string | null = null;

      const toRecord = (value: unknown): Record<string, unknown> | null => {
        if (!value || typeof value !== "object") return null;
        return value as Record<string, unknown>;
      };

      const getString = (record: Record<string, unknown>, key: string) => {
        const value = record[key];
        return typeof value === "string" ? value : "";
      };

      const getNumber = (record: Record<string, unknown>, key: string) => {
        const value = record[key];
        return typeof value === "number" ? value : undefined;
      };

      const toEvalExplanation = (explanation: unknown): EvalExplanation => {
        const record = toRecord(explanation);
        const summary = record ? getString(record, "summary") : "";
        const evidence = record ? record["evidence"] : undefined;
        if (evidence && typeof evidence === "object") {
          return { summary, evidence: evidence as EvalExplanation["evidence"] };
        }
        return { summary, evidence: {} };
      };

      const isChallengerStatus = (value: string): value is ChallengerRun["status"] =>
        value === "queued" || value === "running" || value === "succeeded" || value === "failed";

      const normalizeChallenger = (raw: unknown): ChallengerRun | null => {
        const record = toRecord(raw);
        if (!record) return null;
        const runId = getString(record, "run_id");
        const requestedLogicalModel = getString(record, "requested_logical_model");
        const statusRaw = getString(record, "status");
        if (!runId || !requestedLogicalModel || !isChallengerStatus(statusRaw)) return null;
        return {
          run_id: runId,
          requested_logical_model: requestedLogicalModel,
          status: statusRaw,
          output_preview:
            typeof record["output_preview"] === "string"
              ? (record["output_preview"] as string)
              : undefined,
          latency: getNumber(record, "latency_ms"),
          error_code:
            typeof record["error_code"] === "string"
              ? (record["error_code"] as string)
              : undefined,
        };
      };

      const upsertChallenger = (
        challengers: ChallengerRun[],
        patch: Partial<ChallengerRun> & { run_id: string }
      ) => {
        const idx = challengers.findIndex((c) => c.run_id === patch.run_id);
        if (idx === -1) {
          if (!patch.requested_logical_model || !patch.status) return challengers;
          return [...challengers, patch as ChallengerRun];
        }
        const next = [...challengers];
        const prev = next[idx];
        const updated = { ...prev } as ChallengerRun;
        if (patch.requested_logical_model !== undefined) {
          updated.requested_logical_model = patch.requested_logical_model;
        }
        if (patch.status !== undefined) {
          updated.status = patch.status;
        }
        if (patch.output_preview !== undefined) {
          updated.output_preview = patch.output_preview;
        }
        if (patch.latency !== undefined) {
          updated.latency = patch.latency;
        }
        if (patch.error_code !== undefined) {
          updated.error_code = patch.error_code;
        }
        next[idx] = updated;
        return next;
      };

      const previewFromText = (text: string | undefined) => {
        if (!text) return undefined;
        return text.slice(0, 380).trimEnd();
      };

      const handleStreamMessage = (msg: SSEMessage) => {
        if (!msg.data) return;
        if (msg.data === "[DONE]") return;

        let payload: unknown;
        try {
          payload = JSON.parse(msg.data);
        } catch {
          return;
        }
        const payloadRecord = toRecord(payload);
        if (!payloadRecord) return;

        const eventType = getString(payloadRecord, "type") || msg.event || "";
        if (!eventType) return;

        if (eventType === "eval.created") {
          const evalId = getString(payloadRecord, "eval_id");
          if (!evalId) return;
          streamedEvalId = evalId;

          const evalKey = `/v1/evals/${evalId}`;
          setActiveEval(evalId);
          toast.success(t("chat.eval.trigger_success"));

          const challengersValue = payloadRecord.challengers;
          const challengers = Array.isArray(challengersValue)
            ? (challengersValue
                .map(normalizeChallenger)
                .filter(Boolean) as ChallengerRun[])
            : [];

          void globalMutate(
            evalKey,
            {
              eval_id: evalId,
              status: (getString(payloadRecord, "status") || "running") as EvalResponse["status"],
              baseline_run_id: getString(payloadRecord, "baseline_run_id"),
              challengers,
              explanation: toEvalExplanation(payloadRecord.explanation),
              created_at: new Date().toISOString(),
            } satisfies EvalResponse,
            { revalidate: false }
          );
          return;
        }

        if (eventType === "eval.completed") {
          const evalId = getString(payloadRecord, "eval_id") || streamedEvalId || "";
          if (!evalId) return;
          const evalKey = `/v1/evals/${evalId}`;
          void globalMutate(
            evalKey,
            (current?: EvalResponse) => {
              if (!current) return current;
              return {
                ...current,
                status: (getString(payloadRecord, "status") || "ready") as EvalResponse["status"],
              };
            },
            { revalidate: false }
          );
          return;
        }

        const runId = getString(payloadRecord, "run_id");
        if (!runId) return;

        if (!streamedEvalId) return;
        const evalKey = `/v1/evals/${streamedEvalId}`;

        if (eventType === "run.delta") {
          const delta = getString(payloadRecord, "delta");
          if (!delta) return;
          void globalMutate(
            evalKey,
            (current?: EvalResponse) => {
              if (!current) return current;
              const existing = current.challengers.find((c) => c.run_id === runId);
              const nextPreview = previewFromText(`${existing?.output_preview || ""}${delta}`);
              return {
                ...current,
                challengers: upsertChallenger(current.challengers, {
                  run_id: runId,
                  status: "running",
                  output_preview: nextPreview,
                }),
              };
            },
            { revalidate: false }
          );
          return;
        }

        if (eventType === "run.completed") {
          void globalMutate(
            evalKey,
            (current?: EvalResponse) => {
              if (!current) return current;
              return {
                ...current,
                challengers: upsertChallenger(current.challengers, {
                  run_id: runId,
                  status: "succeeded",
                  latency: getNumber(payloadRecord, "latency_ms"),
                  output_preview: previewFromText(getString(payloadRecord, "full_text")),
                }),
              };
            },
            { revalidate: false }
          );
          return;
        }

        if (eventType === "run.error") {
          void globalMutate(
            evalKey,
            (current?: EvalResponse) => {
              if (!current) return current;
              return {
                ...current,
                challengers: upsertChallenger(current.challengers, {
                  run_id: runId,
                  status: "failed",
                  error_code: getString(payloadRecord, "error_code") || undefined,
                }),
              };
            },
            { revalidate: false }
          );
          return;
        }
      };

      void streamSSERequest(
        "/v1/evals",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
          },
          body: JSON.stringify({
            project_id: selectedProjectId,
            assistant_id: assistantId,
            conversation_id: conversationId,
            message_id: messageId,
            baseline_run_id: baselineRunId,
            streaming: true,
          }),
        },
        handleStreamMessage,
        controller.signal
      )
        .catch((err) => {
        const message = String(err?.name || err?.message || err || "");
        if (message.includes("AbortError")) return;
        console.error("Failed to stream eval:", err);
        toast.error(t("chat.eval.trigger_failed"));
        })
        .finally(() => {
          if (evalStreamControllerRef.current === controller) {
            evalStreamControllerRef.current = null;
          }
        });
    } catch (error) {
      console.error("Failed to trigger eval:", error);
      toast.error(t("chat.eval.trigger_failed"));
    }
  }, [
    assistantId,
    conversationId,
    createEval,
    evalStreamingEnabled,
    globalMutate,
    selectedProjectId,
    setActiveEval,
    t,
    user,
  ]);

  const handleCloseEval = useCallback(() => {
    setActiveEval(null);
  }, [setActiveEval]);

  // MCP 工具处理
  if (!conversation) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-2">
          <div className="text-muted-foreground">
            {t("chat.errors.conversation_not_found")}
          </div>
        </div>
      </div>
    );
  }

  const isArchived = conversation.archived;

  return (
    <div
      className={cn(
        "relative flex h-full min-h-0 flex-col overflow-hidden bg-background",
        isImmersive ? "fixed inset-0 z-[100] h-screen w-screen" : "h-full"
      )}
    >
      <ConversationHeader
        assistantId={assistantId}
        conversationId={conversationId}
        title={conversation.title}
        summaryText={conversation.summary_text ?? null}
        summaryUpdatedAt={conversation.summary_updated_at ?? null}
      />

      {isArchived && (
        <div className="bg-muted/50 border-b px-4 py-2 text-sm text-muted-foreground text-center">
          {t("chat.conversation.archived_notice")}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-hidden">
        <ResizablePanelGroup
          id={isImmersive ? "chat-vertical-layout-immersive" : "chat-vertical-layout"}
          direction="vertical"
          defaultLayout={defaultVerticalLayout}
          onLayoutChange={handleVerticalLayoutChange}
        >
          <ResizablePanel
            id="message-list"
            defaultSize="70%"
            minSize="0%"
            maxSize="100%"
          >
            <div className="h-full overflow-hidden">
              <MessageList
                assistantId={assistantId}
                conversationId={conversationId}
                overrideLogicalModel={overrideLogicalModel}
                disabledActions={isArchived}
                onTriggerEval={handleTriggerEval}
              />
            </div>
          </ResizablePanel>

          <ResizableHandle withHandle aria-orientation="horizontal" />

          <ResizablePanel
            id="message-input"
            defaultSize="30%"
            minSize="0%"
            maxSize="100%"
          >
            <div className="h-full bg-background">
              <ConversationChatInput
                conversationId={conversationId}
                assistantId={assistantId}
                overrideLogicalModel={overrideLogicalModel}
                disabled={isArchived}
                className="h-full border-t-0"
              />
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      {activeEvalId && (
        <div
          className={cn(
            "inset-y-0 right-0 w-full md:w-96 border-l bg-background shadow-lg overflow-y-auto",
            isImmersive ? "absolute z-[110]" : "fixed z-50"
          )}
        >
          <EvalPanel evalId={activeEvalId} onClose={handleCloseEval} />
        </div>
      )}
    </div>
  );
}
