"use client";

import { useI18n } from '@/lib/i18n-context';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { TrendingUp, TrendingDown, Minus, Activity, Target, Clock, AlertTriangle, Database } from 'lucide-react';
import { useMemoryMetricsKpis, type MemoryMetricsKpis } from '@/lib/swr/use-memory-metrics';

interface KpiCardProps {
  title: string;
  value: string | number;
  description?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendLabel?: string;
  icon?: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger';
}

function KpiCard({ title, value, description, trend, trendLabel, icon, variant = 'default' }: KpiCardProps) {
  const variantStyles = {
    default: 'text-foreground',
    success: 'text-green-600 dark:text-green-400',
    warning: 'text-yellow-600 dark:text-yellow-400',
    danger: 'text-red-600 dark:text-red-400',
  };

  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon && <div className="text-muted-foreground">{icon}</div>}
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${variantStyles[variant]}`}>{value}</div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
          {trend && (
            <span className={`flex items-center ${trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : ''}`}>
              <TrendIcon className="h-3 w-3 mr-1" />
              {trendLabel}
            </span>
          )}
          {description && <span>{description}</span>}
        </div>
      </CardContent>
    </Card>
  );
}

function KpiCardSkeleton() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-4 rounded-full" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-8 w-20 mb-2" />
        <Skeleton className="h-3 w-32" />
      </CardContent>
    </Card>
  );
}

interface MemoryKpiCardsProps {
  timeRange?: 'today' | '7d' | '30d';
}

export function MemoryKpiCards({ timeRange = '7d' }: MemoryKpiCardsProps) {
  const { t } = useI18n();
  const { data, loading, error } = useMemoryMetricsKpis({ timeRange });

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <KpiCardSkeleton key={i} />
        ))}
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

  const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;
  const formatMs = (value: number) => `${value.toFixed(0)}ms`;
  const formatNumber = (value: number) => value.toLocaleString();

  // Determine variants based on thresholds
  const getTriggerRateVariant = (rate: number) => {
    if (rate < 0.1) return 'warning';
    if (rate > 0.9) return 'warning';
    return 'success';
  };

  const getHitRateVariant = (rate: number) => {
    if (rate < 0.3) return 'danger';
    if (rate < 0.5) return 'warning';
    return 'success';
  };

  const getLatencyVariant = (latency: number) => {
    if (latency > 500) return 'danger';
    if (latency > 200) return 'warning';
    return 'success';
  };

  const getBacklogVariant = (backlog: number) => {
    if (backlog > 10) return 'danger';
    if (backlog > 5) return 'warning';
    return 'success';
  };

  return (
    <div className="space-y-4">
      {/* Primary KPIs */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title={t('memory_metrics.trigger_rate')}
          value={formatPercent(data.trigger_rate)}
          description={`${formatNumber(data.retrieval_triggered)} / ${formatNumber(data.total_requests)}`}
          icon={<Target className="h-4 w-4" />}
          variant={getTriggerRateVariant(data.trigger_rate)}
        />
        <KpiCard
          title={t('memory_metrics.hit_rate')}
          value={formatPercent(data.hit_rate)}
          description={`${formatNumber(data.memory_hits)} hits`}
          icon={<Activity className="h-4 w-4" />}
          variant={getHitRateVariant(data.hit_rate)}
        />
        <KpiCard
          title={t('memory_metrics.latency_p95')}
          value={formatMs(data.retrieval_latency_p95_ms)}
          description={`avg: ${formatMs(data.retrieval_latency_avg_ms)}`}
          icon={<Clock className="h-4 w-4" />}
          variant={getLatencyVariant(data.retrieval_latency_p95_ms)}
        />
        <KpiCard
          title={t('memory_metrics.avg_backlog')}
          value={data.avg_backlog_per_session.toFixed(1)}
          description={`max: ${data.backlog_batches_max}`}
          icon={<AlertTriangle className="h-4 w-4" />}
          variant={getBacklogVariant(data.avg_backlog_per_session)}
        />
      </div>

      {/* Secondary KPIs */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title={t('memory_metrics.total_requests')}
          value={formatNumber(data.total_requests)}
          description={t('memory_metrics.in_period')}
          icon={<Database className="h-4 w-4" />}
        />
        <KpiCard
          title={t('memory_metrics.routing_user')}
          value={formatNumber(data.routing_stored_user)}
          description={`${formatNumber(data.routing_requests)} total`}
        />
        <KpiCard
          title={t('memory_metrics.routing_system')}
          value={formatNumber(data.routing_stored_system)}
          description={`${formatNumber(data.routing_skipped)} skipped`}
        />
        <KpiCard
          title={t('memory_metrics.sessions')}
          value={formatNumber(data.session_count)}
          description={t('memory_metrics.unique_sessions')}
        />
      </div>
    </div>
  );
}
