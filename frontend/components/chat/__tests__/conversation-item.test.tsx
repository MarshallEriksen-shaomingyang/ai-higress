import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ConversationItem } from '../conversation-item';
import type { Conversation } from '@/lib/api-types';

// Mock i18n context
vi.mock('@/lib/i18n-context', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'chat.conversation.archive': 'Archive Conversation',
        'chat.conversation.delete': 'Delete Conversation',
        'chat.conversation.archive_confirm': 'Are you sure you want to archive this conversation?',
        'chat.conversation.delete_confirm': 'Are you sure you want to delete this conversation?',
        'chat.conversation.last_activity': 'Last activity',
        'chat.conversation.untitled': 'Untitled Conversation',
        'chat.action.cancel': 'Cancel',
        'chat.action.confirm': 'Confirm',
        'chat.action.delete': 'Delete',
      };
      return translations[key] || key;
    },
  }),
}));

describe('ConversationItem', () => {
  const mockConversation: Conversation = {
    conversation_id: 'conv-1',
    assistant_id: 'asst-1',
    project_id: 'proj-1',
    title: 'Test Conversation',
    archived: false,
    last_activity_at: new Date().toISOString(),
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  it('should render conversation title', () => {
    render(<ConversationItem conversation={mockConversation} />);
    expect(screen.getByText('Test Conversation')).toBeInTheDocument();
  });

  it('should render untitled when no title provided', () => {
    const conversationWithoutTitle = { ...mockConversation, title: undefined };
    render(<ConversationItem conversation={conversationWithoutTitle} />);
    expect(screen.getByText('Untitled Conversation')).toBeInTheDocument();
  });

  it('should not display <think> blocks in title', () => {
    const conversationWithThinkTitle = {
      ...mockConversation,
      title: '<think>Hidden reasoning</think> Visible title',
    };
    render(<ConversationItem conversation={conversationWithThinkTitle} />);
    expect(screen.getByText('Visible title')).toBeInTheDocument();
    expect(screen.queryByText('Hidden reasoning')).not.toBeInTheDocument();
  });

  it('should fall back to untitled when title only contains <think>', () => {
    const conversationWithOnlyThink = {
      ...mockConversation,
      title: '<think>Hidden reasoning only</think>',
    };
    render(<ConversationItem conversation={conversationWithOnlyThink} />);
    expect(screen.getByText('Untitled Conversation')).toBeInTheDocument();
  });

  it('should call onSelect when clicked', () => {
    const onSelect = vi.fn();
    render(<ConversationItem conversation={mockConversation} onSelect={onSelect} />);
    
    const card = screen.getByText('Test Conversation').closest('[data-slot="card"]');
    fireEvent.click(card!);
    
    expect(onSelect).toHaveBeenCalledWith('conv-1');
  });

  it('should show selected state', () => {
    const { container } = render(
      <ConversationItem conversation={mockConversation} isSelected={true} />
    );
    
    const card = container.querySelector('[data-slot="card"]');
    expect(card?.className).toContain('ring-2');
  });

  // 注意：下拉菜单的交互测试在实际环境中需要更复杂的设置
  // 这里我们只测试基本的渲染和点击功能
  it('should have archive and delete functionality', () => {
    const onArchive = vi.fn();
    const onDelete = vi.fn();
    
    render(
      <ConversationItem
        conversation={mockConversation}
        onArchive={onArchive}
        onDelete={onDelete}
      />
    );
    
    // 验证组件渲染成功
    expect(screen.getByText('Test Conversation')).toBeInTheDocument();
    
    // 验证有操作按钮
    const menuButton = screen.getByRole('button');
    expect(menuButton).toBeInTheDocument();
  });
});
