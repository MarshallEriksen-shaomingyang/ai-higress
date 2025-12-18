"use client";

import { useMemo } from "react";
import {
  UserOverviewMetricsSummary,
  UserOverviewActiveProviders,
  UserOverviewMetricsTimeSeries,
  UserOverviewAppUsage,
} from "@/lib/api-types";
import { useApiGet } from "./hooks";

export type UserOverviewTimeRange = "today" | "7d" | "30d" | "all";
export type UserOverviewTransport = "http" | "sdk" | "all";
export type UserOverviewStreamFlag = "true" | "false" | "all";

export interface UseUserOverviewParams {
  time_range?: UserOverviewTimeRange;
  transport?: UserOverviewTransport;
  is_stream?: UserOverviewStreamFlag;
  limit?: number;
}

export function useUserOverviewSummary(params: UseUserOverviewParams = {}) {
  const {
    time_range = "7d",
    transport = "all",
    is_stream = "all",
  } = params;

  const { data, error, loading, validating, refresh } = useApiGet<UserOverviewMetricsSummary>(
    "/metrics/user-overview/summary",
    {
      strategy: "frequent",
      params: {
        time_range,
        transport,
        is_stream,
      },
    }
  );

  const summary = useMemo(() => data, [data]);
  return { summary, error, loading, validating, refresh };
}

export function useUserOverviewProviders(params: UseUserOverviewParams = {}) {
  const {
    time_range = "7d",
    transport = "all",
    is_stream = "all",
    limit = 4,
  } = params;

  const { data, error, loading, validating, refresh } = useApiGet<UserOverviewActiveProviders>(
    "/metrics/user-overview/providers",
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

  const providers = useMemo(() => data, [data]);
  return { providers, error, loading, validating, refresh };
}

export function useUserOverviewActivity(params: UseUserOverviewParams = {}) {
  const {
    time_range = "7d",
    transport = "all",
    is_stream = "all",
  } = params;

  const { data, error, loading, validating, refresh } = useApiGet<UserOverviewMetricsTimeSeries>(
    "/metrics/user-overview/timeseries",
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
  return { activity, error, loading, validating, refresh };
}

export function useUserOverviewApps(params: UseUserOverviewParams = {}) {
  const {
    time_range = "7d",
    limit = 10,
  } = params;

  const { data, error, loading, validating, refresh } = useApiGet<UserOverviewAppUsage>(
    "/metrics/user-overview/apps",
    {
      strategy: "frequent",
      params: {
        time_range,
        limit,
      },
    }
  );

  const apps = useMemo(() => data, [data]);
  return { apps, error, loading, validating, refresh };
}

export function useUserSuccessRateTrend(params: UseUserOverviewParams = {}) {
  const { activity, ...rest } = useUserOverviewActivity(params);
  return { trend: activity, ...rest };
}
