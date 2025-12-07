"use client";

import { useMemo } from "react";
import type {
  OverviewActiveProviders,
  OverviewMetricsSummary,
  OverviewMetricsTimeSeries,
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
