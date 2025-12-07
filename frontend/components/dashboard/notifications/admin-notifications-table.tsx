"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Bell, Plus, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { formatDateTime } from "@/lib/utils/time-formatter";
import { useAdminNotifications } from "@/lib/swr/use-notifications";
import { AdminNotificationForm } from "./admin-notification-form";
import type { NotificationAdminView } from "@/lib/api-types";

const PAGE_SIZE = 20;

export function AdminNotificationsTable() {
  const { t, language } = useI18n();
  const [currentPage, setCurrentPage] = useState(1);
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  const { notifications, loading, refresh, isSuperUser } = useAdminNotifications({
    limit: PAGE_SIZE,
    offset: (currentPage - 1) * PAGE_SIZE,
  });

  // 如果不是超级管理员，不渲染组件
  if (!isSuperUser) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("notifications.admin.title")}</CardTitle>
          <CardDescription>{t("common.error_superuser_required")}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  // 计算总页数（简化版）
  const totalPages = notifications.length < PAGE_SIZE ? currentPage : currentPage + 1;

  // 获取等级徽章
  const getLevelBadge = (level: string) => {
    const badges = {
      info: <Badge variant="secondary">{t("notifications.level.info")}</Badge>,
      success: <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100">{t("notifications.level.success")}</Badge>,
      warning: <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100">{t("notifications.level.warning")}</Badge>,
      error: <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100">{t("notifications.level.error")}</Badge>,
    };
    return badges[level as keyof typeof badges] || <Badge>{level}</Badge>;
  };

  // 获取目标类型徽章
  const getTargetTypeBadge = (targetType: string, notification: NotificationAdminView) => {
    if (targetType === 'all') {
      return <Badge variant="outline">{t("notifications.targetType.all")}</Badge>;
    } else if (targetType === 'users') {
      const count = notification.target_user_ids?.length || 0;
      return <Badge variant="outline">{t("notifications.targetType.users")} ({count})</Badge>;
    } else if (targetType === 'roles') {
      const count = notification.target_role_codes?.length || 0;
      return <Badge variant="outline">{t("notifications.targetType.roles")} ({count})</Badge>;
    }
    return <Badge variant="outline">{targetType}</Badge>;
  };

  if (loading && notifications.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("notifications.admin.title")}</CardTitle>
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

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Bell className="w-5 h-5" />
                {t("notifications.admin.title")}
              </CardTitle>
              <CardDescription>
                {t("notifications.admin.description")}
              </CardDescription>
            </div>
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="w-4 h-4 mr-2" />
              {t("notifications.form.createTitle")}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Bell className="w-12 h-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">
                {t("notifications.noNotifications")}
              </h3>
              <p className="text-sm text-muted-foreground mb-4">
                {t("notifications.noNotificationsDescription")}
              </p>
              <Button onClick={() => setShowCreateDialog(true)}>
                <Plus className="w-4 h-4 mr-2" />
                {t("notifications.form.createTitle")}
              </Button>
            </div>
          ) : (
            <>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[200px]">{t("notifications.form.title")}</TableHead>
                      <TableHead className="w-[300px]">{t("notifications.form.content")}</TableHead>
                      <TableHead className="w-[100px]">{t("notifications.form.level")}</TableHead>
                      <TableHead className="w-[150px]">{t("notifications.form.targetType")}</TableHead>
                      <TableHead className="w-[80px] text-center">{t("common.status")}</TableHead>
                      <TableHead className="w-[180px]">{t("common.created_at")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {notifications.map((notification) => (
                      <TableRow key={notification.id}>
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            {notification.title}
                            {notification.link_url && (
                              <ExternalLink className="h-3 w-3 text-muted-foreground" />
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          <div className="line-clamp-2">{notification.content}</div>
                        </TableCell>
                        <TableCell>
                          {getLevelBadge(notification.level)}
                        </TableCell>
                        <TableCell>
                          {getTargetTypeBadge(notification.target_type, notification)}
                        </TableCell>
                        <TableCell className="text-center">
                          {notification.is_active ? (
                            <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100">
                              {t("common.active")}
                            </Badge>
                          ) : (
                            <Badge variant="secondary">{t("common.inactive")}</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDateTime(notification.created_at, language)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
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
        </CardContent>
      </Card>

      {/* 创建通知对话框 */}
      <AdminNotificationForm
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onSuccess={refresh}
      />
    </>
  );
}