"use client";

import { useCallback } from 'react';
import { useApiGet, useApiPost } from './hooks';
import { useAuthStore } from '@/lib/stores/auth-store';
import { useI18n } from '@/lib/i18n-context';
import type { AdminSystemConfig, AdminSystemConfigUpsertRequest } from '@/lib/api-types';

export const KB_GLOBAL_EMBEDDING_LOGICAL_MODEL_KEY = 'KB_GLOBAL_EMBEDDING_LOGICAL_MODEL';

export function useAdminSystemConfig(key: string | null, enabled: boolean = true) {
  const user = useAuthStore(state => state.user);
  const isSuperUser = user?.is_superuser === true;

  const safeKey = key ? encodeURIComponent(key) : null;
  const url = enabled && isSuperUser && safeKey ? `/v1/admin/system/configs/${safeKey}` : null;

  const { data, error, loading, validating, refresh } = useApiGet<AdminSystemConfig>(url, {
    strategy: 'static',
  });

  return {
    config: data,
    loading,
    validating,
    error,
    refresh,
    isSuperUser,
  };
}

export function useUpsertAdminSystemConfig() {
  const user = useAuthStore(state => state.user);
  const isSuperUser = user?.is_superuser === true;
  const { t } = useI18n();

  const { trigger, submitting, error } = useApiPost<AdminSystemConfig, AdminSystemConfigUpsertRequest>(
    '/v1/admin/system/configs',
    { revalidate: false }
  );

  const upsert = useCallback(async (payload: AdminSystemConfigUpsertRequest) => {
    if (!isSuperUser) {
      throw new Error(t('common.error_superuser_required'));
    }
    return trigger(payload);
  }, [isSuperUser, t, trigger]);

  return {
    upsert,
    submitting,
    error,
    isSuperUser,
  };
}

