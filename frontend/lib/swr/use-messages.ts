"use client";

import useSWR, { useSWRConfig } from 'swr';
import { useMemo } from 'react';
import { messageService } from '@/http/message';
import { streamSSERequest } from '@/lib/bridge/sse';
import { useBridgeAgents } from '@/lib/swr/use-bridge';
import { useRunToolEventsStore } from '@/lib/stores/run-tool-events-store';
import { SWRCacheManager, cacheStrategies } from './cache';
import { ErrorHandler } from '@/lib/errors';
import { useConversationPending } from '@/lib/hooks/use-conversation-pending';
import type {
  GetMessagesParams,
  MessagesResponse,
  RunDetail,
  SendMessageRequest,
  RunSummary,
} from '@/lib/api-types';

type SendMessageOptions = {
  streaming?: boolean;
};

/**
 * 获取消息列表
 * 使用 frequent 缓存策略（实时对话场景）
 */
export function useMessages(conversationId: string | null, params?: GetMessagesParams) {
  // 使用字符串 key 确保序列化一致性
  const key = useMemo(() => {
    if (!conversationId) return null;
    
    const queryParams = new URLSearchParams();
    if (params?.cursor) queryParams.set('cursor', params.cursor);
    if (params?.limit) queryParams.set('limit', params.limit.toString());
    
    const queryString = queryParams.toString();
    return `/v1/conversations/${conversationId}/messages${queryString ? `?${queryString}` : ''}`;
  }, [conversationId, params?.cursor, params?.limit]);

  const { data, error, isLoading, mutate } = useSWR<MessagesResponse>(
    key,
    () => messageService.getMessages(conversationId!, params),
    cacheStrategies.frequent
  );

  return {
    messages: data?.items || [],
    nextCursor: data?.next_cursor,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}

/**
 * 获取 Run 详情（惰性加载）
 * 使用 default 缓存策略
 */
export function useRun(runId: string | null) {
  const key = runId ? `/v1/runs/${runId}` : null;

  const { data, error, isLoading, mutate } = useSWR<RunDetail>(
    key,
    () => messageService.getRun(runId!),
    cacheStrategies.default
  );

  return {
    run: data,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}

/**
 * 发送消息的 mutation hook
 * 支持乐观更新和回滚逻辑
 * 
 * 注意：后端返回的消息列表是倒序（新消息在前），所以：
 * - 新消息应该插入到列表开头（因为后端是倒序）
 * - 分页加载的旧消息应该插入到列表末尾（因为后端是倒序）
 */
export function useSendMessage(
  conversationId: string | null,
  assistantId?: string | null,
  overrideLogicalModel?: string | null
) {
  const sendMessageToConversation = useSendMessageToConversation(
    assistantId,
    overrideLogicalModel
  );

  return async (request: SendMessageRequest, options?: SendMessageOptions) => {
    if (!conversationId) throw new Error('Conversation ID is required');
    return await sendMessageToConversation(conversationId, request, options);
  };
}

/**
 * 发送消息（通用版本）：由调用方传入 conversationId，适合「先创建会话再发送」等场景。
 *
 * - 支持乐观更新与回滚
 * - 刷新会话列表（用于更新 last_activity_at / title）
 */
export function useSendMessageToConversation(
  assistantId?: string | null,
  overrideLogicalModel?: string | null
) {
  const { mutate: globalMutate } = useSWRConfig();
  const { agents: bridgeAgents } = useBridgeAgents();
  const { setPending } = useConversationPending();

  const availableBridgeAgentIds = useMemo(() => {
    const ids = new Set<string>();
    for (const agent of bridgeAgents || []) {
      const id = typeof agent.agent_id === 'string' ? agent.agent_id.trim() : '';
      if (id) ids.add(id);
    }
    return ids;
  }, [bridgeAgents]);

  return async (
    conversationId: string,
    request: SendMessageRequest,
    options?: SendMessageOptions
  ) => {
    const nonce = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const createdAt = new Date().toISOString();
    // 使用字符串 key 确保与 MessageList/useMessages 默认第一页一致（limit=50）
    const messagesKey = `/v1/conversations/${conversationId}/messages?limit=50`;
    const wantsStreaming = !!options?.streaming;
    const markPending = (pending: boolean) => setPending(conversationId, pending);
    const shouldShowPendingLoader = true;

    try {
      if (shouldShowPendingLoader) {
        markPending(true);
      }
      const sanitizeBridgePayload = (raw: SendMessageRequest): SendMessageRequest => {
        // 若当前未获取到任何可用的 Bridge Agent（未连接或加载失败），不要携带持久化的 Bridge 字段
        if (!availableBridgeAgentIds.size) {
          const {
            bridge_agent_id: _omitSingle,
            bridge_agent_ids: _omitList,
            bridge_tool_selections: _omitTools,
            ...rest
          } = raw as SendMessageRequest & Record<string, unknown>;
          return rest as SendMessageRequest;
        }

        const filterId = (value: unknown): string | null => {
          const v = typeof value === 'string' ? value.trim() : '';
          return v && availableBridgeAgentIds.has(v) ? v : null;
        };

        const filteredAgentIds = Array.isArray(raw.bridge_agent_ids)
          ? raw.bridge_agent_ids
              .map((id) => filterId(id))
              .filter((id): id is string => !!id)
          : [];

        const singleAgentId = filterId(raw.bridge_agent_id);

        const filteredToolSelections = Array.isArray(raw.bridge_tool_selections)
          ? raw.bridge_tool_selections
              .map((sel) => {
                const agentId = filterId((sel as any)?.agent_id);
                if (!agentId) return null;
                const names = Array.isArray((sel as any)?.tool_names)
                  ? (sel as any).tool_names
                      .map((n: unknown) => (typeof n === 'string' ? n.trim() : ''))
                      .filter(Boolean)
                  : [];
                if (!names.length) return null;
                return { agent_id: agentId, tool_names: names };
              })
              .filter((x): x is { agent_id: string; tool_names: string[] } => !!x)
          : [];

        const next: SendMessageRequest = {
          ...raw,
          bridge_agent_id: singleAgentId ?? undefined,
          bridge_agent_ids: filteredAgentIds.length ? filteredAgentIds : undefined,
          bridge_tool_selections: filteredToolSelections.length ? filteredToolSelections : undefined,
        };

        // 如果经过过滤后没有任何有效的 bridge 选择，则删除相关字段
        if (!next.bridge_agent_id && !next.bridge_agent_ids && !next.bridge_tool_selections) {
          delete (next as any).bridge_agent_id;
          delete (next as any).bridge_agent_ids;
          delete (next as any).bridge_tool_selections;
        }

        return next;
      };

      const payload: SendMessageRequest = sanitizeBridgePayload({ ...request });
      if (overrideLogicalModel) {
        payload.override_logical_model = overrideLogicalModel;
      }

      if (wantsStreaming) {
        const nonce = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const tempUserMessageId = `temp-${nonce}`;
        const tempAssistantMessageId = `temp-assistant-${nonce}`;
        const createdAt = new Date().toISOString();

        let userMessageId: string = tempUserMessageId;
        let assistantMessageId: string = tempAssistantMessageId;
        let assistantText = '';
        let assistantBuffer = '';
        let flushTimer: ReturnType<typeof setTimeout> | number | null = null;
        let baselineRun: RunSummary | null = null;
        const clearPending = () => {
          if (shouldShowPendingLoader) {
            markPending(false);
          }
        };

        const updateAssistantContent = (nextText: string) => {
          void globalMutate(
            messagesKey,
            (current?: MessagesResponse) => {
              if (!current) return current;
              const nextItems = current.items.map((it) => {
                if (it.message.message_id !== assistantMessageId) return it;
                return {
                  ...it,
                  message: { ...it.message, content: nextText },
                };
              });
              return { ...current, items: nextItems };
            },
            { revalidate: false }
          );
        };

        const computeFlushDelay = () => {
          const backlog = assistantBuffer.length;
          const total = assistantText.length + backlog;
          // 短回复/短 backlog 更快刷新，长回复略慢以减轻抖动
          if (backlog > 200 || total > 800) return 75;
          if (backlog > 120 || total > 400) return 60;
          if (backlog > 60 || total > 200) return 45;
          return 35;
        };

        const flushBuffer = (force?: boolean) => {
          if (!assistantBuffer) {
            flushTimer = null;
            return;
          }
          assistantText += assistantBuffer;
          assistantBuffer = '';
          updateAssistantContent(assistantText);
          flushTimer = null;

          // 在完成阶段可以微调节奏，让收尾更平滑
          if (!force && assistantBuffer.length === 0) {
            flushTimer = setTimeout(() => {
              flushTimer = null;
              if (assistantBuffer) {
                flushBuffer();
              }
            }, 24);
          }
        };

        const scheduleFlush = () => {
          if (flushTimer) return;
          // 优先使用 rAF，对齐帧节奏；回退到定时器
          if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
            flushTimer = window.requestAnimationFrame(() => flushBuffer());
            return;
          }
          flushTimer = setTimeout(flushBuffer, computeFlushDelay());
        };

        await globalMutate(
          messagesKey,
          async (currentData?: MessagesResponse) => {
            const assistantPlaceholder = {
              message: {
                message_id: tempAssistantMessageId,
                conversation_id: conversationId,
                role: 'assistant' as const,
                content: '',
                created_at: createdAt,
              },
              run: undefined,
              runs: undefined,
            };
            const userPlaceholder = {
              message: {
                message_id: tempUserMessageId,
                conversation_id: conversationId,
                role: 'user' as const,
                content: request.content,
                created_at: createdAt,
              },
              run: undefined,
              runs: undefined,
            };
            if (!currentData) {
              return { items: [assistantPlaceholder, userPlaceholder] } satisfies MessagesResponse;
            }
            return { ...currentData, items: [assistantPlaceholder, userPlaceholder, ...currentData.items] };
          },
          { revalidate: false }
        );

        const toRecord = (value: unknown): Record<string, unknown> | null => {
          if (!value || typeof value !== 'object') return null;
          return value as Record<string, unknown>;
        };

        const getString = (record: Record<string, unknown>, key: string) => {
          const v = record[key];
          return typeof v === 'string' ? v : '';
        };

        const parseRunSummary = (value: unknown): RunSummary | null => {
          const record = toRecord(value);
          if (!record) return null;
          const runId = getString(record, 'run_id');
          const requestedLogicalModel = getString(record, 'requested_logical_model');
          const status = getString(record, 'status');
          if (!runId || !requestedLogicalModel || !status) return null;
          const isRunStatus = (
            value: string
          ): value is RunSummary['status'] =>
            value === 'queued' ||
            value === 'running' ||
            value === 'succeeded' ||
            value === 'failed' ||
            value === 'canceled';
          if (!isRunStatus(status)) return null;

          const outputPreview =
            typeof record['output_preview'] === 'string'
              ? (record['output_preview'] as string)
              : undefined;
          const latencyMs =
            typeof record['latency_ms'] === 'number'
              ? (record['latency_ms'] as number)
              : undefined;
          const errorCode =
            typeof record['error_code'] === 'string'
              ? (record['error_code'] as string)
              : undefined;
          const toolInvocations = Array.isArray(record['tool_invocations'])
            ? (record['tool_invocations'] as RunSummary['tool_invocations'])
            : undefined;
          return {
            run_id: runId,
            requested_logical_model: requestedLogicalModel,
            status,
            output_preview: outputPreview,
            latency: latencyMs,
            error_code: errorCode,
            tool_invocations: toolInvocations,
          };
        };

        const normalizeSseEvent = (
          outer: Record<string, unknown>,
          sseEvent: string
        ): {
          type: string;
          record: Record<string, unknown>;
          outer: Record<string, unknown>;
        } | null => {
          const rawOuterType = getString(outer, 'type');
          const outerType = rawOuterType && rawOuterType !== 'message' ? rawOuterType : '';
          const fallbackEvent = typeof sseEvent === 'string' && sseEvent !== 'message' ? sseEvent : '';

          if (outerType === 'run.event') {
            const eventType = getString(outer, 'event_type') || fallbackEvent;
            const payload = toRecord(outer['payload']);
            const runId = getString(outer, 'run_id');
            if (payload) {
              const payloadType = getString(payload, 'type') || eventType;
              const payloadRunId = getString(payload, 'run_id');
              const mergedPayload =
                runId && !payloadRunId ? { ...payload, run_id: runId } : payload;
              return {
                type: payloadType,
                record: mergedPayload,
                outer,
              };
            }
            return {
              type: eventType,
              record: outer,
              outer,
            };
          }

          const type = outerType || fallbackEvent;
          if (!type) return null;
          return { type, record: outer, outer };
        };

        const streamUrl = `/v1/conversations/${conversationId}/messages`;

        const controller = new AbortController();
        const abortOnTerminal = () => {
          if (!controller.signal.aborted) controller.abort();
        };

        try {
          await streamSSERequest(
            streamUrl,
            {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                Accept: 'text/event-stream',
              },
              body: JSON.stringify({ ...payload, streaming: true }),
            },
            (msg) => {
              if (!msg.data) return;
              if (msg.data === '[DONE]') {
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
              const normalized = normalizeSseEvent(outer, msg.event);
              if (!normalized) return;
              const { type, record: rec, outer: outerRec } = normalized;
              if (!type) return;

              if (type === 'message.created') {
                const newUserId = getString(rec, 'user_message_id') || getString(outerRec, 'user_message_id');
                const newAssistantId =
                  getString(rec, 'assistant_message_id') || getString(outerRec, 'assistant_message_id');
                if (newUserId) userMessageId = newUserId;
                if (newAssistantId) assistantMessageId = newAssistantId;

                baselineRun = parseRunSummary(rec['baseline_run'] ?? outerRec['baseline_run']);

                void globalMutate(
                  messagesKey,
                  (current?: MessagesResponse) => {
                    if (!current) return current;
                    const nextItems = current.items.map((it) => {
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
                    });
                    return { ...current, items: nextItems };
                  },
                  { revalidate: false }
                );
                return;
              }

              // 兼容：若后端未来在 chat SSE 里直接透传 tool.* 事件，这里同步写入工具事件 store
              if (type === 'tool.status' || type === 'tool.result') {
                const runId = getString(rec, 'run_id') || getString(outerRec, 'run_id');
                if (!runId) return;
                useRunToolEventsStore.getState().apply_tool_event(runId, 0, rec as any);
                return;
              }

              if (type === 'message.delta') {
                const delta = getString(rec, 'delta') || getString(outerRec, 'delta');
                if (!delta) return;
                assistantBuffer += delta;
                clearPending();
                scheduleFlush();
                return;
              }

              if (type === 'message.completed' || type === 'message.failed') {
                flushBuffer(true);
                clearPending();
                const finalRun = parseRunSummary(rec['baseline_run'] ?? outerRec['baseline_run']);
                if (finalRun) baselineRun = finalRun;

                const outputText = getString(rec, 'output_text') || getString(outerRec, 'output_text');
                if (outputText) assistantText = outputText;

                void globalMutate(
                  messagesKey,
                  (current?: MessagesResponse) => {
                    if (!current) return current;
                    const nextItems = current.items.map((it) => {
                      if (it.message.message_id === assistantMessageId) {
                        return {
                          ...it,
                          message: { ...it.message, content: assistantText },
                        };
                      }
                      if (it.message.message_id === userMessageId) {
                        return { ...it, run: baselineRun ?? it.run, runs: baselineRun ? [baselineRun] : it.runs };
                      }
                      return it;
                    });
                    return { ...current, items: nextItems };
                  },
                  { revalidate: false }
                );
                abortOnTerminal();
              }
            },
            controller.signal
          );
        } catch (err) {
          if (!(err instanceof DOMException && err.name === 'AbortError')) {
            throw err;
          }
        }

        await globalMutate(messagesKey);
        if (assistantId) {
          const queryParams = new URLSearchParams();
          queryParams.set('assistant_id', assistantId);
          queryParams.set('limit', '50');
          await globalMutate(`/v1/conversations?${queryParams.toString()}`);
        }

        if (!baselineRun) {
          throw new Error('No baseline run received from stream');
        }

        return { message_id: userMessageId, baseline_run: baselineRun };
      }

      const optimisticMessage = {
        message: {
          message_id: `temp-${nonce}`,
          conversation_id: conversationId,
          role: 'user' as const,
          content: request.content,
          created_at: createdAt,
        },
        run: undefined,
        runs: undefined,
      };

      await globalMutate(
        messagesKey,
        async (currentData?: MessagesResponse) => {
          const baseItems = currentData?.items ?? [];
          return {
            ...currentData,
            items: [optimisticMessage, ...baseItems],
          };
        },
        { revalidate: false }
      );

      const response = await messageService.sendMessage(conversationId, payload);

      await globalMutate(messagesKey);

      if (assistantId) {
        const queryParams = new URLSearchParams();
        queryParams.set('assistant_id', assistantId);
        queryParams.set('limit', '50');
        await globalMutate(`/v1/conversations?${queryParams.toString()}`);
      }

      return response;
    } catch (error) {
      const standardError = ErrorHandler.normalize(error);
      const errorText = standardError.message || 'Send failed';
      
      const optimisticMessage = {
        message: {
          message_id: `temp-${nonce}`,
          conversation_id: conversationId,
          role: 'user' as const,
          content: request.content,
          created_at: createdAt,
        },
        run: undefined,
        runs: undefined,
      };
      
      const errorMessage = {
        message: {
          message_id: `error-${nonce}`,
          conversation_id: conversationId,
          role: 'assistant' as const,
          content: `[Error] ${errorText}`,
          created_at: new Date().toISOString(),
        },
        run: undefined,
        runs: undefined,
      };

      await globalMutate(
        messagesKey,
        (currentData?: MessagesResponse) => {
          const baseItems =
            currentData?.items ?? [];
          const hasUser = baseItems.some(
            (it) => it.message.message_id === `temp-${nonce}`
          );
          const itemsWithUser = hasUser
            ? baseItems
            : [optimisticMessage, ...baseItems];

          return {
            ...currentData,
            items: [errorMessage, ...itemsWithUser],
          };
        },
        { revalidate: false }
      );

      throw standardError;
    }
    finally {
      if (shouldShowPendingLoader) {
        markPending(false);
      }
    }
  };
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * 清空会话消息历史（保留会话本身）
 *
 * - 删除该会话下所有分页缓存
 * - 重新验证当前会话消息与会话列表
 */
export function useClearConversationMessages(assistantId?: string | null) {
  const { mutate: globalMutate, cache } = useSWRConfig();
  const cacheManager = useMemo(() => new SWRCacheManager(cache), [cache]);

  return async (conversationId: string) => {
    if (!conversationId) throw new Error('Conversation ID is required');

    const pattern = new RegExp(`^/v1/conversations/${escapeRegExp(conversationId)}/messages`);
    const messageKeys = cacheManager.getKeysByPattern(pattern);
    await Promise.all(
      messageKeys.map((key) =>
        globalMutate(
          key,
          {
            items: [],
            next_cursor: undefined,
          } satisfies MessagesResponse,
          { revalidate: false }
        )
      )
    );

    try {
      await messageService.clearConversationMessages(conversationId);
    } finally {
      await globalMutate(`/v1/conversations/${conversationId}/messages?limit=50`);
      if (assistantId) {
        const queryParams = new URLSearchParams();
        queryParams.set('assistant_id', assistantId);
        queryParams.set('limit', '50');
        await globalMutate(`/v1/conversations?${queryParams.toString()}`);
      }
    }
  };
}
