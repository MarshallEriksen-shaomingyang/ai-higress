"use client";

import { useI18n } from '@/lib/i18n-context';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertCircle, AlertTriangle, CheckCircle } from 'lucide-react';
import { useMemoryMetricsAlerts, type MemoryAlert } from '@/lib/swr/use-memory-metrics';

interface MemoryAlertsProps {
  timeRange?: 'today' | '7d' | '30d';
}

function AlertItem({ alert }: { alert: MemoryAlert }) {
  const { t } = useI18n();

  const SeverityIcon = alert.severity === 'critical' ? AlertCircle : AlertTriangle;
  const severityStyles = {
    critical: 'bg-red-50 border-red-200 dark:bg-red-950/50 dark:border-red-800',
    warning: 'bg-yellow-50 border-yellow-200 dark:bg-yellow-950/50 dark:border-yellow-800',
  };
  const iconStyles = {
    critical: 'text-red-600 dark:text-red-400',
    warning: 'text-yellow-600 dark:text-yellow-400',
  };

  const formatValue = (type: string, value: number) => {
    if (type.includes('rate')) {
      return `${(value * 100).toFixed(1)}%`;
    }
    if (type.includes('latency')) {
      return `${value.toFixed(0)}ms`;
    }
    return value.toFixed(1);
  };

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${severityStyles[alert.severity]}`}>
      <SeverityIcon className={`h-5 w-5 mt-0.5 ${iconStyles[alert.severity]}`} />
      <div className="flex-1 min-w-0">
        <div className="font-medium text-sm">{alert.message}</div>
        <div className="text-xs text-muted-foreground mt-1">
          {t('memory_metrics.current')}: {formatValue(alert.alert_type, alert.current_value)} | {t('memory_metrics.threshold')}: {formatValue(alert.alert_type, alert.threshold)}
        </div>
      </div>
      <span className={`text-xs font-medium px-2 py-0.5 rounded ${
        alert.severity === 'critical'
          ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
          : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'
      }`}>
        {alert.severity.toUpperCase()}
      </span>
    </div>
  );
}

export function MemoryAlerts({ timeRange = 'today' }: MemoryAlertsProps) {
  const { t } = useI18n();
  const { data, loading, error } = useMemoryMetricsAlerts({ timeRange });

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-48" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('memory_metrics.alerts')}</CardTitle>
        </CardHeader>
        <CardContent className="text-center text-muted-foreground">
          {t('common.error_loading_data')}
        </CardContent>
      </Card>
    );
  }

  const hasAlerts = data.alerts.length > 0;
  const criticalCount = data.alerts.filter(a => a.severity === 'critical').length;
  const warningCount = data.alerts.filter(a => a.severity === 'warning').length;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              {hasAlerts ? (
                criticalCount > 0 ? (
                  <AlertCircle className="h-5 w-5 text-red-500" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-yellow-500" />
                )
              ) : (
                <CheckCircle className="h-5 w-5 text-green-500" />
              )}
              {t('memory_metrics.alerts')}
            </CardTitle>
            <CardDescription>
              {hasAlerts
                ? `${criticalCount} critical, ${warningCount} warning`
                : t('memory_metrics.no_alerts')
              }
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {hasAlerts ? (
          <div className="space-y-3">
            {data.alerts.map((alert, index) => (
              <AlertItem key={`${alert.alert_type}-${index}`} alert={alert} />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <CheckCircle className="h-12 w-12 mx-auto mb-3 text-green-500" />
            <p>{t('memory_metrics.all_metrics_normal')}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
