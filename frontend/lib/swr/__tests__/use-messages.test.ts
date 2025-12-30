import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createElement } from 'react';
import { SWRConfig } from 'swr';
import {
  useClearConversationMessages,
  useMessages,
  useRun,
  useSendMessage,
  useSendMessageToConversation,
} from '../use-messages';
import { messageService } from '@/http/message';
import { streamSSERequest } from '@/lib/bridge/sse';
import type { MessagesResponse, RunDetail } from '@/lib/api-types';

const mockUseBridgeAgents = vi.fn(() => ({
  agents: [],
  error: null,
  loading: false,
  refresh: vi.fn(),
}));

const resetBridgeAgentsMock = () =>
  mockUseBridgeAgents.mockReturnValue({
    agents: [],
    error: null,
    loading: false,
    refresh: vi.fn(),
  });

// Mock messageService
vi.mock('@/http/message', () => ({
  messageService: {
    getMessages: vi.fn(),
    getRun: vi.fn(),
    sendMessage: vi.fn(),
    clearConversationMessages: vi.fn(),
  },
}));

vi.mock('@/lib/bridge/sse', () => ({
  streamSSERequest: vi.fn(),
}));

vi.mock('@/lib/swr/use-bridge', () => ({
  useBridgeAgents: () => mockUseBridgeAgents(),
}));

vi.mock('@/lib/hooks/use-conversation-pending', () => ({
  useConversationPending: () => ({ setPending: vi.fn() }),
}));

// Mock SWR provider wrapper
const wrapper = ({ children }: { children: React.ReactNode }) => children;

const swrWrapper = ({ children }: { children: React.ReactNode }) => (
  createElement(SWRConfig, { value: { provider: () => new Map(), dedupingInterval: 0 } }, children)
);

describe('useMessages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetBridgeAgentsMock();
  });

  it('should fetch messages with pagination support', async () => {
    const mockResponse: MessagesResponse = {
      items: [
        {
          message: {
            message_id: 'msg-1',
            conversation_id: 'conv-1',
            role: 'user',
            content: 'Hello',
            created_at: '2024-01-01T00:00:00Z',
          },
        },
      ],
      next_cursor: 'cursor-1',
    };

    vi.mocked(messageService.getMessages).mockResolvedValue(mockResponse);

    const { result } = renderHook(
      () => useMessages('conv-1', { limit: 10 }),
      { wrapper }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.messages).toEqual(mockResponse.items);
    expect(result.current.nextCursor).toBe('cursor-1');
    expect(messageService.getMessages).toHaveBeenCalledWith('conv-1', { limit: 10 });
  });

  it('should not fetch when conversationId is null', () => {
    const { result } = renderHook(() => useMessages(null), { wrapper });

    expect(result.current.messages).toEqual([]);
    expect(messageService.getMessages).not.toHaveBeenCalled();
  });

  it('should handle errors', async () => {
    const error = new Error('Failed to fetch messages');
    vi.mocked(messageService.getMessages).mockRejectedValue(error);

    const { result } = renderHook(() => useMessages('conv-1'), { wrapper });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBe(error);
  });
});

describe('useRun', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetBridgeAgentsMock();
  });

  it('should fetch run details lazily', async () => {
    const mockRun: RunDetail = {
      run_id: 'run-1',
      requested_logical_model: 'gpt-4',
      status: 'succeeded',
      output_preview: 'Hello!',
      latency: 1000,
      request: { messages: [] },
      response: { choices: [] },
      output_text: 'Hello!',
      input_tokens: 10,
      output_tokens: 5,
      total_tokens: 15,
      cost: 0.001,
    };

    vi.mocked(messageService.getRun).mockResolvedValue(mockRun);

    const { result } = renderHook(() => useRun('run-1'), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.run).toEqual(mockRun);
    expect(messageService.getRun).toHaveBeenCalledWith('run-1');
  });

  it('should not fetch when runId is null', () => {
    const { result } = renderHook(() => useRun(null), { wrapper });

    expect(result.current.run).toBeUndefined();
    expect(messageService.getRun).not.toHaveBeenCalled();
  });
});

