"use client";

import { useState, useEffect } from 'react';
import { useI18n } from '@/lib/i18n-context';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowRight, Activity, AlertTriangle, CheckCircle } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useMemoryMetricsAlerts } from '@/lib/swr/use-memory-metrics';

/**
 * Memory Monitoring Entry Card (System Admin Page)
 */
export function MemoryMonitoringCard() {
  const { t } = useI18n();
  const router = useRouter();
  const { data: alertsData, loading } = useMemoryMetricsAlerts({ timeRange: 'today' });
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleNavigate = () => {
    router.push('/system/admin/memory-monitoring');
  };

  const hasAlerts = alertsData?.alerts && alertsData.alerts.length > 0;
  const criticalCount = alertsData?.alerts?.filter(a => a.severity === 'critical').length || 0;
  const warningCount = alertsData?.alerts?.filter(a => a.severity === 'warning').length || 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <CardTitle className="text-lg font-normal">
            {t('system.memory_monitoring.card_title')}
          </CardTitle>
          {mounted && !loading && (
            hasAlerts ? (
              <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300">
                <AlertTriangle className="h-3 w-3" />
                {criticalCount > 0 ? `${criticalCount} critical` : `${warningCount} warning`}
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                <CheckCircle className="h-3 w-3" />
                OK
              </span>
            )
          )}
        </div>
        <CardDescription>
          {t('system.memory_monitoring.card_description')}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button variant="outline" size="sm" onClick={handleNavigate}>
          {t('system.memory_monitoring.view_dashboard')}
          <ArrowRight className="h-4 w-4 ml-2" />
        </Button>
      </CardContent>
    </Card>
  );
}
