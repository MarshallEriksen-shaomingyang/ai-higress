import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ConversationList } from '../conversation-list';
import type { Conversation } from '@/lib/api-types';
import { useChatSidebarSearchStore } from '@/lib/stores/chat-sidebar-search-store';

// Mock i18n context
vi.mock('@/lib/i18n-context', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'chat.conversation.title': 'Conversations',
        'chat.conversation.create': 'New Conversation',
        'chat.conversation.search_placeholder': 'Search conversations...',
        'chat.conversation.search_empty': 'No matching conversations',
        'chat.search.clear': 'Clear search',
        'chat.conversation.empty': 'No Conversations',
        'chat.conversation.empty_description': 'Start a new conversation with this assistant',
        'chat.conversation.loading': 'Loading conversations...',
        'chat.message.load_more': 'Load More',
      };
      return translations[key] || key;
    },
  }),
}));

// Mock ConversationItem
vi.mock('../conversation-item', () => ({
  ConversationItem: ({ conversation, isSelected, onSelect }: any) => (
    <div
      data-testid={`conversation-${conversation.conversation_id}`}
      onClick={() => onSelect?.(conversation.conversation_id)}
      className={isSelected ? 'selected' : ''}
    >
      {conversation.title || 'Untitled'}
    </div>
  ),
}));

describe('ConversationList', () => {
  beforeEach(() => {
    useChatSidebarSearchStore.getState().reset();
  });

  const mockConversations: Conversation[] = [
    {
      conversation_id: 'conv-1',
      assistant_id: 'asst-1',
      project_id: 'proj-1',
      title: 'Conversation 1',
      archived: false,
      last_activity_at: '2024-01-02T00:00:00Z',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
    {
      conversation_id: 'conv-2',
      assistant_id: 'asst-1',
      project_id: 'proj-1',
      title: 'Conversation 2',
      archived: false,
      last_activity_at: '2024-01-01T00:00:00Z',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  ];

  it('should render conversations list', () => {
    render(<ConversationList conversations={mockConversations} />);
    
    expect(screen.getByText('Conversations')).toBeInTheDocument();
    expect(screen.getByTestId('conversation-conv-1')).toBeInTheDocument();
    expect(screen.getByTestId('conversation-conv-2')).toBeInTheDocument();
  });

  it('should filter conversations by search query', () => {
    useChatSidebarSearchStore.getState().setConversationQuery('2');
    render(<ConversationList conversations={mockConversations} />);

    expect(screen.queryByTestId('conversation-conv-1')).not.toBeInTheDocument();
    expect(screen.getByTestId('conversation-conv-2')).toBeInTheDocument();
  });

  it('should show empty search state when no conversations match', () => {
    useChatSidebarSearchStore.getState().setConversationQuery('nope');
    render(<ConversationList conversations={mockConversations} />);

    expect(screen.getByText('No matching conversations')).toBeInTheDocument();
  });

  it('should show loading state', () => {
    render(<ConversationList conversations={[]} isLoading={true} />);
    
    expect(screen.getByText('Conversations')).toBeInTheDocument();
    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  it('should show empty state', () => {
    render(<ConversationList conversations={[]} isLoading={false} />);
    
    expect(screen.getByText('No Conversations')).toBeInTheDocument();
    expect(screen.getByText('Start a new conversation with this assistant')).toBeInTheDocument();
  });

  it('should call onCreateConversation when create button clicked', () => {
    const onCreateConversation = vi.fn();
    render(
      <ConversationList
        conversations={mockConversations}
        onCreateConversation={onCreateConversation}
      />
    );
    
    const createButton = screen.getByText('New Conversation');
    fireEvent.click(createButton);
    
    expect(onCreateConversation).toHaveBeenCalled();
  });

  it('should call onSelectConversation when conversation clicked', () => {
    const onSelectConversation = vi.fn();
    render(
      <ConversationList
        conversations={mockConversations}
        onSelectConversation={onSelectConversation}
      />
    );
    
    const conversation = screen.getByTestId('conversation-conv-1');
    fireEvent.click(conversation);
    
    expect(onSelectConversation).toHaveBeenCalledWith('conv-1');
  });

  it('should highlight selected conversation', () => {
    render(
      <ConversationList
        conversations={mockConversations}
        selectedConversationId="conv-1"
      />
    );
    
    const selectedConversation = screen.getByTestId('conversation-conv-1');
    expect(selectedConversation.className).toContain('selected');
  });

  it('should show load more button when hasMore is true', () => {
    render(
      <ConversationList
        conversations={mockConversations}
        hasMore={true}
      />
    );
    
    expect(screen.getByText('Load More')).toBeInTheDocument();
  });

  it('should call onLoadMore when load more button clicked', () => {
    const onLoadMore = vi.fn();
    render(
      <ConversationList
        conversations={mockConversations}
        hasMore={true}
        onLoadMore={onLoadMore}
      />
    );
    
    const loadMoreButton = screen.getByText('Load More');
    fireEvent.click(loadMoreButton);
    
    expect(onLoadMore).toHaveBeenCalled();
  });

  it('should disable load more button when loading', () => {
    render(
      <ConversationList
        conversations={mockConversations}
        hasMore={true}
        isLoading={true}
      />
    );
    
    const loadMoreButton = screen.getByText('Loading conversations...');
    expect(loadMoreButton).toBeDisabled();
  });
});
