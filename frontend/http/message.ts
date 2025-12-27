import { httpClient } from './client';
import type {
  SendMessageRequest,
  SendMessageResponse,
  GetMessagesParams,
  MessagesResponse,
  RunDetail,
  RegenerateMessageResponse,
  RegenerateMessageRequest,
} from '@/lib/api-types';
import {
  normalizeMessagesResponse,
  normalizeSendMessageResponse,
  normalizeRunDetail,
  type MessagesResponseBackend,
  type SendMessageResponseBackend,
  type RunDetailBackend,
} from '@/lib/normalizers/chat-normalizers';
import { SEND_MESSAGE_TIMEOUT_MS, RUN_DETAIL_TIMEOUT_MS } from '@/config/timeouts';

/**
 * 消息和 Run 管理服务
 */
export const messageService = {
  /**
   * 获取会话的消息列表（分页）
   */
  getMessages: async (
    conversationId: string,
    params?: GetMessagesParams
  ): Promise<MessagesResponse> => {
    const { data } = await httpClient.get<MessagesResponseBackend>(`/v1/conversations/${conversationId}/messages`, {
      params,
    });
    return normalizeMessagesResponse(data, conversationId);
  },

  /**
   * 发送消息（同步执行 baseline run）
   */
  sendMessage: async (
    conversationId: string,
    request: SendMessageRequest
  ): Promise<SendMessageResponse> => {
    const { data } = await httpClient.post<SendMessageResponseBackend>(
      `/v1/conversations/${conversationId}/messages`,
      request,
      { timeout: SEND_MESSAGE_TIMEOUT_MS }
    );
    return normalizeSendMessageResponse(data);
  },

  /**
   * 清空会话消息历史（保留会话本身）
   */
  clearConversationMessages: async (conversationId: string): Promise<void> => {
    await httpClient.delete(`/v1/conversations/${conversationId}/messages`);
  },

  /**
   * 重新生成助手消息
   */
  regenerateMessage: async (
    assistantMessageId: string,
    request?: RegenerateMessageRequest
  ): Promise<RegenerateMessageResponse> => {
    // 复用较长超时，避免大模型重新生成时被前端 10s 默认超时打断
    const { data } = await httpClient.post<RegenerateMessageResponse>(
      `/v1/messages/${assistantMessageId}/regenerate`,
      request,
      { timeout: SEND_MESSAGE_TIMEOUT_MS }
    );
    return data;
  },

  /**
   * 删除单条消息
   */
  deleteMessage: async (messageId: string): Promise<void> => {
    await httpClient.delete(`/v1/messages/${messageId}`);
  },

  /**
   * 获取 Run 详情（惰性加载完整数据）
   */
  getRun: async (runId: string): Promise<RunDetail> => {
    const { data } = await httpClient.get<RunDetailBackend>(`/v1/runs/${runId}`, {
      timeout: RUN_DETAIL_TIMEOUT_MS,
    });
    return normalizeRunDetail(data);
  },
};
