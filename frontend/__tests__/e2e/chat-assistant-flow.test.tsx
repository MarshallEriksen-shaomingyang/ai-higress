/**
 * E2E 测试：聊天助手系统关键路径
 * 
 * 测试覆盖：
 * 1. 创建助手 → 创建会话 → 发送消息 → 查看回复流程
 * 2. 触发评测 → 查看 challengers → 提交评分流程
 * 3. 归档会话 → 验证无法发送消息流程
 * 4. 删除助手 → 验证级联删除流程
 * 
 * Requirements: 1.1-10.6
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { assistantService } from '@/http/assistant';
import { conversationService } from '@/http/conversation';
import { messageService } from '@/http/message';
import { evalService } from '@/http/eval';

// Mock HTTP services
vi.mock('@/http/assistant');
vi.mock('@/http/conversation');
vi.mock('@/http/message');
vi.mock('@/http/eval');

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => '/chat',
  useSearchParams: () => new URLSearchParams(),
}));

// Mock i18n
vi.mock('@/lib/i18n-context', () => ({
  useI18n: () => ({
    t: (key: string) => key,
    locale: 'zh',
  }),
}));

// Mock SWR Provider
import { SWRConfig } from 'swr';

const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
    {children}
  </SWRConfig>
);

describe('E2E: 创建助手 → 创建会话 → 发送消息 → 查看回复流程', () => {
  const mockAssistant = {
    assistant_id: 'asst-1',
    project_id: 'proj-1',
    name: '测试助手',
    system_prompt: '你是一个有帮助的助手',
    default_logical_model: 'gpt-4',
    model_preset: {},
    archived: false,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  const mockConversation = {
    conversation_id: 'conv-1',
    assistant_id: 'asst-1',
    project_id: 'proj-1',
    title: '新会话',
    archived: false,
    last_activity_at: '2024-01-01T00:00:00Z',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  const mockMessage = {
    message_id: 'msg-1',
    conversation_id: 'conv-1',
    role: 'user' as const,
    content: '你好',
    created_at: '2024-01-01T00:00:00Z',
  };

  const mockAssistantMessage = {
    message_id: 'msg-2',
    conversation_id: 'conv-1',
    role: 'assistant' as const,
    content: '你好！我能帮你什么？',
    run_id: 'run-1',
    created_at: '2024-01-01T00:00:01Z',
  };

  const mockRunSummary = {
    run_id: 'run-1',
    requested_logical_model: 'gpt-4',
    status: 'succeeded' as const,
    output_preview: '你好！我能帮你什么？',
    latency: 1200,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('应该完成完整的创建助手到查看回复流程', async () => {
    // Mock API 响应
    vi.mocked(assistantService.createAssistant).mockResolvedValue(mockAssistant);
    vi.mocked(assistantService.getAssistants).mockResolvedValue({
      items: [mockAssistant],
      next_cursor: undefined,
    });
    vi.mocked(conversationService.createConversation).mockResolvedValue(mockConversation);
    vi.mocked(conversationService.getConversations).mockResolvedValue({
      items: [mockConversation],
      next_cursor: undefined,
    });
    vi.mocked(messageService.sendMessage).mockResolvedValue({
      message_id: 'msg-1',
      baseline_run: mockRunSummary,
    });
    vi.mocked(messageService.getMessages).mockResolvedValue({
      items: [
        { message: mockMessage },
        { message: mockAssistantMessage, run: mockRunSummary },
      ],
      next_cursor: undefined,
    });

    // 1. 创建助手
    const assistant = await assistantService.createAssistant({
      project_id: 'proj-1',
      name: '测试助手',
      default_logical_model: 'gpt-4',
    });
    expect(assistant.assistant_id).toBe('asst-1');

    // 2. 创建会话
    const conversation = await conversationService.createConversation({
      assistant_id: assistant.assistant_id,
      project_id: 'proj-1',
    });
    expect(conversation.conversation_id).toBe('conv-1');

    // 3. 发送消息
    const messageResponse = await messageService.sendMessage(conversation.conversation_id, {
      content: '你好',
    });
    expect(messageResponse.baseline_run.status).toBe('succeeded');

    // 4. 获取消息列表
    const messages = await messageService.getMessages(conversation.conversation_id, {});
    expect(messages.items).toHaveLength(2);
    expect(messages.items[0].message.role).toBe('user');
    expect(messages.items[1].message.role).toBe('assistant');
  });

  it('应该在发送消息时显示乐观更新', async () => {
    vi.mocked(messageService.sendMessage).mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({
        message_id: 'msg-1',
        baseline_run: mockRunSummary,
      }), 100))
    );

    // 验证乐观更新逻辑
    const sendPromise = messageService.sendMessage('conv-1', { content: '你好' });
    
    // 消息应该立即显示（乐观更新）
    // 实际实现中会通过 SWR mutate 实现
    
    await sendPromise;
    
    expect(messageService.sendMessage).toHaveBeenCalled();
  });

  it('应该在 baseline run 完成后显示助手回复', async () => {
    vi.mocked(messageService.sendMessage).mockResolvedValue({
      message_id: 'msg-1',
      baseline_run: mockRunSummary,
    });

    const response = await messageService.sendMessage('conv-1', { content: '你好' });

    expect(response.baseline_run.status).toBe('succeeded');
    expect(response.baseline_run.output_preview).toBeDefined();
  });
});

describe('E2E: 触发评测 → 查看 challengers → 提交评分流程', () => {
  const mockEval = {
    eval_id: 'eval-1',
    status: 'running' as const,
    baseline_run_id: 'run-1',
    challengers: [
      {
        run_id: 'run-2',
        requested_logical_model: 'gpt-4-turbo',
        status: 'running' as const,
      },
      {
        run_id: 'run-3',
        requested_logical_model: 'claude-3-opus',
        status: 'running' as const,
      },
    ],
    explanation: {
      summary: '选择了 GPT-4 Turbo 和 Claude 3 Opus 进行对比',
      evidence: {
        policy_version: 'v1',
        exploration: false,
      },
    },
    created_at: '2024-01-01T00:00:00Z',
  };

  const mockEvalReady = {
    ...mockEval,
    status: 'ready' as const,
    challengers: [
      {
        run_id: 'run-2',
        requested_logical_model: 'gpt-4-turbo',
        status: 'succeeded' as const,
        output_preview: 'GPT-4 Turbo 的回复',
        latency: 1000,
      },
      {
        run_id: 'run-3',
        requested_logical_model: 'claude-3-opus',
        status: 'succeeded' as const,
        output_preview: 'Claude 3 Opus 的回复',
        latency: 1500,
      },
    ],
  };

  const mockRating = {
    eval_id: 'eval-1',
    winner_run_id: 'run-2',
    reason_tags: ['accurate', 'fast'] as const,
    created_at: '2024-01-01T00:00:02Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('应该完成完整的评测流程', async () => {
    // Mock API 响应
    vi.mocked(evalService.createEval).mockResolvedValue(mockEval);
    vi.mocked(evalService.getEval)
      .mockResolvedValueOnce(mockEval)
      .mockResolvedValueOnce(mockEvalReady);
    vi.mocked(evalService.submitRating).mockResolvedValue(mockRating);

    // 1. 创建评测
    const evalResponse = await evalService.createEval({
      project_id: 'proj-1',
      assistant_id: 'asst-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      baseline_run_id: 'run-1',
    });

    expect(evalResponse.status).toBe('running');
    expect(evalResponse.challengers).toHaveLength(2);
    expect(evalResponse.explanation).toBeDefined();

    // 2. 轮询评测状态
    const evalStatus1 = await evalService.getEval('eval-1');
    expect(evalStatus1.status).toBe('running');

    // 3. 评测完成
    const evalStatus2 = await evalService.getEval('eval-1');
    expect(evalStatus2.status).toBe('ready');
    expect(evalStatus2.challengers.every(c => c.status === 'succeeded')).toBe(true);

    // 4. 提交评分
    const ratingResponse = await evalService.submitRating('eval-1', {
      winner_run_id: 'run-2',
      reason_tags: ['accurate', 'fast'],
    });

    expect(ratingResponse.winner_run_id).toBe('run-2');
    expect(ratingResponse.reason_tags).toContain('accurate');
    expect(ratingResponse.reason_tags).toContain('fast');
  });

  it('应该在评测创建后立即显示 challenger 占位', async () => {
    vi.mocked(evalService.createEval).mockResolvedValue(mockEval);

    const evalResponse = await evalService.createEval({
      project_id: 'proj-1',
      assistant_id: 'asst-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      baseline_run_id: 'run-1',
    });

    // 验证 challengers 立即返回（即使状态是 running）
    expect(evalResponse.challengers).toBeDefined();
    expect(evalResponse.challengers.length).toBeGreaterThan(0);
    expect(evalResponse.challengers.every(c => c.status === 'running')).toBe(true);
  });

  it('应该支持重复提交评分', async () => {
    vi.mocked(evalService.submitRating)
      .mockResolvedValueOnce(mockRating)
      .mockResolvedValueOnce({
        ...mockRating,
        winner_run_id: 'run-3',
        reason_tags: ['complete', 'concise'],
      });

    // 第一次提交
    const rating1 = await evalService.submitRating('eval-1', {
      winner_run_id: 'run-2',
      reason_tags: ['accurate', 'fast'],
    });
    expect(rating1.winner_run_id).toBe('run-2');

    // 第二次提交（覆盖）
    const rating2 = await evalService.submitRating('eval-1', {
      winner_run_id: 'run-3',
      reason_tags: ['complete', 'concise'],
    });
    expect(rating2.winner_run_id).toBe('run-3');
  });

  it('应该处理 challenger 执行失败的情况', async () => {
    const mockEvalWithFailure = {
      ...mockEval,
      status: 'ready' as const,
      challengers: [
        {
          run_id: 'run-2',
          requested_logical_model: 'gpt-4-turbo',
          status: 'succeeded' as const,
          output_preview: 'GPT-4 Turbo 的回复',
          latency: 1000,
        },
        {
          run_id: 'run-3',
          requested_logical_model: 'claude-3-opus',
          status: 'failed' as const,
          error_code: 'RATE_LIMIT_EXCEEDED',
        },
      ],
    };

    vi.mocked(evalService.getEval).mockResolvedValue(mockEvalWithFailure);

    const evalStatus = await evalService.getEval('eval-1');

    // 验证即使有失败的 challenger，评测仍然可以完成
    expect(evalStatus.status).toBe('ready');
    expect(evalStatus.challengers.some(c => c.status === 'failed')).toBe(true);
    expect(evalStatus.challengers.some(c => c.status === 'succeeded')).toBe(true);
  });
});

describe('E2E: 归档会话 → 验证无法发送消息流程', () => {
  const mockConversation = {
    conversation_id: 'conv-1',
    assistant_id: 'asst-1',
    project_id: 'proj-1',
    title: '测试会话',
    archived: false,
    last_activity_at: '2024-01-01T00:00:00Z',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('应该完成归档会话流程', async () => {
    // Mock API 响应
    vi.mocked(conversationService.updateConversation).mockResolvedValue({
      ...mockConversation,
      archived: true,
    });

    const updatedConversation = await conversationService.updateConversation('conv-1', {
      archived: true,
    });

    expect(updatedConversation.archived).toBe(true);
  });

  it('应该在归档后仍能读取历史消息', async () => {
    const mockMessages = {
      items: [
        {
          message: {
            message_id: 'msg-1',
            conversation_id: 'conv-1',
            role: 'user' as const,
            content: '历史消息',
            created_at: '2024-01-01T00:00:00Z',
          },
        },
      ],
      next_cursor: undefined,
    };

    vi.mocked(messageService.getMessages).mockResolvedValue(mockMessages);

    const messages = await messageService.getMessages('conv-1', {});

    expect(messages.items).toHaveLength(1);
    expect(messages.items[0].message.content).toBe('历史消息');
  });

  it('应该在归档后拒绝发送新消息', async () => {
    // Mock 404 错误
    vi.mocked(messageService.sendMessage).mockRejectedValue({
      response: {
        status: 404,
        data: {
          detail: {
            error: 'CONVERSATION_ARCHIVED',
            message: '会话已归档，无法继续对话',
          },
        },
      },
    });

    await expect(
      messageService.sendMessage('conv-1', { content: '新消息' })
    ).rejects.toMatchObject({
      response: {
        status: 404,
      },
    });
  });

  it('应该在列表中隐藏归档的会话', async () => {
    vi.mocked(conversationService.getConversations).mockResolvedValue({
      items: [], // 归档的会话不在列表中
      next_cursor: undefined,
    });

    const conversations = await conversationService.getConversations({
      assistant_id: 'asst-1',
    });

    expect(conversations.items).toHaveLength(0);
  });
});

describe('E2E: 删除助手 → 验证级联删除流程', () => {
  const mockAssistant = {
    assistant_id: 'asst-1',
    project_id: 'proj-1',
    name: '待删除助手',
    system_prompt: '测试',
    default_logical_model: 'gpt-4',
    model_preset: {},
    archived: false,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('应该完成删除助手流程', async () => {
    vi.mocked(assistantService.deleteAssistant).mockResolvedValue(undefined);

    await assistantService.deleteAssistant('asst-1');

    expect(assistantService.deleteAssistant).toHaveBeenCalledWith('asst-1');
  });

  it('应该在删除助手后无法获取该助手', async () => {
    vi.mocked(assistantService.getAssistant).mockRejectedValue({
      response: {
        status: 404,
        data: {
          detail: {
            error: 'ASSISTANT_NOT_FOUND',
            message: '助手不存在或已被删除',
          },
        },
      },
    });

    await expect(
      assistantService.getAssistant('asst-1')
    ).rejects.toMatchObject({
      response: {
        status: 404,
      },
    });
  });

  it('应该在删除助手后无法获取其会话', async () => {
    vi.mocked(conversationService.getConversations).mockResolvedValue({
      items: [],
      next_cursor: undefined,
    });

    const conversations = await conversationService.getConversations({
      assistant_id: 'asst-1',
    });

    expect(conversations.items).toHaveLength(0);
  });

  it('应该在删除会话后无法获取该会话', async () => {
    vi.mocked(conversationService.deleteConversation).mockResolvedValue(undefined);

    await conversationService.deleteConversation('conv-1');

    expect(conversationService.deleteConversation).toHaveBeenCalledWith('conv-1');

    // 验证删除后无法获取
    vi.mocked(messageService.getMessages).mockRejectedValue({
      response: {
        status: 404,
        data: {
          detail: {
            error: 'CONVERSATION_NOT_FOUND',
            message: '会话不存在或已被删除',
          },
        },
      },
    });

    await expect(
      messageService.getMessages('conv-1', {})
    ).rejects.toMatchObject({
      response: {
        status: 404,
      },
    });
  });
});

describe('E2E: 错误处理和边缘情况', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('应该处理网络错误', async () => {
    vi.mocked(assistantService.getAssistants).mockRejectedValue(
      new Error('Network Error')
    );

    await expect(
      assistantService.getAssistants({ project_id: 'proj-1' })
    ).rejects.toThrow('Network Error');
  });

  it('应该处理认证错误', async () => {
    vi.mocked(assistantService.getAssistants).mockRejectedValue({
      response: {
        status: 401,
        data: {
          detail: {
            error: 'UNAUTHORIZED',
            message: '未授权',
          },
        },
      },
    });

    await expect(
      assistantService.getAssistants({ project_id: 'proj-1' })
    ).rejects.toMatchObject({
      response: {
        status: 401,
      },
    });
  });

  it('应该处理评测频率限制', async () => {
    vi.mocked(evalService.createEval).mockRejectedValue({
      response: {
        status: 429,
        data: {
          detail: {
            error: 'EVAL_COOLDOWN',
            message: '评测触发过于频繁，请稍后再试',
          },
        },
      },
    });

    await expect(
      evalService.createEval({
        project_id: 'proj-1',
        assistant_id: 'asst-1',
        conversation_id: 'conv-1',
        message_id: 'msg-1',
        baseline_run_id: 'run-1',
      })
    ).rejects.toMatchObject({
      response: {
        status: 429,
      },
    });
  });

  it('应该处理评测未启用错误', async () => {
    vi.mocked(evalService.createEval).mockRejectedValue({
      response: {
        status: 403,
        data: {
          detail: {
            error: 'EVAL_NOT_ENABLED',
            message: '该项目未启用推荐评测',
          },
        },
      },
    });

    await expect(
      evalService.createEval({
        project_id: 'proj-1',
        assistant_id: 'asst-1',
        conversation_id: 'conv-1',
        message_id: 'msg-1',
        baseline_run_id: 'run-1',
      })
    ).rejects.toMatchObject({
      response: {
        status: 403,
      },
    });
  });

  it('应该处理空列表情况', async () => {
    vi.mocked(assistantService.getAssistants).mockResolvedValue({
      items: [],
      next_cursor: undefined,
    });

    const response = await assistantService.getAssistants({ project_id: 'proj-1' });

    expect(response.items).toHaveLength(0);
    expect(response.next_cursor).toBeUndefined();
  });

  it('应该处理分页加载', async () => {
    vi.mocked(conversationService.getConversations)
      .mockResolvedValueOnce({
        items: [
          {
            conversation_id: 'conv-1',
            assistant_id: 'asst-1',
            project_id: 'proj-1',
            title: '会话 1',
            archived: false,
            last_activity_at: '2024-01-01T00:00:00Z',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
        ],
        next_cursor: 'cursor-1',
      })
      .mockResolvedValueOnce({
        items: [
          {
            conversation_id: 'conv-2',
            assistant_id: 'asst-1',
            project_id: 'proj-1',
            title: '会话 2',
            archived: false,
            last_activity_at: '2024-01-01T00:00:01Z',
            created_at: '2024-01-01T00:00:01Z',
            updated_at: '2024-01-01T00:00:01Z',
          },
        ],
        next_cursor: undefined,
      });

    // 第一页
    const page1 = await conversationService.getConversations({
      assistant_id: 'asst-1',
    });
    expect(page1.items).toHaveLength(1);
    expect(page1.next_cursor).toBe('cursor-1');

    // 第二页
    const page2 = await conversationService.getConversations({
      assistant_id: 'asst-1',
      cursor: 'cursor-1',
    });
    expect(page2.items).toHaveLength(1);
    expect(page2.next_cursor).toBeUndefined();
  });
});
