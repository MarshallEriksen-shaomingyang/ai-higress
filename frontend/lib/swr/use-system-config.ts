import type { GatewayConfig, UpdateGatewayConfigRequest } from '@/lib/api-types';
import { useApiGet, useApiPut } from './hooks';

/**
 * 获取和更新中转网关基础配置的 Hook。
 *
 * - GET /system/gateway-config
 * - PUT /system/gateway-config
 */
export function useGatewayConfig() {
  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<GatewayConfig>('/system/gateway-config', {
    strategy: 'static',
  });

  const {
    trigger,
    submitting,
    error: updateError,
  } = useApiPut<GatewayConfig, UpdateGatewayConfigRequest>('/system/gateway-config');

  return {
    config: data,
    loading,
    validating,
    error,
    refresh,
    saveConfig: trigger,
    saving: submitting,
    saveError: updateError,
  };
}

