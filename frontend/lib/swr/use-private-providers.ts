"use client";

import { useApiGet, useApiPost, useApiPut, useApiDelete } from "./hooks";
import type {
  Provider,
  CreatePrivateProviderRequest,
  UpdatePrivateProviderRequest,
} from "@/http/provider";

interface UsePrivateProvidersOptions {
  userId: string | null;
}

/**
 * 使用 SWR 获取用户的私有提供商列表
 * 
 * @param options - 配置选项
 * @param options.userId - 用户 ID
 * 
 * @example
 * ```tsx
 * const { providers, loading, refresh, createProvider } = usePrivateProviders({
 *   userId: currentUser.id
 * });
 * ```
 */
export const usePrivateProviders = (options: UsePrivateProvidersOptions) => {
  const { userId } = options;

  // 获取私有提供商列表
  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<Provider[]>(
    userId ? `/users/${userId}/private-providers` : null,
    {
      strategy: "default",
    }
  );

  // 创建私有提供商
  const createMutation = useApiPost<Provider, CreatePrivateProviderRequest>(
    userId ? `/users/${userId}/private-providers` : ""
  );

  // 更新私有提供商
  const updateMutation = useApiPut<Provider, UpdatePrivateProviderRequest>(
    userId ? `/users/${userId}/private-providers` : ""
  );

  // 删除私有提供商
  const deleteMutation = useApiDelete<void>(
    userId ? `/users/${userId}/private-providers` : ""
  );

  // 创建提供商的包装函数
  const createProvider = async (data: CreatePrivateProviderRequest) => {
    const result = await createMutation.trigger(data);
    // 创建成功后刷新列表
    await refresh();
    return result;
  };

  // 更新提供商的包装函数
  const updateProvider = async (providerId: string, data: UpdatePrivateProviderRequest) => {
    if (!userId) throw new Error("User ID is required");
    const result = await updateMutation.trigger(data);
    // 更新成功后刷新列表
    await refresh();
    return result;
  };

  // 删除提供商的包装函数
  const deleteProvider = async (providerId: string) => {
    if (!userId) throw new Error("User ID is required");
    const result = await deleteMutation.trigger();
    // 删除成功后刷新列表
    await refresh();
    return result;
  };

  return {
    providers: data ?? [],
    total: data?.length ?? 0,
    loading,
    validating,
    error,
    refresh,
    createProvider,
    updateProvider,
    deleteProvider,
    creating: createMutation.submitting,
    updating: updateMutation.submitting,
    deleting: deleteMutation.submitting,
  };
};

/**
 * 获取私有提供商配额信息
 * 
 * @param userId - 用户 ID
 * 
 * @example
 * ```tsx
 * const { current, limit, percentage, loading } = usePrivateProviderQuota(userId);
 * ```
 */
export const usePrivateProviderQuota = (userId: string | null) => {
  // TODO: 接入真实的配额 API
  // const { data, error, loading, refresh } = useApiGet<{ current: number; limit: number }>(
  //   userId ? `/users/${userId}/quota` : null,
  //   { strategy: "default" }
  // );

  // 暂时返回模拟数据
  const data = { current: 0, limit: 10 };
  const loading = false;
  const error = null;

  const percentage = data.limit > 0 ? (data.current / data.limit) * 100 : 0;
  const remaining = Math.max(0, data.limit - data.current);

  return {
    current: data.current,
    limit: data.limit,
    percentage,
    remaining,
    loading,
    error,
    refresh: async () => {},
  };
};
