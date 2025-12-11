"use client";

import { useMemo } from "react";
import type {
  OverviewActiveProviders,
  OverviewMetricsSummary,
  OverviewMetricsTimeSeries,
  ActiveModelsResponse,
  OverviewEventsResponse,
} from "@/lib/api-types";
import { useApiGet } from "./hooks";

export type OverviewTimeRange = "today" | "7d" | "30d" | "all";
export type OverviewTransport = "http" | "sdk" | "all";
export type OverviewStreamFlag = "true" | "false" | "all";

export interface UseOverviewMetricsParams {
  time_range?: OverviewTimeRange;
  transport?: OverviewTransport;
  is_stream?: OverviewStreamFlag;
  // 仅在 useActiveProvidersOverview 中使用
  limit?: number;
}

export function useOverviewMetrics(
  params: UseOverviewMetricsParams = {}
) {
  const {
    time_range = "7d",
    transport = "all",
    is_stream = "all",
  } = params;

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<OverviewMetricsSummary>(
    "/metrics/overview/summary",
    {
      strategy: "frequent",
      params: {
        time_range,
        transport,
        is_stream,
      },
    }
  );

  const overview = useMemo(() => data, [data]);

  return {
    overview,
    error,
    loading,
    validating,
    refresh,
  };
}

export type UseOverviewMetricsResult = ReturnType<typeof useOverviewMetrics>;

export function useActiveProvidersOverview(
  params: UseOverviewMetricsParams = {}
) {
  const {
    time_range = "7d",
    transport = "all",
    is_stream = "all",
    limit = 4,
  } = params;

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<OverviewActiveProviders>(
    "/metrics/overview/providers",
    {
      strategy: "frequent",
      params: {
        time_range,
        transport,
        is_stream,
        limit,
      },
    }
  );

  const activeProviders = useMemo(() => data, [data]);

  return {
    data: activeProviders,
    error,
    loading,
    validating,
    refresh,
  };
}

export function useOverviewActivity(
  params: UseOverviewMetricsParams = {}
) {
  const {
    time_range = "7d",
    transport = "all",
    is_stream = "all",
  } = params;

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<OverviewMetricsTimeSeries>(
    "/metrics/overview/timeseries",
    {
      strategy: "frequent",
      params: {
        time_range,
        transport,
        is_stream,
        bucket: "minute",
      },
    }
  );

  const activity = useMemo(() => data, [data]);

  return {
    activity,
    error,
    loading,
    validating,
    refresh,
  };
}

export type UseOverviewActivityResult = ReturnType<typeof useOverviewActivity>;

/**
 * 获取活跃模型列表（调用最多、失败最多）
 */
export function useActiveModels(
  params: UseOverviewMetricsParams = {}
) {
  const {
    time_range = "7d",
    transport = "all",
    is_stream = "all",
  } = params;

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<ActiveModelsResponse>(
    "/metrics/overview/active-models",
    {
      strategy: "static",
      params: {
        time_range,
        transport,
        is_stream,
      },
    }
  );

  const models = useMemo(() => data, [data]);

  return {
    models,
    error,
    loading,
    validating,
    refresh,
  };
}

export type UseActiveModelsResult = ReturnType<typeof useActiveModels>;

/**
 * 获取事件流（限流、错误等关键事件）
 */
export function useOverviewEvents(
  params: UseOverviewMetricsParams = {}
) {
  const {
    time_range = "7d",
    transport = "all",
    is_stream = "all",
  } = params;

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<OverviewEventsResponse>(
    "/metrics/overview/events",
    {
      strategy: "frequent",
      params: {
        time_range,
        transport,
        is_stream,
      },
    }
  );

  const events = useMemo(() => data?.events || [], [data]);

  return {
    events,
    error,
    loading,
    validating,
    refresh,
  };
}

export type UseOverviewEventsResult = ReturnType<typeof useOverviewEvents>;

/**
 * 获取成功率趋势数据（复用 timeseries 端点）
 * 
 * 注意：此 hook 复用 /metrics/overview/timeseries 端点，
 * 该端点已包含成功率计算所需的所有数据点。
 */
export function useSuccessRateTrend(
  params: UseOverviewMetricsParams = {}
) {
  const {
    time_range = "7d",
    transport = "all",
    is_stream = "all",
  } = params;

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<OverviewMetricsTimeSeries>(
    "/metrics/overview/timeseries",
    {
      strategy: "frequent",
      params: {
        time_range,
        transport,
        is_stream,
        bucket: "minute",
      },
    }
  );

  const trend = useMemo(() => data, [data]);

  return {
    trend,
    error,
    loading,
    validating,
    refresh,
  };
}

export type UseSuccessRateTrendResult = ReturnType<typeof useSuccessRateTrend>;
