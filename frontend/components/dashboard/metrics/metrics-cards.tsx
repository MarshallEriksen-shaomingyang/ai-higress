"use client";

import React, { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Activity, Server, TrendingUp, AlertTriangle } from "lucide-react";
import { useOverviewMetrics } from "@/lib/swr/use-overview-metrics";
import { useI18n } from "@/lib/i18n-context";

interface MetricProps {
  title: string;
  value: string;
  change: string;
  icon: React.ElementType;
}

function Metric({ title, value, change, icon: Icon }: MetricProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
              {title}
            </p>
            <h3 className="text-2xl font-bold mt-2">{value}</h3>
            <p className="text-sm text-muted-foreground mt-1">{change}</p>
          </div>
          <div className="p-2 bg-muted rounded">
            <Icon className="w-5 h-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function formatNumber(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }
  return value.toString();
}

function formatPercent01(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function computeChange(
  current: number,
  previous: number | null,
  t: (key: string) => string
): string {
  if (previous === null || previous <= 0) {
    return t("metrics.overview.change.na");
  }
  const delta = (current - previous) / previous;
  const sign = delta >= 0 ? "+" : "";
  const percent = (delta * 100).toFixed(1);
  return `${t("metrics.overview.change.prefix")}${sign}${percent}%`;
}

export function MetricsCards() {
  const { t } = useI18n();
  const { overview } = useOverviewMetrics({ time_range: "7d" });

  const metrics = useMemo<MetricProps[]>(() => {
    if (!overview) {
      return [
        {
          title: t("metrics.overview.card.total_requests"),
          value: "--",
          change: t("metrics.overview.change.na"),
          icon: Activity,
        },
        {
          title: t("metrics.overview.card.active_providers"),
          value: "--",
          change: t("metrics.overview.change.na"),
          icon: Server,
        },
        {
          title: t("metrics.overview.card.success_rate"),
          value: "--",
          change: t("metrics.overview.change.na"),
          icon: TrendingUp,
        },
        {
          title: t("metrics.overview.card.error_rate"),
          value: "--",
          change: t("metrics.overview.change.na"),
          icon: AlertTriangle,
        },
      ];
    }

    const totalRequests = overview.total_requests;
    const activeProviders = overview.active_providers;
    const successRate = overview.success_rate;
    const errorRate = totalRequests > 0 ? overview.error_requests / totalRequests : 0;

    const totalChange = computeChange(
      totalRequests,
      overview.total_requests_prev,
      t
    );
    const providerChange = computeChange(
      activeProviders,
      overview.active_providers_prev,
      t
    );
    const successChange = computeChange(
      successRate,
      overview.success_rate_prev,
      t
    );
    const errorChange = computeChange(
      errorRate,
      overview.error_requests_prev !== null && overview.total_requests_prev
        ? overview.error_requests_prev / overview.total_requests_prev
        : null,
      t
    );

    return [
      {
        title: t("metrics.overview.card.total_requests"),
        value: formatNumber(totalRequests),
        change: totalChange,
        icon: Activity,
      },
      {
        title: t("metrics.overview.card.active_providers"),
        value: activeProviders.toString(),
        change: providerChange,
        icon: Server,
      },
      {
        title: t("metrics.overview.card.success_rate"),
        value: formatPercent01(successRate),
        change: successChange,
        icon: TrendingUp,
      },
      {
        title: t("metrics.overview.card.error_rate"),
        value: formatPercent01(errorRate),
        change: errorChange,
        icon: AlertTriangle,
      },
    ];
  }, [overview, t]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {metrics.map((metric, index) => (
        <Metric
          key={index}
          title={metric.title}
          value={metric.value}
          change={metric.change}
          icon={metric.icon}
        />
      ))}
    </div>
  );
}
