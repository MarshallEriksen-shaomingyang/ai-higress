"use client";

import React, { useMemo } from "react";
import { Activity, Server, Database } from "lucide-react";
import { StatCard } from "../common";
import { useOverviewMetrics } from "@/lib/swr/use-overview-metrics";

function formatNumber(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }
  return value.toString();
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function computeChange(
  current: number,
  previous: number | null
): { text: string; trend: "up" | "down" } {
  if (previous === null || previous <= 0) {
    // 没有上一周期数据时，仅展示当前值，不标明显著涨跌
    return { text: "--", trend: "up" };
  }
  const delta = (current - previous) / previous;
  const percent = (delta * 100).toFixed(1);
  const trend: "up" | "down" = delta >= 0 ? "up" : "down";
  const sign = delta >= 0 ? "+" : "";
  return { text: `${sign}${percent}%`, trend };
}

export function StatsGrid() {
  // 概览页聚焦“今天”的运行情况
  const { overview } = useOverviewMetrics({ time_range: "today" });

  const cards = useMemo(() => {
    if (!overview) {
      // 初始加载或发生错误时保留占位布局
      return [
        {
          titleKey: "overview.total_requests",
          value: "--",
          change: "--",
          trend: "up" as const,
          icon: Activity,
        },
        {
          titleKey: "overview.active_providers",
          value: "--",
          change: "--",
          trend: "up" as const,
          icon: Server,
        },
        {
          titleKey: "overview.success_rate",
          value: "--",
          change: "--",
          trend: "up" as const,
          icon: Database,
        },
      ];
    }

    const totalChange = computeChange(
      overview.total_requests,
      overview.total_requests_prev
    );
    const providerChange = computeChange(
      overview.active_providers,
      overview.active_providers_prev
    );
    const successChange = computeChange(
      overview.success_rate,
      overview.success_rate_prev
    );

    return [
      {
        titleKey: "overview.total_requests",
        value: formatNumber(overview.total_requests),
        change: totalChange.text,
        trend: totalChange.trend,
        icon: Activity,
      },
      {
        titleKey: "overview.active_providers",
        value: overview.active_providers.toString(),
        change: providerChange.text,
        trend: providerChange.trend,
        icon: Server,
      },
      {
        titleKey: "overview.success_rate",
        value: formatPercent(overview.success_rate),
        change: successChange.text,
        trend: successChange.trend,
        icon: Database,
      },
    ];
  }, [overview]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {cards.map((stat, index) => (
        <StatCard
          key={index}
          titleKey={stat.titleKey}
          value={stat.value}
          change={stat.change}
          trend={stat.trend}
          icon={stat.icon}
        />
      ))}
    </div>
  );
}