describe('useSendMessage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetBridgeAgentsMock();
  });

  it('should send message and return response', async () => {
    vi.mocked(streamSSERequest).mockImplementation(async (_url, _init, onMessage) => {
      onMessage({
        event: 'message.created',
        data: JSON.stringify({
          type: 'message.created',
          user_message_id: 'msg-user-1',
          assistant_message_id: 'msg-assistant-1',
          baseline_run: { run_id: 'run-1', requested_logical_model: 'gpt-4', status: 'running' },
        }),
      });
      onMessage({
        event: 'message.completed',
        data: JSON.stringify({
          type: 'message.completed',
          output_text: 'Hi there!',
          baseline_run: {
            run_id: 'run-1',
            requested_logical_model: 'gpt-4',
            status: 'succeeded',
            output_preview: 'Hi there!',
            latency_ms: 1200,
          },
        }),
      });
      onMessage({ event: 'done', data: '[DONE]' });
    });

    const { result } = renderHook(() => useSendMessage('conv-1'), { wrapper: swrWrapper });

    const response = await result.current({ content: 'Hello' });

    expect(response.message_id).toBe('msg-user-1');
    expect(response.baseline_run.status).toBe('succeeded');
    expect(streamSSERequest).toHaveBeenCalled();
  });

  it('should pass override_logical_model when provided', async () => {
    vi.mocked(streamSSERequest).mockImplementation(async (_url, init, onMessage) => {
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : {};
      expect(body.override_logical_model).toBe('test-model');

      onMessage({
        event: 'message.completed',
        data: JSON.stringify({
          type: 'message.completed',
          output_text: 'ok',
          baseline_run: {
            run_id: 'run-1',
            requested_logical_model: 'gpt-4',
            status: 'succeeded',
            output_preview: 'ok',
          },
        }),
      });
      onMessage({ event: 'done', data: '[DONE]' });
    });

    const { result } = renderHook(
      () => useSendMessage('conv-1', undefined, 'test-model'),
      { wrapper: swrWrapper }
    );

    await result.current({ content: 'Hello' });
    expect(streamSSERequest).toHaveBeenCalled();
  });

  it('should throw error when conversationId is null', async () => {
    const { result } = renderHook(() => useSendMessage(null), { wrapper });

    await expect(result.current({ content: 'Hello' })).rejects.toThrow(
      'Conversation ID is required'
    );
  });

  it('should handle send errors', async () => {
    const error = new Error('Failed to send message');
    vi.mocked(streamSSERequest).mockRejectedValue(error);

    const { result } = renderHook(() => useSendMessage('conv-1'), { wrapper });

    await expect(result.current({ content: 'Hello' })).rejects.toThrow(
      'Failed to send message'
    );
  });

  it('should handle run.event enveloped streaming events', async () => {
    vi.mocked(streamSSERequest).mockImplementation(
      async (_url, _init, onMessage, _signal) => {
        onMessage({
          event: 'message.created',
          data: JSON.stringify({
            type: 'run.event',
            run_id: 'run-1',
            seq: 1,
            event_type: 'message.created',
            payload: {
              type: 'message.created',
              user_message_id: 'msg-user-1',
              assistant_message_id: 'msg-assistant-1',
              baseline_run: {
                run_id: 'run-1',
                requested_logical_model: 'gpt-4',
                status: 'running',
              },
            },
          }),
        });

        onMessage({
          event: 'message.delta',
          data: JSON.stringify({
            type: 'run.event',
            run_id: 'run-1',
            seq: 2,
            event_type: 'message.delta',
            payload: { type: 'message.delta', delta: 'hi' },
          }),
        });

        onMessage({
          event: 'message.completed',
          data: JSON.stringify({
            type: 'run.event',
            run_id: 'run-1',
            seq: 3,
            event_type: 'message.completed',
            payload: {
              type: 'message.completed',
              output_text: 'hi',
              baseline_run: {
                run_id: 'run-1',
                requested_logical_model: 'gpt-4',
                status: 'succeeded',
                output_preview: 'hi',
              },
            },
          }),
        });
      }
    );

    const { result } = renderHook(() => useSendMessage('conv-1'), { wrapper: swrWrapper });

    const response = await result.current({ content: 'Hello' });

    expect(response.baseline_run.status).toBe('succeeded');
    expect(streamSSERequest).toHaveBeenCalled();
  });
});

