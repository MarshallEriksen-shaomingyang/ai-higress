"use client";

import { useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { ConversationItem } from "./conversation-item";
import { useCachePreloader } from "@/lib/swr/cache";
import { conversationService } from "@/http/conversation";
import type { Conversation } from "@/lib/api-types";
import { SidebarSearchInput } from "./sidebar-search-input";
import { useChatSidebarSearchStore } from "@/lib/stores/chat-sidebar-search-store";

interface ConversationListProps {
  conversations: Conversation[];
  isLoading?: boolean;
  selectedConversationId?: string;
  onSelectConversation?: (conversationId: string) => void;
  onCreateConversation?: () => void;
  onArchiveConversation?: (conversationId: string) => void;
  onRenameConversation?: (conversationId: string, title: string) => void;
  onDeleteConversation?: (conversationId: string) => void;
  onLoadMore?: () => void;
  hasMore?: boolean;
  nextCursor?: string;
  assistantId?: string;
}

/**
 * 会话列表组件
 * 显示会话列表（按时间倒序），支持选中会话、分页加载和新建会话
 */
export function ConversationList({
  conversations,
  isLoading = false,
  selectedConversationId,
  onSelectConversation,
  onCreateConversation,
  onArchiveConversation,
  onRenameConversation,
  onDeleteConversation,
  onLoadMore,
  hasMore = false,
  nextCursor,
  assistantId,
}: ConversationListProps) {
  const { t } = useI18n();
  const { preloadData } = useCachePreloader();
  const conversationQuery = useChatSidebarSearchStore((s) => s.conversationQuery);
  const setConversationQuery = useChatSidebarSearchStore((s) => s.setConversationQuery);

  const normalizedQuery = useMemo(
    () => conversationQuery.trim().toLowerCase(),
    [conversationQuery]
  );
  const filteredConversations = useMemo(() => {
    if (!normalizedQuery) return conversations;
    return conversations.filter((conversation) => {
      const title = (conversation.title || "").toLowerCase();
      const id = (conversation.conversation_id || "").toLowerCase();
      return title.includes(normalizedQuery) || id.includes(normalizedQuery);
    });
  }, [conversations, normalizedQuery]);

  const isInitialLoading = isLoading && conversations.length === 0;
  const header = (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{t("chat.conversation.title")}</h2>
        <Button
          size="sm"
          disabled={isInitialLoading}
          onClick={isInitialLoading ? undefined : onCreateConversation}
          aria-label={t("chat.conversation.create")}
        >
          <Plus className="w-4 h-4 mr-1" aria-hidden="true" />
          {t("chat.conversation.create")}
        </Button>
      </div>
      <SidebarSearchInput
        value={conversationQuery}
        onValueChange={setConversationQuery}
        placeholder={t("chat.conversation.search_placeholder")}
        ariaLabel={t("chat.conversation.search_placeholder")}
        clearAriaLabel={t("chat.search.clear")}
        disabled={isInitialLoading}
      />
    </div>
  );

  // 预加载下一页数据（缓存优化）
  useEffect(() => {
    if (nextCursor && assistantId && !isLoading) {
      const nextPageKey = {
        url: '/v1/conversations',
        params: { assistant_id: assistantId, cursor: nextCursor, limit: 20 },
      };
      
      // 预加载下一页，但不触发重新验证
      preloadData(
        JSON.stringify(nextPageKey),
        () => conversationService.getConversations({
          assistant_id: assistantId,
          cursor: nextCursor,
          limit: 20,
        })
      );
    }
  }, [nextCursor, assistantId, isLoading, preloadData]);

  // 加载状态
  if (isLoading && conversations.length === 0) {
    return (
      <div className="space-y-4">
        {header}
        <div 
          className="flex items-center justify-center py-12"
          role="status"
          aria-live="polite"
          aria-label={t("chat.conversation.loading")}
        >
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" aria-hidden="true"></div>
        </div>
      </div>
    );
  }

  // 空状态
  if (!isLoading && conversations.length === 0) {
    return (
      <div className="space-y-4">
        {header}
        <div 
          className="flex flex-col items-center justify-center py-12 text-center"
          role="status"
          aria-live="polite"
        >
          <div className="text-muted-foreground mb-4">
            <div className="text-lg font-medium mb-2">
              {t("chat.conversation.empty")}
            </div>
            <div className="text-sm">
              {t("chat.conversation.empty_description")}
            </div>
          </div>
          <Button onClick={onCreateConversation} aria-label={t("chat.conversation.create")}>
            <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
            {t("chat.conversation.create")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4" role="region" aria-label={t("chat.conversation.list_label")}>
      {header}

      {/* 会话列表 */}
      {normalizedQuery && filteredConversations.length === 0 ? (
        <div className="py-10 text-center text-sm text-muted-foreground" role="status">
          {t("chat.conversation.search_empty")}
        </div>
      ) : (
        <div className="space-y-3" role="list" aria-label={t("chat.conversation.list")}>
          {filteredConversations.map((conversation) => (
            <div key={conversation.conversation_id} role="listitem">
              <ConversationItem
                conversation={conversation}
                isSelected={selectedConversationId === conversation.conversation_id}
                onSelect={onSelectConversation}
                onArchive={onArchiveConversation}
                onRename={onRenameConversation}
                onDelete={onDeleteConversation}
              />
            </div>
          ))}
        </div>
      )}

      {/* 加载更多按钮 */}
      {hasMore && (
        <div className="flex justify-center pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onLoadMore}
            disabled={isLoading}
            aria-label={isLoading ? t("chat.conversation.loading") : t("chat.message.load_more")}
          >
            {isLoading ? t("chat.conversation.loading") : t("chat.message.load_more")}
          </Button>
        </div>
      )}
    </div>
  );
}
