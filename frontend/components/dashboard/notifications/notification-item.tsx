"use client";

import { useState } from "react";
import { Info, CheckCircle, AlertTriangle, XCircle, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n-context";
import { formatRelativeTime } from "@/lib/utils/time-formatter";
import { useMarkNotificationsRead } from "@/lib/swr/use-notifications";
import type { Notification } from "@/lib/api-types";

interface NotificationItemProps {
  notification: Notification;
  compact?: boolean;
}

const levelIcons = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: XCircle,
};

const levelColors = {
  info: "text-blue-600 bg-blue-50",
  success: "text-green-600 bg-green-50",
  warning: "text-yellow-600 bg-yellow-50",
  error: "text-red-600 bg-red-50",
};

export function NotificationItem({ notification, compact = false }: NotificationItemProps) {
  const { t, language } = useI18n();
  const { markAsRead, submitting } = useMarkNotificationsRead();
  const [marking, setMarking] = useState(false);

  const Icon = levelIcons[notification.level];

  const handleClick = async () => {
    if (!notification.is_read && !marking && !submitting) {
      setMarking(true);
      try {
        await markAsRead([notification.id]);
      } catch (error) {
        console.error('Failed to mark as read:', error);
      } finally {
        setMarking(false);
      }
    }

    if (notification.link_url) {
      window.open(notification.link_url, '_blank');
    }
  };

  return (
    <div
      className={cn(
        "p-4 cursor-pointer transition-colors hover:bg-muted/50",
        !notification.is_read && "bg-muted/20"
      )}
      onClick={handleClick}
    >
      <div className="flex gap-3">
        {/* 图标 */}
        <div className={cn("p-2 rounded-full flex-shrink-0 h-fit", levelColors[notification.level])}>
          <Icon className="h-4 w-4" />
        </div>

        {/* 内容 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h4 className={cn(
              "font-medium text-sm",
              !notification.is_read && "font-semibold"
            )}>
              {notification.title}
            </h4>
            {!notification.is_read && (
              <div className="h-2 w-2 rounded-full bg-blue-600 flex-shrink-0 mt-1" />
            )}
          </div>

          {!compact && (
            <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
              {notification.content}
            </p>
          )}

          <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
            <span>
              {formatRelativeTime(notification.created_at, language)}
            </span>
            {notification.link_url && (
              <>
                <span>•</span>
                <ExternalLink className="h-3 w-3" />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}