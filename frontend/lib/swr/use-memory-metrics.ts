"use client";

import { useMemo } from 'react';
import { useApiGet } from './hooks';

/**
 * Memory metrics filter parameters
 */
export interface MemoryMetricsFilterParams {
  timeRange?: 'today' | '7d' | '30d';
  granularity?: 'minute' | 'hour';
}

/**
 * Memory metrics KPI data structure
 */
export interface MemoryMetricsKpis {
  time_range: string;
  total_requests: number;
  retrieval_triggered: number;
  retrieval_skipped: number;
  trigger_rate: number;
  hit_rate: number;
  retrieval_latency_avg_ms: number;
  retrieval_latency_p95_ms: number;
  memory_hits: number;
  memory_misses: number;
  routing_requests: number;
  routing_stored_user: number;
  routing_stored_system: number;
  routing_skipped: number;
  session_count: number;
  avg_backlog_per_session: number;
  backlog_batches_max: number;
}

/**
 * Memory metrics data point for time series
 */
export interface MemoryMetricsDataPoint {
  window_start: string;
  total_requests: number;
  retrieval_triggered: number;
  memory_hits: number;
  memory_misses: number;
  trigger_rate: number;
  hit_rate: number;
  retrieval_latency_avg_ms: number;
  routing_requests: number;
  avg_backlog_per_session: number;
}

/**
 * Memory metrics pulse (time series) response
 */
export interface MemoryMetricsPulse {
  time_range: string;
  granularity: string;
  points: MemoryMetricsDataPoint[];
}

/**
 * Memory alert thresholds
 */
export interface MemoryAlertThresholds {
  trigger_rate_low: number;
  trigger_rate_high: number;
  hit_rate_low: number;
  latency_p95_high_ms: number;
  backlog_per_session_high: number;
}

/**
 * Memory alert
 */
export interface MemoryAlert {
  alert_type: string;
  severity: 'warning' | 'critical';
  current_value: number;
  threshold: number;
  message: string;
  window_start: string;
}

/**
 * Memory metrics alerts response
 */
export interface MemoryMetricsAlerts {
  time_range: string;
  thresholds: MemoryAlertThresholds;
  alerts: MemoryAlert[];
}

/**
 * Combined memory metrics dashboard data
 */
export interface MemoryMetricsDashboard {
  kpis: MemoryMetricsKpis;
  pulse: MemoryMetricsPulse;
  alerts: MemoryMetricsAlerts;
}

/**
 * Cache configuration for memory metrics
 */
const memoryMetricsCacheConfig = {
  revalidateOnFocus: false,
  revalidateOnReconnect: true,
  refreshInterval: 60000, // 60s
  dedupingInterval: 5000,
};

/**
 * Hook to fetch memory metrics KPIs
 */
export const useMemoryMetricsKpis = (filters: MemoryMetricsFilterParams = {}) => {
  const { timeRange = '7d' } = filters;

  const params = useMemo(() => ({
    time_range: timeRange,
  }), [timeRange]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<MemoryMetricsKpis>(
    '/metrics/memory/kpis',
    {
      ...memoryMetricsCacheConfig,
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
 * Hook to fetch memory metrics pulse (time series)
 */
export const useMemoryMetricsPulse = (filters: MemoryMetricsFilterParams = {}) => {
  const { timeRange = '7d', granularity = 'hour' } = filters;

  const params = useMemo(() => ({
    time_range: timeRange,
    granularity,
  }), [timeRange, granularity]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<MemoryMetricsPulse>(
    '/metrics/memory/pulse',
    {
      ...memoryMetricsCacheConfig,
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
 * Hook to fetch memory metrics alerts
 */
export const useMemoryMetricsAlerts = (filters: MemoryMetricsFilterParams = {}) => {
  const { timeRange = 'today' } = filters;

  const params = useMemo(() => ({
    time_range: timeRange,
  }), [timeRange]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<MemoryMetricsAlerts>(
    '/metrics/memory/alerts',
    {
      ...memoryMetricsCacheConfig,
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
 * Hook to fetch combined memory metrics dashboard
 */
export const useMemoryMetricsDashboard = (filters: MemoryMetricsFilterParams = {}) => {
  const { timeRange = '7d' } = filters;

  const params = useMemo(() => ({
    time_range: timeRange,
  }), [timeRange]);

  const {
    data,
    error,
    loading,
    validating,
    refresh,
  } = useApiGet<MemoryMetricsDashboard>(
    '/metrics/memory/dashboard',
    {
      ...memoryMetricsCacheConfig,
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
