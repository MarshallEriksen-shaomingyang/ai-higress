"use client";

import { useState } from 'react';
import { useI18n } from '@/lib/i18n-context';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { RefreshCw, Brain } from 'lucide-react';
import { MemoryKpiCards } from './memory-kpi-cards';
import { MemoryAlerts } from './memory-alerts';
import { MemoryCharts } from './memory-charts';

type TimeRange = 'today' | '7d' | '30d';

export function MemoryMonitoringClient() {
  const { t } = useI18n();
  const [timeRange, setTimeRange] = useState<TimeRange>('7d');
  const [refreshKey, setRefreshKey] = useState(0);

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  return (
    <div className="space-y-6" key={refreshKey}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">{t('memory_metrics.title')}</h1>
            <p className="text-muted-foreground">{t('memory_metrics.subtitle')}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Tabs value={timeRange} onValueChange={(v) => setTimeRange(v as TimeRange)}>
            <TabsList>
              <TabsTrigger value="today">{t('common.today')}</TabsTrigger>
              <TabsTrigger value="7d">{t('common.7_days')}</TabsTrigger>
              <TabsTrigger value="30d">{t('common.30_days')}</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="h-4 w-4 mr-2" />
            {t('common.refresh')}
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <MemoryKpiCards timeRange={timeRange} />

      {/* Alerts Section */}
      <MemoryAlerts timeRange={timeRange} />

      {/* Charts Section */}
      <MemoryCharts timeRange={timeRange} />
    </div>
  );
}
