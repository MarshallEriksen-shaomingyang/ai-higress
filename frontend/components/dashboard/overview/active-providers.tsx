"use client";

import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { ProviderStatusCard } from "../common";
import { useI18n } from "@/lib/i18n-context";
import { useActiveProvidersOverview } from "@/lib/swr/use-overview-metrics";

function formatLatency(latencyMs: number | null): string {
  if (latencyMs == null) {
    return "--";
  }
  return `${Math.round(latencyMs)}ms`;
}

function formatSuccessRate(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

function getStatusKey(successRate: number, latencyP95Ms: number | null): string {
  const latency = latencyP95Ms ?? 0;
  // 简单规则：高成功率且延迟较低视为"健康"，否则视为"性能下降"
  if (successRate >= 0.98 && latency <= 800) {
    return "overview.status_healthy";
  }
  return "overview.status_degraded";
}

import { OverviewTimeRange } from "@/lib/swr/use-overview-metrics";

interface ActiveProvidersProps {
  timeRange?: OverviewTimeRange;
}

export function ActiveProviders({ timeRange = "today" }: ActiveProvidersProps) {
  const { t } = useI18n();
  // 根据传入的时间范围获取活跃 Provider 数据
  const { data, loading } = useActiveProvidersOverview({
    time_range: timeRange,
  });

  const providers = useMemo(() => {
    if (!data) {
      return [];
    }
    return data.items.map((item) => ({
      name: item.provider_id,
      statusKey: getStatusKey(item.success_rate, item.latency_p95_ms),
      latency: formatLatency(item.latency_p95_ms),
      success: formatSuccessRate(item.success_rate),
    }));
  }, [data]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-medium">{t("dashboard.active_providers")}</h2>
        <a href="/dashboard/metrics/providers">
          <Button size="sm" variant="ghost" className="h-8 text-xs">
            {t("overview.view_all")}
          </Button>
        </a>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {loading && providers.length === 0 ? (
          // 初次加载时的简单占位
          <>
            <ProviderStatusCard
              name="..."
              statusKey="overview.status_healthy"
              latency="--"
              success="--"
            />
          </>
        ) : (
          providers.map((provider, index) => (
            <ProviderStatusCard
              key={index}
              name={provider.name}
              statusKey={provider.statusKey}
              latency={provider.latency}
              success={provider.success}
            />
          ))
        )}
      </div>
    </div>
  );
}
