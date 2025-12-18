"use client";

import { useMemo } from 'react';
import { useApiGet } from './hooks';
import type {
  DashboardV2KPIData,
  DashboardV2PulseResponse,
  DashboardV2TokensResponse,
  DashboardV2TopModelsResponse,
  DashboardV2CostByProviderResponse,
  DashboardV2ProvidersMetricsResponse,
  SystemKPIData,
  SystemDashboardProvidersResponse,
} from '@/lib/api-types';

/**
 * Dashboard v2 筛选器参数
 */
export interface DashboardV2FilterParams {
  timeRange?: 'today' | '7d' | '30d';
  transport?: 'all' | 'http' | 'sdk' | 'claude_cli';
  isStream?: 'all' | 'true' | 'false';
}

/**
 * Dashboard v2 自定义缓存策略
 * 优化：减少不必要的重新验证，提升性能
 */
const dashboardV2CacheConfig = {
  revalidateOnFocus: false, // 关闭焦点时重新验证，减少请求
  revalidateOnReconnect: true,
  refreshInterval: 60000, // 60s TTL
  dedupingInterval: 5000, // 增加去重间隔到 5s，减少重复请求
};

/**
 * 获取用户 Dashboard v2 KPI 指标
 * 
 * @param filters 筛选器参数
 * @returns KPI 数据、加载状态、错误信息和刷新函数
 */
