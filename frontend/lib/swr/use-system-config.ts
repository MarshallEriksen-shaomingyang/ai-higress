import type {
  GatewayConfig,
  ProviderLimits,
  UpdateGatewayConfigRequest,
  UpdateProviderLimitsRequest,
} from '@/lib/api-types';
import { useApiGet, useApiPut } from './hooks';

/**
 * 获取和更新中转网关基础配置的 Hook。
 *
 * - GET /system/gateway-config
 * - PUT /system/gateway-config
 */
export function useGatewayConfig(enabled: boolean = true) {
  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<GatewayConfig>(enabled ? '/system/gateway-config' : null, {
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

/**
 * 获取和更新 Provider 限制配置的 Hook。
 *
 * - GET /system/provider-limits
 * - PUT /system/provider-limits
 */
export function useProviderLimits() {
  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<ProviderLimits>('/system/provider-limits', {
    strategy: 'static',
  });

  const {
    trigger,
    submitting,
    error: updateError,
  } = useApiPut<ProviderLimits, UpdateProviderLimitsRequest>('/system/provider-limits');

  return {
    limits: data,
    loading,
    validating,
    error,
    refresh,
    saveLimits: trigger,
    saving: submitting,
    saveError: updateError,
  };
}
