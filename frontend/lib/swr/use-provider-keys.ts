import useSWR from 'swr';
import { providerKeyService } from '@/http/provider-keys';
import type { ProviderKey } from '@/lib/api-types';

/**
 * 获取指定提供商的 API 密钥列表
 * @param providerId 提供商ID
 * @returns SWR hook 返回值
 */
export function useProviderKeys(providerId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<ProviderKey[]>(
    providerId ? `/providers/${providerId}/keys` : null,
    () => providerId ? providerKeyService.getKeys(providerId) : Promise.resolve([]),
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 5000, // 5秒内不重复请求
    }
  );

  return {
    keys: data || [],
    isLoading,
    error,
    mutate,
  };
}

/**
 * 获取单个密钥详情
 * @param providerId 提供商ID
 * @param keyId 密钥ID
 * @returns SWR hook 返回值
 */
export function useProviderKey(providerId: string | null, keyId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<ProviderKey>(
    providerId && keyId ? `/providers/${providerId}/keys/${keyId}` : null,
    () => providerId && keyId 
      ? providerKeyService.getKey(providerId, keyId) 
      : Promise.reject(new Error('Missing parameters')),
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
    }
  );

  return {
    key: data,
    isLoading,
    error,
    mutate,
  };
}