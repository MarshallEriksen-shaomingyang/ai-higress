"use client";

import { useApiGet } from "@/lib/swr";
import type {
  Provider,
  ModelsResponse,
  HealthStatus,
  MetricsResponse,
} from "@/http/provider";

interface UseProviderDetailOptions {
  providerId: string | null;
  logicalModel?: string;
}

interface UseProviderDetailResult {
  provider: Provider | undefined;
  models: ModelsResponse | undefined;
  health: HealthStatus | undefined;
  metrics: MetricsResponse | undefined;
  loading: boolean;
  error: any;
  refresh: () => Promise<void>;
}

/**
 * 使用 SWR 获取 Provider 详情数据
 * 
 * 并行获取：
 * - Provider 基本信息
 * - 模型列表
 * - 健康状态
 * - 路由指标
 * 
 * @param options - 配置选项
 * @param options.providerId - Provider ID
 * @param options.logicalModel - 可选的逻辑模型过滤
 * 
 * @example
 * ```tsx
 * const { provider, models, health, metrics, loading } = useProviderDetail({
 *   providerId: 'openai'
 * });
 * ```
 */
export const useProviderDetail = (
  options: UseProviderDetailOptions
): UseProviderDetailResult => {
  const { providerId, logicalModel } = options;

  // 获取 Provider 基本信息
  const {
    data: provider,
    error: providerError,
    loading: providerLoading,
    refresh: refreshProvider,
  } = useApiGet<Provider>(
    providerId ? `/providers/${providerId}` : null,
    {
      strategy: "default",
    }
  );

  // 获取模型列表
  const {
    data: models,
    error: modelsError,
    loading: modelsLoading,
    refresh: refreshModels,
  } = useApiGet<ModelsResponse>(
    providerId ? `/providers/${providerId}/models` : null,
    {
      strategy: "default",
    }
  );

  // 获取健康状态
  const {
    data: health,
    error: healthError,
    loading: healthLoading,
    refresh: refreshHealth,
  } = useApiGet<HealthStatus>(
    providerId ? `/providers/${providerId}/health` : null,
    {
      strategy: "frequent", // 健康状态需要更频繁地更新
    }
  );

  // 获取路由指标
  const {
    data: metrics,
    error: metricsError,
    loading: metricsLoading,
    refresh: refreshMetrics,
  } = useApiGet<MetricsResponse>(
    providerId ? `/providers/${providerId}/metrics` : null,
    {
      params: logicalModel ? { logical_model: logicalModel } : undefined,
      strategy: "frequent", // 指标需要更频繁地更新
    }
  );

  // 统一的加载状态：任何一个请求在加载中都算加载中
  const loading = providerLoading || modelsLoading || healthLoading || metricsLoading;

  // 统一的错误：优先显示 provider 错误，因为它是最关键的
  const error = providerError || modelsError || healthError || metricsError;

  // 统一的刷新方法
  const refresh = async () => {
    await Promise.all([
      refreshProvider(),
      refreshModels(),
      refreshHealth(),
      refreshMetrics(),
    ]);
  };

  return {
    provider,
    models,
    health,
    metrics,
    loading,
    error,
    refresh,
  };
};