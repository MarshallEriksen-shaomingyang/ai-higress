"use client";

import { useCallback, useMemo } from "react";
import { v4 as uuidv4 } from "uuid";
import { useSWRConfig } from "swr";

import { useI18n } from "@/lib/i18n-context";
import { streamSSERequest } from "@/lib/bridge/sse";
import { useConversationPending } from "@/lib/hooks/use-conversation-pending";
import type {
  ImageGenerationRequest,
  MessagesResponse,
  RunSummary,
} from "@/lib/api-types";

type SendConversationImageGenerationPayload = Pick<
  ImageGenerationRequest,
  "prompt" | "model" | "n" | "size" | "quality" | "extra_body"
> & {
  enableGoogleSearch?: boolean;
  sendResponseFormat?: boolean;
};

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, unknown>;
}

function getString(obj: Record<string, unknown>, key: string): string | null {
  const v = obj[key];
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

function parseRunSummary(value: unknown): RunSummary | null {
  const record = toRecord(value);
  if (!record) return null;
  const runId = getString(record, "run_id");
  const requestedLogicalModel = getString(record, "requested_logical_model");
  const status = getString(record, "status");
  if (!runId || !requestedLogicalModel || !status) return null;
  if (
    status !== "queued" &&
    status !== "running" &&
    status !== "succeeded" &&
    status !== "failed" &&
    status !== "canceled"
  ) {
    return null;
  }
  return {
    run_id: runId,
    requested_logical_model: requestedLogicalModel,
    status,
    output_preview:
      typeof record["output_preview"] === "string"
        ? (record["output_preview"] as string)
        : undefined,
    latency:
      typeof record["latency_ms"] === "number"
        ? (record["latency_ms"] as number)
        : undefined,
    error_code:
      typeof record["error_code"] === "string"
        ? (record["error_code"] as string)
        : undefined,
    tool_invocations: Array.isArray(record["tool_invocations"])
      ? (record["tool_invocations"] as RunSummary["tool_invocations"])
      : undefined,
  };
}

export function useSendConversationImageGeneration(conversationId: string | null) {
  const { t } = useI18n();
  const { mutate: globalMutate } = useSWRConfig();
  const { setPending } = useConversationPending();

  const messagesKey = useMemo(() => {
    if (!conversationId) return null;
    return `/v1/conversations/${conversationId}/messages?limit=50`;
  }, [conversationId]);

  return useCallback(
    async (payload: SendConversationImageGenerationPayload) => {
      if (!conversationId) throw new Error("Conversation ID is required");
      if (!messagesKey) throw new Error("Messages key is missing");

      const trimmedPrompt = String(payload.prompt || "").trim();
      const model = String(payload.model || "").trim();
      if (!trimmedPrompt) throw new Error(t("chat.image_gen.prompt"));
      if (!model) throw new Error(t("chat.image_gen.select_model"));

      const nonce = uuidv4();
      const createdAtIso = new Date().toISOString();
      const tempUserMessageId = `temp-img-user-${nonce}`;
      const tempAssistantMessageId = `temp-img-assistant-${nonce}`;

      const optimisticRun: RunSummary = {
        run_id: `temp-run-${nonce}`,
        requested_logical_model: model,
        status: "queued",
      };

      const optimisticUser = {
        message: {
          message_id: tempUserMessageId,
          conversation_id: conversationId,
          role: "user" as const,
          content: trimmedPrompt,
          created_at: createdAtIso,
        },
        runs: [optimisticRun],
        run: optimisticRun,
      };

      const optimisticAssistant = {
        message: {
          message_id: tempAssistantMessageId,
          conversation_id: conversationId,
          role: "assistant" as const,
          content: t("chat.image_gen.generating"),
          image_generation: {
            type: "image_generation" as const,
            status: "pending" as const,
            prompt: trimmedPrompt,
            params: {
              model,
              prompt: trimmedPrompt,
              n: payload.n,
              size: payload.size,
              quality: payload.quality,
              ...(payload.sendResponseFormat === false ? {} : { response_format: "url" as const }),
            },
            images: [],
          },
          created_at: createdAtIso,
        },
      };

      setPending(conversationId, true);

      // 乐观插入：注意后端列表是倒序，新消息应插入到 items 开头
      await globalMutate(
        messagesKey,
        (current?: MessagesResponse) => {
          if (!current) {
            return { items: [optimisticAssistant, optimisticUser], next_cursor: undefined };
          }
          return {
            ...current,
            items: [optimisticAssistant, optimisticUser, ...current.items],
          };
        },
        { revalidate: false }
      );

      let userMessageId = tempUserMessageId;
      let assistantMessageId = tempAssistantMessageId;
      let baselineRun: RunSummary | null = optimisticRun;

      const controller = new AbortController();
      const abortOnTerminal = () => {
        if (!controller.signal.aborted) controller.abort();
      };

      try {
        await streamSSERequest(
          `/v1/conversations/${conversationId}/image-generations`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "text/event-stream",
            },
            body: JSON.stringify({
              prompt: trimmedPrompt,
              model,
              n: payload.n,
              size: payload.size,
              quality: payload.quality,
              streaming: true,
              response_format: payload.sendResponseFormat === false ? null : ("url" as const),
              extra_body:
                payload.enableGoogleSearch || payload.extra_body
                  ? {
                      openai: {
                        ...(payload.enableGoogleSearch ? { tools: [{ google_search: {} }] } : {}),
                        ...(payload.extra_body?.openai ?? {}),
                      },
                      google: {
                        ...(payload.enableGoogleSearch
                          ? { tools: [{ googleSearch: {} }], responseModalities: ["TEXT", "IMAGE"] }
                          : {}),
                        ...(payload.extra_body?.google ?? {}),
                      },
                      ...(payload.extra_body
                        ? Object.fromEntries(
                            Object.entries(payload.extra_body).filter(
                              ([k]) => k !== "google" && k !== "openai"
                            )
                          )
                        : {}),
                    }
                  : undefined,
            }),
          },
          (msg) => {
            if (!msg.data) return;
            if (msg.data === "[DONE]") {
              abortOnTerminal();
              return;
            }
            let parsed: unknown;
            try {
              parsed = JSON.parse(msg.data);
            } catch {
              return;
            }
            const outer = toRecord(parsed);
            if (!outer) return;
            const type = getString(outer, "type") || msg.event;
            if (!type) return;

            if (type === "message.created") {
              const newUserId = getString(outer, "user_message_id");
              const newAssistantId = getString(outer, "assistant_message_id");
              if (newUserId) userMessageId = newUserId;
              if (newAssistantId) assistantMessageId = newAssistantId;
              baselineRun = parseRunSummary(outer["baseline_run"]);

              void globalMutate(
                messagesKey,
                (current?: MessagesResponse) => {
                  if (!current) return current;
                  return {
                    ...current,
                    items: current.items.map((it) => {
                      if (it.message.message_id === tempUserMessageId) {
                        return {
                          ...it,
                          message: { ...it.message, message_id: userMessageId },
                          run: baselineRun ?? it.run,
                          runs: baselineRun ? [baselineRun] : it.runs,
                        };
                      }
                      if (it.message.message_id === tempAssistantMessageId) {
                        return {
                          ...it,
                          message: { ...it.message, message_id: assistantMessageId },
                        };
                      }
                      return it;
                    }),
                  };
                },
                { revalidate: false }
              );
              return;
            }

            if (type === "message.completed") {
              baselineRun = parseRunSummary(outer["baseline_run"]) ?? baselineRun;
              const imageGen = toRecord(outer["image_generation"]);
              void globalMutate(
                messagesKey,
                (current?: MessagesResponse) => {
                  if (!current) return current;
                  return {
                    ...current,
                    items: current.items.map((it) => {
                      if (it.message.message_id === assistantMessageId) {
                        return {
                          ...it,
                          message: {
                            ...it.message,
                            content: "[图片]",
                            image_generation: imageGen ? (imageGen as any) : it.message.image_generation,
                          },
                        };
                      }
                      if (it.message.message_id === userMessageId) {
                        return { ...it, run: baselineRun ?? it.run, runs: baselineRun ? [baselineRun] : it.runs };
                      }
                      return it;
                    }),
                  };
                },
                { revalidate: false }
              );
              abortOnTerminal();
              return;
            }

            if (type === "message.failed") {
              baselineRun = parseRunSummary(outer["baseline_run"]) ?? baselineRun;
              const error = getString(outer, "error") || t("chat.image_gen.failed");
              void globalMutate(
                messagesKey,
                (current?: MessagesResponse) => {
                  if (!current) return current;
                  return {
                    ...current,
                    items: current.items.map((it) => {
                      if (it.message.message_id === assistantMessageId) {
                        return {
                          ...it,
                          message: {
                            ...it.message,
                            content: "[图片生成失败]",
                            image_generation: {
                              type: "image_generation" as const,
                              status: "failed" as const,
                              prompt: trimmedPrompt,
                              params: (it.message.image_generation?.params ??
                                {
                                  model,
                                  prompt: trimmedPrompt,
                                  n: payload.n,
                                  size: payload.size,
                                  quality: payload.quality,
                                  ...(payload.sendResponseFormat === false ? {} : { response_format: "url" }),
                                }) as any,
                              images: [],
                              error,
                            },
                          },
                        };
                      }
                      if (it.message.message_id === userMessageId) {
                        return { ...it, run: baselineRun ?? it.run, runs: baselineRun ? [baselineRun] : it.runs };
                      }
                      return it;
                    }),
                  };
                },
                { revalidate: false }
              );
              abortOnTerminal();
            }
          },
          controller.signal
        );
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          throw err;
        }
      } finally {
        setPending(conversationId, false);
        await globalMutate(messagesKey);
      }
    },
    [conversationId, globalMutate, messagesKey, setPending, t]
  );
}
