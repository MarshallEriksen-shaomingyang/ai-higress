"use client";

import { useApiGet } from "@/lib/swr";
import type {
  Provider,
  UserAvailableProvidersResponse,
} from "@/http/provider";

interface UseProvidersOptions {
  userId: string | null;
  visibility?: 'all' | 'private' | 'public' | 'shared';
}

interface UseProvidersResult {
  privateProviders: Provider[];
  sharedProviders: Provider[];
  publicProviders: Provider[];
  allProviders: Provider[];
  total: number;
  loading: boolean;
  validating: boolean;
  error: any;
  refresh: () => Promise<UserAvailableProvidersResponse | undefined>;
}

/**
 * 使用 SWR 获取用户可用的提供商列表（私有 + 授权 + 公共）
 * 
 * @param options - 配置选项
 * @param options.userId - 用户 ID
 * @param options.visibility - 可见性过滤：'all' | 'private' | 'public' | 'shared'
 * 
 * @example
 * ```tsx
 * const { privateProviders, publicProviders, loading } = useProviders({
 *   userId: currentUser.id,
 *   visibility: 'all'
 * });
 * ```
 */
export const useProviders = (options: UseProvidersOptions): UseProvidersResult => {
  const { userId, visibility = 'all' } = options;

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<UserAvailableProvidersResponse>(
    userId ? `/users/${userId}/providers` : null,
    {
      params: visibility !== 'all' ? { visibility } : undefined,
      // 提供商列表变化频率适中，使用默认缓存策略
      strategy: "default",
    }
  );

  const privateProviders = data?.private_providers ?? [];
  const sharedProviders = data?.shared_providers ?? [];
  const publicProviders = data?.public_providers ?? [];
  const allProviders = [...privateProviders, ...sharedProviders, ...publicProviders];

  return {
    privateProviders,
    sharedProviders,
    publicProviders,
    allProviders,
    total: data?.total ?? 0,
    loading,
    validating,
    error,
    refresh,
  };
};

/**
 * 仅获取用户的私有提供商列表
 */
export const usePrivateProviders = (userId: string | null) => {
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

  return {
    providers: data ?? [],
    total: data?.length ?? 0,
    loading,
    validating,
    error,
    refresh,
  };
};
