"use client";

import { useState, useMemo } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Bell, ChevronLeft, ChevronRight } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { useNotifications, useMarkNotificationsRead } from "@/lib/swr/use-notifications";
import { NotificationItem } from "./notification-item";

const PAGE_SIZE = 20;

export function NotificationList() {
  const { t } = useI18n();
  const [currentPage, setCurrentPage] = useState(1);
  const [activeTab, setActiveTab] = useState<"all" | "unread">("all");

  // 根据 tab 获取通知
  const { notifications, loading } = useNotifications({
    status: activeTab === "unread" ? "unread" : undefined,
    limit: PAGE_SIZE,
    offset: (currentPage - 1) * PAGE_SIZE,
  });

  const { markAsRead } = useMarkNotificationsRead();

  // 计算总页数（简化版，实际应该从 API 获取 total）
  const totalPages = useMemo(() => {
    if (!notifications || notifications.length < PAGE_SIZE) {
      return currentPage;
    }
    return currentPage + 1; // 简化处理，假设还有下一页
  }, [notifications, currentPage]);

  const handleMarkAllRead = async () => {
    if (notifications && notifications.length > 0) {
      const unreadIds = notifications
        .filter(n => !n.is_read)
        .map(n => n.id);
      
      if (unreadIds.length > 0) {
        await markAsRead(unreadIds);
      }
    }
  };

  const handleTabChange = (value: string) => {
    setActiveTab(value as "all" | "unread");
    setCurrentPage(1); // 切换 tab 时重置页码
  };

  if (loading && notifications.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("notifications.title")}</CardTitle>
          <CardDescription>{t("common.loading")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const hasUnread = notifications.some(n => !n.is_read);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Bell className="w-5 h-5" />
              {t("notifications.title")}
            </CardTitle>
            <CardDescription>
              {t("notifications.description")}
            </CardDescription>
          </div>
          {hasUnread && activeTab === "all" && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleMarkAllRead}
            >
              {t("notifications.markAllRead")}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList className="mb-4">
            <TabsTrigger value="all">{t("notifications.all")}</TabsTrigger>
            <TabsTrigger value="unread">{t("notifications.unread")}</TabsTrigger>
          </TabsList>

          <TabsContent value={activeTab} className="mt-0">
            {notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Bell className="w-12 h-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">
                  {t("notifications.noNotifications")}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {activeTab === "unread" 
                    ? t("notifications.noUnreadNotifications")
                    : t("notifications.noNotificationsDescription")}
                </p>
              </div>
            ) : (
              <>
                <div className="rounded-md border divide-y">
                  {notifications.map((notification) => (
                    <NotificationItem
                      key={notification.id}
                      notification={notification}
                    />
                  ))}
                </div>

                {/* 分页控件 */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-2 mt-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(p => p - 1)}
                      disabled={currentPage === 1 || loading}
                    >
                      <ChevronLeft className="w-4 h-4 mr-1" />
                      {t("common.previous")}
                    </Button>
                    <div className="text-sm text-muted-foreground px-4">
                      {currentPage} / {totalPages}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(p => p + 1)}
                      disabled={currentPage === totalPages || loading}
                    >
                      {t("common.next")}
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  </div>
                )}
              </>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}