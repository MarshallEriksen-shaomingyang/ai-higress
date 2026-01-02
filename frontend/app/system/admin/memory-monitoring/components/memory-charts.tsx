"use client";

import { useMemo } from 'react';
import { useI18n } from '@/lib/i18n-context';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useMemoryMetricsPulse, type MemoryMetricsDataPoint } from '@/lib/swr/use-memory-metrics';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Area,
  AreaChart,
} from 'recharts';
import { format } from 'date-fns';

interface MemoryChartsProps {
  timeRange?: 'today' | '7d' | '30d';
}

function ChartSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-4 w-60" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-[300px] w-full" />
      </CardContent>
    </Card>
  );
}

export function MemoryCharts({ timeRange = '7d' }: MemoryChartsProps) {
  const { t } = useI18n();
  const granularity = timeRange === 'today' ? 'minute' : 'hour';
  const { data, loading, error } = useMemoryMetricsPulse({ timeRange, granularity });

  const chartData = useMemo(() => {
    if (!data?.points) return [];
    return data.points.map((point) => ({
      ...point,
      time: format(new Date(point.window_start), timeRange === 'today' ? 'HH:mm' : 'MM/dd HH:mm'),
      trigger_rate_pct: point.trigger_rate * 100,
      hit_rate_pct: point.hit_rate * 100,
    }));
  }, [data?.points, timeRange]);

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <ChartSkeleton />
        <ChartSkeleton />
      </div>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          {t('common.error_loading_data')}
        </CardContent>
      </Card>
    );
  }

  if (chartData.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          {t('memory_metrics.no_data')}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {/* Trigger Rate & Hit Rate Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('memory_metrics.rates_trend')}</CardTitle>
          <CardDescription>{t('memory_metrics.rates_description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `${value}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--popover))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                }}
                formatter={(value: number) => `${value.toFixed(1)}%`}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="trigger_rate_pct"
                name={t('memory_metrics.trigger_rate')}
                stroke="hsl(var(--primary))"
                fill="hsl(var(--primary))"
                fillOpacity={0.1}
                strokeWidth={2}
              />
              <Area
                type="monotone"
                dataKey="hit_rate_pct"
                name={t('memory_metrics.hit_rate')}
                stroke="hsl(142.1 76.2% 36.3%)"
                fill="hsl(142.1 76.2% 36.3%)"
                fillOpacity={0.1}
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Latency Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('memory_metrics.latency_trend')}</CardTitle>
          <CardDescription>{t('memory_metrics.latency_description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `${value}ms`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--popover))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                }}
                formatter={(value: number) => `${value.toFixed(0)}ms`}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="retrieval_latency_avg_ms"
                name={t('memory_metrics.avg_latency')}
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Requests Volume Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('memory_metrics.requests_trend')}</CardTitle>
          <CardDescription>{t('memory_metrics.requests_description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--popover))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                }}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="total_requests"
                name={t('memory_metrics.total_requests')}
                stroke="hsl(var(--muted-foreground))"
                fill="hsl(var(--muted))"
                fillOpacity={0.5}
                strokeWidth={1}
              />
              <Area
                type="monotone"
                dataKey="retrieval_triggered"
                name={t('memory_metrics.retrieval_triggered')}
                stroke="hsl(var(--primary))"
                fill="hsl(var(--primary))"
                fillOpacity={0.3}
                strokeWidth={2}
              />
              <Area
                type="monotone"
                dataKey="memory_hits"
                name={t('memory_metrics.hits')}
                stroke="hsl(142.1 76.2% 36.3%)"
                fill="hsl(142.1 76.2% 36.3%)"
                fillOpacity={0.3}
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Backlog Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('memory_metrics.backlog_trend')}</CardTitle>
          <CardDescription>{t('memory_metrics.backlog_description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--popover))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                }}
                formatter={(value: number) => value.toFixed(1)}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="avg_backlog_per_session"
                name={t('memory_metrics.avg_backlog')}
                stroke="hsl(38.3 95.8% 51.8%)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
