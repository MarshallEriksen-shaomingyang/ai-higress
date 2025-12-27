"use client";

import { useState } from "react";
import { AdaptiveCard } from "@/components/cards/adaptive-card";
import { CardHeader, CardTitle, CardDescription, CardAction } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreVertical, Archive, Trash2, Pencil } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import type { Conversation } from "@/lib/api-types";
import { ConversationItemDialogs } from "./conversation-item-dialogs";
import { useChatStore } from "@/lib/stores/chat-store";
import { Skeleton } from "@/components/ui/skeleton";
import { sanitizeConversationTitle } from "@/lib/chat/sanitize-conversation-title";

interface ConversationItemProps {
  conversation: Conversation;
  isSelected?: boolean;
  onSelect?: (conversationId: string) => void;
  onArchive?: (conversationId: string) => void;
  onRename?: (conversationId: string, title: string) => void;
  onDelete?: (conversationId: string) => void;
}

/**
 * 会话列表项组件
 * 显示会话 title 和 last_activity_at，提供归档和删除按钮
 */
export function ConversationItem({
  conversation,
  isSelected = false,
  onSelect,
  onArchive,
  onRename,
  onDelete,
}: ConversationItemProps) {
  const { t } = useI18n();
  const sanitizedTitle = sanitizeConversationTitle(conversation.title);
  const displayTitle = sanitizedTitle || t("chat.conversation.untitled");
  const [showArchiveDialog, setShowArchiveDialog] = useState(false);
  const [showRenameDialog, setShowRenameDialog] = useState(false);
  const [draftTitle, setDraftTitle] = useState(sanitizedTitle);
  const conversationPending =
    useChatStore((s) => s.conversationPending[conversation.conversation_id]) ?? false;
  const hasTitle = !!sanitizedTitle;
  const showTitleSkeleton = !hasTitle && conversationPending;

  const handleCardClick = () => {
    if (onSelect) {
      onSelect(conversation.conversation_id);
    }
  };

  const handleArchiveConfirm = () => {
    if (onArchive) {
      onArchive(conversation.conversation_id);
    }
    setShowArchiveDialog(false);
  };

  const handleRenameConfirm = () => {
    if (onRename) {
      onRename(conversation.conversation_id, draftTitle.trim());
    }
    setShowRenameDialog(false);
  };

  // 格式化时间显示
  const formatLastActivity = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) {
      return t("chat.conversation.just_now") || "刚刚";
    } else if (diffMins < 60) {
      return `${diffMins} ${t("chat.conversation.minutes_ago") || "分钟前"}`;
    } else if (diffHours < 24) {
      return `${diffHours} ${t("chat.conversation.hours_ago") || "小时前"}`;
    } else if (diffDays < 7) {
      return `${diffDays} ${t("chat.conversation.days_ago") || "天前"}`;
    } else {
      return date.toLocaleDateString();
    }
  };

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Enter 或 Space 键选择会话
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleCardClick();
    }
  };

  return (
    <>
      <AdaptiveCard
        showDecor={false}
        selected={isSelected}
        className="cursor-pointer transition-all hover:bg-muted/40 hover:shadow-md hover:scale-100 data-[state=selected]:hover:bg-transparent"
        onClick={handleCardClick}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        role="button"
        aria-label={`${t("chat.conversation.select")} ${displayTitle}`}
        aria-pressed={isSelected}
      >
        <CardHeader>
          <CardTitle className="text-[15px] leading-snug">
            {showTitleSkeleton ? (
              <div className="flex items-center gap-2">
                <Skeleton className="h-4 w-32" />
                <span className="text-[11px] text-muted-foreground animate-pulse">
                  {t("chat.message.loading")}
                </span>
              </div>
            ) : (
              displayTitle
            )}
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground/75">
            {t("chat.conversation.last_activity")}: {formatLastActivity(conversation.last_activity_at)}
          </CardDescription>
          <CardAction>
            <div className="flex items-center gap-2">
              {isSelected ? (
                <Badge
                  variant="default"
                  className="h-5 px-2 text-[10px] leading-none"
                >
                  {t("chat.action.selected")}
                </Badge>
              ) : null}

              <DropdownMenu>
                <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                  <Button 
                    variant="ghost" 
                    size="icon-sm"
                    aria-label={t("chat.conversation.actions")}
                  >
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      setDraftTitle(sanitizedTitle);
                      setShowRenameDialog(true);
                    }}
                  >
                    <Pencil className="w-4 h-4 mr-2" />
                    {t("chat.conversation.rename")}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowArchiveDialog(true);
                    }}
                  >
                    <Archive className="w-4 h-4 mr-2" />
                    {t("chat.conversation.archive")}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onDelete) {
                        onDelete(conversation.conversation_id);
                      }
                    }}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    {t("chat.conversation.delete")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </CardAction>
        </CardHeader>
      </AdaptiveCard>

      <ConversationItemDialogs
        showRenameDialog={showRenameDialog}
        setShowRenameDialog={setShowRenameDialog}
        draftTitle={draftTitle}
        setDraftTitle={setDraftTitle}
        onRenameConfirm={handleRenameConfirm}
        showArchiveDialog={showArchiveDialog}
        setShowArchiveDialog={setShowArchiveDialog}
        onArchiveConfirm={handleArchiveConfirm}
      />
    </>
  );
}
