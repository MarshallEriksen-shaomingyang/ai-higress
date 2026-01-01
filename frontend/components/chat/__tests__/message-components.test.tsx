import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MessageItem } from '../message-item';
import type { Message, RunSummary } from '@/lib/api-types';
import type { ComparisonVariant } from '@/lib/stores/chat-comparison-store';
import { useUserPreferencesStore } from '@/lib/stores/user-preferences-store';

// Mock i18n
vi.mock('@/lib/i18n-context', () => ({
  useI18n: () => ({
    t: (key: string) => key,
    language: 'zh',
  }),
}));

describe('MessageItem', () => {
  beforeEach(() => {
    localStorage.clear();
    useUserPreferencesStore.getState().resetPreferences();
  });

  const mockUserMessage: Message = {
    message_id: 'msg-1',
    conversation_id: 'conv-1',
    role: 'user',
    content: 'Hello, assistant!',
    created_at: new Date().toISOString(),
  };

  const mockAssistantMessage: Message = {
    message_id: 'msg-2',
    conversation_id: 'conv-1',
    role: 'assistant',
    content: 'Hello! How can I help you?',
    run_id: 'run-1',
    created_at: new Date().toISOString(),
  };

  const mockRun: RunSummary = {
    run_id: 'run-1',
    requested_logical_model: 'gpt-4',
    status: 'succeeded',
    output_preview: 'Hello! How can I help you?',
    latency: 1500,
  };

  it('renders user message correctly', () => {
    render(<MessageItem message={mockUserMessage} />);
    expect(screen.getByText('Hello, assistant!')).toBeInTheDocument();
  });

  it('renders assistant message with run summary', () => {
    render(<MessageItem message={mockAssistantMessage} runs={[mockRun]} />);
    expect(screen.getByText('Hello! How can I help you?')).toBeInTheDocument();
    expect(screen.getByText('gpt-4')).toBeInTheDocument();
    expect(screen.getByText('1500ms')).toBeInTheDocument();
  });

  it('does not show TTS control when project TTS model is not configured', () => {
    render(
      <MessageItem
        message={mockAssistantMessage}
        runs={[mockRun]}
        projectId="proj-1"
      />
    );
    expect(screen.queryByLabelText('chat.tts.play')).not.toBeInTheDocument();
  });

  it('shows TTS control when project TTS model is configured', () => {
    useUserPreferencesStore.getState().setPreferredTtsModel('proj-1', 'tts-model-1');

    render(
      <MessageItem
        message={mockAssistantMessage}
        runs={[mockRun]}
        projectId="proj-1"
      />
    );
    expect(screen.getByLabelText('chat.tts.play')).toBeInTheDocument();
  });

  it('shows status badge for assistant message', () => {
    render(<MessageItem message={mockAssistantMessage} runs={[mockRun]} />);
    expect(screen.getByText('chat.run.status_succeeded')).toBeInTheDocument();
  });

  it('does not show running indicator after run succeeded (even if recent/typewriter enabled)', () => {
    render(
      <MessageItem
        message={mockAssistantMessage}
        runs={[mockRun]}
        enableTypewriter
        isLatestAssistant
      />
    );
    expect(screen.queryByText('chat.run.status_running')).not.toBeInTheDocument();
  });

  it('shows running indicator for recent assistant placeholder without run status and empty content', () => {
    const placeholderAssistant: Message = {
      message_id: 'msg-5',
      conversation_id: 'conv-1',
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    };
    render(<MessageItem message={placeholderAssistant} runs={[]} enableTypewriter isLatestAssistant />);
    expect(screen.getByText('chat.run.status_running')).toBeInTheDocument();
  });

  it('collapses <think> content by default and toggles on click', () => {
    const messageWithThink: Message = {
      message_id: 'msg-3',
      conversation_id: 'conv-1',
      role: 'assistant',
      content: '<think>Hidden reasoning content that is long enough to be truncated in preview</think>\n\nVisible answer.',
      run_id: 'run-2',
      created_at: new Date().toISOString(),
    };

    render(<MessageItem message={messageWithThink} runs={[mockRun]} />);

    expect(screen.queryByText('Hidden reasoning content that is long enough to be truncated in preview')).not.toBeInTheDocument();
    expect(screen.getByText(/Hidden reasoning/)).toBeInTheDocument();
    expect(screen.getByText('Visible answer.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'chat.message.show_thoughts' }));
    expect(screen.getByText('Hidden reasoning content that is long enough to be truncated in preview')).toBeInTheDocument();
  });

  it('renders markdown image and auto-embeds standalone image url', () => {
    const messageWithImages: Message = {
      message_id: 'msg-4',
      conversation_id: 'conv-1',
      role: 'assistant',
      content: [
        'Here is an image:',
        '![alt text](https://example.com/a.png)',
        '',
        'https://example.com/b.jpg',
      ].join('\n'),
      run_id: 'run-3',
      created_at: new Date().toISOString(),
    };

    render(<MessageItem message={messageWithImages} runs={[mockRun]} />);
    expect(screen.getAllByRole('img').length).toBeGreaterThanOrEqual(2);
  });

  it('renders comparison variants as tabs and allows switching', () => {
    const comparisons: ComparisonVariant[] = [
      {
        id: 'cmp-1',
        model: 'claude-3-opus',
        status: 'succeeded',
        created_at: new Date().toISOString(),
        content: 'Alternative answer.',
      },
    ];

    render(
      <MessageItem
        message={mockAssistantMessage}
        runs={[mockRun]}
        runSourceMessageId={mockUserMessage.message_id}
        comparisonVariants={comparisons}
        onAddComparison={() => undefined}
      />
    );

    expect(screen.getByText('gpt-4')).toBeInTheDocument();
    expect(screen.getByText('claude-3-opus')).toBeInTheDocument();

    // default shows baseline content
    expect(screen.getByText('Hello! How can I help you?')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'claude-3-opus' }));
    expect(screen.getByText('Alternative answer.')).toBeInTheDocument();
  });
});
