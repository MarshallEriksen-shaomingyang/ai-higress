"use client";

import { useCallback, useMemo } from 'react';
import { useApiGet, useApiPost } from './hooks';
import { useAuthStore } from '@/lib/stores/auth-store';
import { useI18n } from '@/lib/i18n-context';
import type {
  Notification,
  NotificationAdminView,
  NotificationQueryParams,
  CreateNotificationRequest,
  MarkNotificationsReadRequest,
  UnreadCountResponse,
} from '@/lib/api-types';

// ============= 用户端 Hooks =============

/**
 * 获取当前用户的通知列表
 */
export const useNotifications = (params: NotificationQueryParams = {}) => {
  const queryString = useMemo(() => {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.set('status', params.status);
    if (params.limit) searchParams.set('limit', params.limit.toString());
    if (params.offset) searchParams.set('offset', params.offset.toString());
    return searchParams.toString();
  }, [params.status, params.limit, params.offset]);

  const url = queryString ? `/v1/notifications?${queryString}` : '/v1/notifications';

  const {
    data,
    error,
    loading,
    refresh,
  } = useApiGet<Notification[]>(url, {
    strategy: 'frequent',
  });

  return {
    notifications: data || [],
    loading,
    error,
    refresh,
  };
};

/**
 * 获取未读通知数量
 */
export const useUnreadCount = () => {
  const {
    data,
    error,
    loading,
    refresh,
  } = useApiGet<UnreadCountResponse>('/v1/notifications/unread-count', {
    strategy: 'realtime',
    refreshInterval: 30000, // 每30秒自动刷新
  });

  return {
    unreadCount: data?.unread_count ?? 0,
    loading,
    error,
    refresh,
  };
};

/**
 * 标记通知为已读
 */
export const useMarkNotificationsRead = () => {
  const { refresh: refreshNotifications } = useNotifications();
  const { refresh: refreshUnreadCount } = useUnreadCount();

  const { trigger, submitting, error } = useApiPost<
    { updated_count: number },
    MarkNotificationsReadRequest
  >('/v1/notifications/read');

  const markAsRead = useCallback(
    async (notificationIds: string[]) => {
      const result = await trigger({ notification_ids: notificationIds });
      
      // 刷新通知列表和未读数量
      await Promise.all([
        refreshNotifications(),
        refreshUnreadCount(),
      ]);

      return result;
    },
    [trigger, refreshNotifications, refreshUnreadCount]
  );

  return {
    markAsRead,
    submitting,
    error,
  };
};

// ============= 管理员 Hooks =============

/**
 * 获取管理员通知列表
 */
export const useAdminNotifications = (params: { limit?: number; offset?: number } = {}) => {
  const user = useAuthStore(state => state.user);
  const isSuperUser = user?.is_superuser === true;

  const queryString = useMemo(() => {
    const searchParams = new URLSearchParams();
    if (params.limit) searchParams.set('limit', params.limit.toString());
    if (params.offset) searchParams.set('offset', params.offset.toString());
    return searchParams.toString();
  }, [params.limit, params.offset]);

  const url = queryString
    ? `/v1/admin/notifications?${queryString}`
    : '/v1/admin/notifications';

  const {
    data,
    error,
    loading,
    refresh,
  } = useApiGet<NotificationAdminView[]>(
    isSuperUser ? url : null,
    { strategy: 'frequent' }
  );

  return {
    notifications: data || [],
    loading,
    error,
    refresh,
    isSuperUser,
  };
};

/**
 * 创建通知
 */
export const useCreateNotification = () => {
  const user = useAuthStore(state => state.user);
  const isSuperUser = user?.is_superuser === true;
  const { t } = useI18n();
  const { refresh } = useAdminNotifications();

  const { trigger, submitting, error } = useApiPost<
    NotificationAdminView,
    CreateNotificationRequest
  >('/v1/admin/notifications');

  const createNotification = useCallback(
    async (payload: CreateNotificationRequest) => {
      if (!isSuperUser) {
        throw new Error(t('common.error_superuser_required'));
      }

      const result = await trigger(payload);
      
      // 刷新通知列表
      await refresh();

      return result;
    },
    [isSuperUser, trigger, refresh, t]
  );

  return {
    createNotification,
    submitting,
    error,
    isSuperUser,
  };
};