describe('useSendMessageToConversation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetBridgeAgentsMock();
  });

  it('should send message with provided conversationId', async () => {
    vi.mocked(streamSSERequest).mockImplementation(async (_url, init, onMessage) => {
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : {};
      expect(body.content).toBe('Hello');
      expect(body.streaming).toBe(true);

      onMessage({
        event: 'message.completed',
        data: JSON.stringify({
          type: 'message.completed',
          output_text: 'Hi there!',
          baseline_run: {
            run_id: 'run-2',
            requested_logical_model: 'gpt-4',
            status: 'succeeded',
            output_preview: 'Hi there!',
          },
        }),
      });
      onMessage({ event: 'done', data: '[DONE]' });
    });

    const { result } = renderHook(() => useSendMessageToConversation(), { wrapper: swrWrapper });

    const response = await result.current('conv-1', { content: 'Hello' });

    expect(response.baseline_run.status).toBe('succeeded');
    expect(streamSSERequest).toHaveBeenCalled();
  });

  it('should pass override_logical_model when provided', async () => {
    vi.mocked(streamSSERequest).mockImplementation(async (_url, init, onMessage) => {
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : {};
      expect(body.override_logical_model).toBe('test-model');

      onMessage({
        event: 'message.completed',
        data: JSON.stringify({
          type: 'message.completed',
          output_text: 'ok',
          baseline_run: {
            run_id: 'run-2',
            requested_logical_model: 'gpt-4',
            status: 'succeeded',
            output_preview: 'ok',
          },
        }),
      });
      onMessage({ event: 'done', data: '[DONE]' });
    });

    const { result } = renderHook(
      () => useSendMessageToConversation(undefined, 'test-model'),
      { wrapper: swrWrapper }
    );

    await result.current('conv-1', { content: 'Hello' });
    expect(streamSSERequest).toHaveBeenCalled();
  });

  it('should drop bridge payload when no bridge agents are available', async () => {
    mockUseBridgeAgents.mockReturnValue({
      agents: [],
      error: null,
      loading: false,
      refresh: vi.fn(),
    });
    vi.mocked(streamSSERequest).mockImplementation(async (_url, init, onMessage) => {
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : {};
      expect(body.bridge_agent_ids).toBeUndefined();
      expect(body.bridge_tool_selections).toBeUndefined();

      onMessage({
        event: 'message.completed',
        data: JSON.stringify({
          type: 'message.completed',
          output_text: 'ok',
          baseline_run: { run_id: 'run-3', requested_logical_model: 'gpt-4', status: 'succeeded' },
        }),
      });
      onMessage({ event: 'done', data: '[DONE]' });
    });

    const { result } = renderHook(() => useSendMessageToConversation(), { wrapper: swrWrapper });

    await result.current('conv-1', {
      content: 'Hello',
      bridge_agent_ids: ['agent-1'],
      bridge_tool_selections: [{ agent_id: 'agent-1', tool_names: ['search'] }],
    });
    expect(streamSSERequest).toHaveBeenCalled();
  });

  it('should keep bridge payload when bridge agents are available', async () => {
    mockUseBridgeAgents.mockReturnValue({
      agents: [{ agent_id: 'agent-1' }],
      error: null,
      loading: false,
      refresh: vi.fn(),
    });
    vi.mocked(streamSSERequest).mockImplementation(async (_url, init, onMessage) => {
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : {};
      expect(body.bridge_agent_ids).toEqual(['agent-1']);
      expect(body.bridge_tool_selections).toEqual([{ agent_id: 'agent-1', tool_names: ['search'] }]);

      onMessage({
        event: 'message.completed',
        data: JSON.stringify({
          type: 'message.completed',
          output_text: 'ok',
          baseline_run: { run_id: 'run-4', requested_logical_model: 'gpt-4', status: 'succeeded' },
        }),
      });
      onMessage({ event: 'done', data: '[DONE]' });
    });

    const { result } = renderHook(() => useSendMessageToConversation(), { wrapper: swrWrapper });

    const payload = {
      content: 'Hello',
      bridge_agent_ids: ['agent-1'],
      bridge_tool_selections: [{ agent_id: 'agent-1', tool_names: ['search'] }],
    };

    await result.current('conv-1', payload);
    expect(streamSSERequest).toHaveBeenCalled();
  });
});

describe('useClearConversationMessages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetBridgeAgentsMock();
  });

  it('should clear messages and keep conversation id', async () => {
    vi.mocked(messageService.clearConversationMessages).mockResolvedValue(undefined);

    const { result } = renderHook(
      () => useClearConversationMessages('assistant-1'),
      { wrapper }
    );

    await result.current('conv-1');

    expect(messageService.clearConversationMessages).toHaveBeenCalledWith('conv-1');
  });
});
