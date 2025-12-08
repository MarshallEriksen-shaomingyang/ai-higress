"use client";

import useSWR from "swr";
import { adminService, type UserInfo } from "@/http/admin";
import { useAuthStore } from "@/lib/stores/auth-store";

/**
 * 获取所有用户列表（仅超级管理员可见）。
 */
export function useAdminUsers() {
  const user = useAuthStore(state => state.user);
  const isSuperUser = user?.is_superuser === true;

  const { data, error, isLoading, mutate } = useSWR<UserInfo[]>(
    isSuperUser ? "/admin/users" : null,
    () => adminService.getAllUsers(),
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
    }
  );

  return {
    users: data || [],
    loading: isLoading,
    error,
    refresh: mutate,
    isSuperUser,
  };
}

export type { UserInfo };
