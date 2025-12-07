"use client";

import { useCallback, useState } from "react";
import { useApiGet, useApiPost } from "./hooks";
import type {
  RegistrationWindow,
  CreateRegistrationWindowRequest,
} from "@/lib/api-types";
import { useAuthStore } from "@/lib/stores/auth-store";
import { useI18n } from "@/lib/i18n-context";
import { httpClient } from "@/http/client";

/**
 * 获取当前激活的注册窗口（仅超级管理员会发起请求）。
 */
export const useActiveRegistrationWindow = () => {
  const currentUser = useAuthStore((state) => state.user);
  const isSuperUser = currentUser?.is_superuser === true;

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<RegistrationWindow | null>(
    isSuperUser ? "/admin/registration-windows/active" : null,
    {
      strategy: "frequent",
    }
  );

  return {
    window: data ?? null,
    loading,
    validating,
    error,
    refresh,
    isSuperUser,
  };
};

/**
 * 创建注册窗口的 Hook，支持自动激活与手动激活两种模式。
 */
export const useCreateRegistrationWindow = () => {
  const currentUser = useAuthStore((state) => state.user);
  const isSuperUser = currentUser?.is_superuser === true;
  const { t } = useI18n();

  const {
    trigger: triggerAuto,
    submitting: autoSubmitting,
    error: autoError,
  } = useApiPost<RegistrationWindow, CreateRegistrationWindowRequest>(
    "/admin/registration-windows/auto"
  );
  const {
    trigger: triggerManual,
    submitting: manualSubmitting,
    error: manualError,
  } = useApiPost<RegistrationWindow, CreateRegistrationWindowRequest>(
    "/admin/registration-windows/manual"
  );

  const createAuto = useCallback(
    async (payload: CreateRegistrationWindowRequest) => {
      if (!isSuperUser) {
        throw new Error(t("common.error_superuser_required"));
      }
      return await triggerAuto(payload);
    },
    [triggerAuto, isSuperUser, t]
  );

  const createManual = useCallback(
    async (payload: CreateRegistrationWindowRequest) => {
      if (!isSuperUser) {
        throw new Error(t("common.error_superuser_required"));
      }
      return await triggerManual(payload);
    },
    [isSuperUser, triggerManual, t]
  );

  const creating = autoSubmitting || manualSubmitting;

  return {
    createAuto,
    createManual,
    creating,
    autoError,
    manualError,
    isSuperUser,
  };
};

/**
 * 立即关闭注册窗口
 */
export const useCloseRegistrationWindow = () => {
  const currentUser = useAuthStore((state) => state.user);
  const isSuperUser = currentUser?.is_superuser === true;
  const { t } = useI18n();
  const [closing, setClosing] = useState(false);

  const closeWindow = useCallback(
    async (windowId: string) => {
      if (!isSuperUser) {
        throw new Error(t("common.error_superuser_required"));
      }
      try {
        setClosing(true);
        const response = await httpClient.post<RegistrationWindow>(
          `/admin/registration-windows/${windowId}/close`
        );
        return response.data;
      } finally {
        setClosing(false);
      }
    },
    [isSuperUser, t]
  );

  return {
    closeWindow,
    closing,
    isSuperUser,
  };
};
