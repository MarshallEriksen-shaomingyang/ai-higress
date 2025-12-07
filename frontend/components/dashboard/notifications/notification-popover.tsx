"use client";

import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useI18n } from "@/lib/i18n-context";
import { useNotifications, useUnreadCount, useMarkNotificationsRead } from "@/lib/swr/use-notifications";
import { NotificationItem } from "./notification-item";
import { cn } from "@/lib/utils";
import type { Notification as NotificationType } from "@/lib/api-types";

interface NotificationPopoverProps {
  className?: string;
}

export function NotificationPopover({ className }: NotificationPopoverProps) {
  const { t } = useI18n();
  const { unreadCount } = useUnreadCount();
  const { notifications, loading } = useNotifications({
    status: 'unread',
    limit: 10
  });
  const { markAsRead } = useMarkNotificationsRead();

  const handleMarkAllRead = async () => {
    if (notifications && notifications.length > 0) {
      const unreadIds = notifications
        .filter((n: NotificationType) => !n.is_read)
        .map((n: NotificationType) => n.id);
      
      if (unreadIds.length > 0) {
        await markAsRead(unreadIds);
      }
    }
  };

  const hasUnread = unreadCount > 0;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn("relative", className)}
          aria-label={t('notifications.title')}
        >
          <Bell className="h-5 w-5" />
          {hasUnread && (
            <span className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-red-600 text-white text-xs flex items-center justify-center font-medium">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-96 p-0" align="end">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="font-semibold">{t('notifications.title')}</h3>
          {hasUnread && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleMarkAllRead}
              className="h-8 text-xs"
            >
              {t('notifications.markAllRead')}
            </Button>
          )}
        </div>

        <ScrollArea className="h-[400px]">
          {loading ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              {t('common.loading')}
            </div>
          ) : notifications && notifications.length > 0 ? (
            <div className="divide-y">
              {notifications.map((notification: NotificationType) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  compact
                />
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-sm text-muted-foreground">
              {t('notifications.noNotifications')}
            </div>
          )}
        </ScrollArea>

        {notifications && notifications.length > 0 && (
          <div className="p-3 border-t text-center">
            <Button
              variant="ghost"
              size="sm"
              className="w-full"
              onClick={() => window.location.href = '/dashboard/notifications'}
            >
              {t('notifications.viewAll')}
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}