export const useUserDashboardKPIs = (filters: DashboardV2FilterParams = {}) => {
  const {
    timeRange = '7d',
    transport = 'all',
    isStream = 'all',
  } = filters;

  const params = useMemo(() => ({
    time_range: timeRange,
    transport,
    is_stream: isStream,
  }), [timeRange, transport, isStream]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<DashboardV2KPIData>(
    '/metrics/user-dashboard/kpis',
    {
      ...dashboardV2CacheConfig,
      params,
    }
  );

  return {
    data,
    error,
    loading,
    validating,
    refresh,
  };
};

/**
 * 获取用户 Dashboard v2 Pulse 数据（近 24h，分钟粒度）
 * 
 * @param filters 筛选器参数（不包含 timeRange，固定近 24h）
 * @returns Pulse 数据、加载状态、错误信息和刷新函数
 */
export const useUserDashboardPulse = (filters: Omit<DashboardV2FilterParams, 'timeRange'> = {}) => {
  const {
    transport = 'all',
    isStream = 'all',
  } = filters;

  const params = useMemo(() => ({
    transport,
    is_stream: isStream,
  }), [transport, isStream]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<DashboardV2PulseResponse>(
    '/metrics/user-dashboard/pulse',
    {
      ...dashboardV2CacheConfig,
      params,
    }
  );

  return {
    data,
    points: data?.points || [],
    error,
    loading,
    validating,
    refresh,
  };
};

/**
 * 获取用户 Dashboard v2 Token 趋势数据
 * 
 * @param filters 筛选器参数
 * @param bucket 时间桶粒度（hour 或 day）
 * @returns Token 趋势数据、加载状态、错误信息和刷新函数
 */
export const useUserDashboardTokens = (
  filters: DashboardV2FilterParams = {},
  bucket: 'hour' | 'day' = 'hour'
) => {
  const {
    timeRange = '7d',
    transport = 'all',
    isStream = 'all',
  } = filters;

  const params = useMemo(() => ({
    time_range: timeRange,
    bucket,
    transport,
    is_stream: isStream,
  }), [timeRange, bucket, transport, isStream]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<DashboardV2TokensResponse>(
    '/metrics/user-dashboard/tokens',
    {
      ...dashboardV2CacheConfig,
      params,
    }
  );

  return {
    data,
    points: data?.points || [],
    error,
    loading,
    validating,
    refresh,
  };
};

/**
 * 获取用户 Dashboard v2 Top Models 排行
 * 
 * @param filters 筛选器参数
 * @param limit 返回数量限制（默认 10）
 * @returns Top Models 数据、加载状态、错误信息和刷新函数
 */
export const useUserDashboardTopModels = (
  filters: DashboardV2FilterParams = {},
  limit: number = 10
) => {
  const {
    timeRange = '7d',
    transport = 'all',
    isStream = 'all',
  } = filters;

  const params = useMemo(() => ({
    time_range: timeRange,
    limit: limit.toString(),
    transport,
    is_stream: isStream,
  }), [timeRange, limit, transport, isStream]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<DashboardV2TopModelsResponse>(
    '/metrics/user-dashboard/top-models',
    {
      ...dashboardV2CacheConfig,
      params,
    }
  );

  return {
    data,
    items: data?.items || [],
    error,
    loading,
    validating,
    refresh,
  };
};

/**
 * 获取用户 Dashboard v2 成本结构（按 Provider）
 * 
 * @param filters 筛选器参数（不包含 transport 和 isStream）
 * @param limit 返回数量限制（默认 12）
 * @returns 成本结构数据、加载状态、错误信息和刷新函数
 */
export const useUserDashboardCostByProvider = (
  filters: Pick<DashboardV2FilterParams, 'timeRange'> = {},
  limit: number = 12
) => {
  const {
    timeRange = '7d',
  } = filters;

  const params = useMemo(() => ({
    time_range: timeRange,
    limit: limit.toString(),
  }), [timeRange, limit]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<DashboardV2CostByProviderResponse>(
    '/metrics/user-dashboard/cost-by-provider',
    {
      ...dashboardV2CacheConfig,
      params,
    }
  );

  return {
    data,
    items: data?.items || [],
    error,
    loading,
    validating,
    refresh,
  };
};

/**
 * 获取用户 Provider 卡片用的指标（按 Provider 聚合）
 *
 * @param providerIds 逗号分隔的 provider_id 列表（推荐传入：只查用户私有 provider）
 * @param filters 筛选器参数
 * @param limit 未传 providerIds 时的返回数量限制
 */
export const useUserDashboardProvidersMetrics = (
  providerIds: string | undefined,
  filters: DashboardV2FilterParams = {},
  limit: number = 12
) => {
  const {
    timeRange = '7d',
    transport = 'all',
    isStream = 'all',
  } = filters;

  const params = useMemo(() => {
    const base: Record<string, string> = {
      time_range: timeRange,
      bucket: 'hour',
      transport,
      is_stream: isStream,
    };
    if (providerIds && providerIds.trim()) {
      base.provider_ids = providerIds;
      return base;
    }
    base.limit = limit.toString();
    return base;
  }, [timeRange, transport, isStream, providerIds, limit]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<DashboardV2ProvidersMetricsResponse>(
    '/metrics/user-dashboard/providers',
    {
      ...dashboardV2CacheConfig,
      params,
    }
  );

  return {
    data,
    items: data?.items || [],
    error,
    loading,
    validating,
    refresh,
  };
};

// ============= Dashboard v2 系统页 Hooks =============

/**
 * 获取系统 Dashboard v2 KPI 指标
 * 
 * @param filters 筛选器参数
 * @returns KPI 数据、加载状态、错误信息和刷新函数
 */
export const useSystemDashboardKPIs = (filters: DashboardV2FilterParams = {}) => {
  const {
    timeRange = '7d',
    transport = 'all',
    isStream = 'all',
  } = filters;

  const params = useMemo(() => ({
    time_range: timeRange,
    transport,
    is_stream: isStream,
  }), [timeRange, transport, isStream]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<SystemKPIData>(
    '/metrics/system-dashboard/kpis',
    {
      ...dashboardV2CacheConfig,
      params,
    }
  );

  return {
    data,
    error,
    loading,
    validating,
    refresh,
  };
};

/**
 * 获取系统 Dashboard v2 Pulse 数据（近 24h，分钟粒度）
 * 
 * @param filters 筛选器参数（不包含 timeRange，固定近 24h）
 * @returns Pulse 数据、加载状态、错误信息和刷新函数
 */
export const useSystemDashboardPulse = (filters: Omit<DashboardV2FilterParams, 'timeRange'> = {}) => {
  const {
    transport = 'all',
    isStream = 'all',
  } = filters;

  const params = useMemo(() => ({
    transport,
    is_stream: isStream,
  }), [transport, isStream]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<DashboardV2PulseResponse>(
    '/metrics/system-dashboard/pulse',
    {
      ...dashboardV2CacheConfig,
      params,
    }
  );

  return {
    data,
    points: data?.points || [],
    error,
    loading,
    validating,
    refresh,
  };
};

/**
 * 获取系统 Dashboard v2 Token 趋势数据
 * 
 * @param filters 筛选器参数
 * @param bucket 时间桶粒度（hour 或 day）
 * @returns Token 趋势数据、加载状态、错误信息和刷新函数
 */
export const useSystemDashboardTokens = (
  filters: DashboardV2FilterParams = {},
  bucket: 'hour' | 'day' = 'hour'
) => {
  const {
    timeRange = '7d',
    transport = 'all',
    isStream = 'all',
  } = filters;

  const params = useMemo(() => ({
    time_range: timeRange,
    bucket,
    transport,
    is_stream: isStream,
  }), [timeRange, bucket, transport, isStream]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<DashboardV2TokensResponse>(
    '/metrics/system-dashboard/tokens',
    {
      ...dashboardV2CacheConfig,
      params,
    }
  );

  return {
    data,
    points: data?.points || [],
    error,
    loading,
    validating,
    refresh,
  };
};

/**
 * 获取系统 Dashboard v2 Top Models 排行
 * 
 * @param filters 筛选器参数
 * @param limit 返回数量限制（默认 10）
 * @returns Top Models 数据、加载状态、错误信息和刷新函数
 */
export const useSystemDashboardTopModels = (
  filters: DashboardV2FilterParams = {},
  limit: number = 10
) => {
  const {
    timeRange = '7d',
    transport = 'all',
    isStream = 'all',
  } = filters;

  const params = useMemo(() => ({
    time_range: timeRange,
    limit: limit.toString(),
    transport,
    is_stream: isStream,
  }), [timeRange, limit, transport, isStream]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<DashboardV2TopModelsResponse>(
    '/metrics/system-dashboard/top-models',
    {
      ...dashboardV2CacheConfig,
      params,
    }
  );

  return {
    data,
    items: data?.items || [],
    error,
    loading,
    validating,
    refresh,
  };
};

/**
 * 获取系统 Dashboard v2 Provider 状态列表
 * 
 * @returns Provider 状态数据、加载状态、错误信息和刷新函数
 */
export const useSystemDashboardProviders = () => {
  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<SystemDashboardProvidersResponse>(
    '/metrics/system-dashboard/providers',
    {
      ...dashboardV2CacheConfig,
    }
  );

  return {
    data,
    items: data?.items || [],
    error,
    loading,
    validating,
    refresh,
  };
};
