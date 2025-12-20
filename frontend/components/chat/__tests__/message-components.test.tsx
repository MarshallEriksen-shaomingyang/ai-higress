import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MessageItem } from '../message-item';
import { MessageInput } from '../message-input';
import type { Message, RunSummary } from '@/lib/api-types';

// Mock i18n
vi.mock('@/lib/i18n-context', () => ({
  useI18n: () => ({
    t: (key: string) => key,
    language: 'zh',
  }),
}));

// Mock SWR
vi.mock('@/lib/swr/use-messages', () => ({
  useSendMessage: () => vi.fn(),
}));

describe('MessageItem', () => {
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

  it('shows status badge for assistant message', () => {
    render(<MessageItem message={mockAssistantMessage} runs={[mockRun]} />);
    expect(screen.getByText('chat.run.status_succeeded')).toBeInTheDocument();
  });

  it('collapses <think> content by default and toggles on click', () => {
    const messageWithThink: Message = {
      message_id: 'msg-3',
      conversation_id: 'conv-1',
      role: 'assistant',
      content: '<think>Hidden reasoning</think>\n\nVisible answer.',
      run_id: 'run-2',
      created_at: new Date().toISOString(),
    };

    render(<MessageItem message={messageWithThink} runs={[mockRun]} />);

    expect(screen.queryByText('Hidden reasoning')).not.toBeInTheDocument();
    expect(screen.getByText('Visible answer.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'chat.message.show_thoughts' }));
    expect(screen.getByText('Hidden reasoning')).toBeInTheDocument();
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
});

describe('MessageInput', () => {
  it('renders input field and send button', () => {
    render(<MessageInput conversationId="conv-1" />);
    expect(screen.getByPlaceholderText('chat.message.input_placeholder')).toBeInTheDocument();
    expect(screen.getByTitle('chat.message.send_hint')).toBeInTheDocument();
  });

  it('disables input when disabled prop is true', () => {
    render(<MessageInput conversationId="conv-1" disabled />);
    const input = screen.getByPlaceholderText('chat.conversation.archived_notice');
    expect(input).toBeDisabled();
  });

  it('shows archived notice in placeholder when disabled', () => {
    render(<MessageInput conversationId="conv-1" disabled />);
    expect(screen.getByPlaceholderText('chat.conversation.archived_notice')).toBeInTheDocument();
  });
});
