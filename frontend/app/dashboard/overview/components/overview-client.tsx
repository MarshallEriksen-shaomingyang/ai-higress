"use client";

import { useState } from "react";
import { OverviewTimeRange } from "@/lib/swr/use-overview-metrics";
import { FilterBar } from "@/components/dashboard/overview/filter-bar";
import { StatsGrid } from "@/components/dashboard/overview/stats-grid";
import { MetricsGrid } from "@/components/dashboard/overview/metrics-grid";
import { ConsumptionSummaryCard } from "@/components/dashboard/overview/consumption-summary-card";
import { ProviderRankingCard } from "@/components/dashboard/overview/provider-ranking-card";
import { SuccessRateTrendCard } from "@/components/dashboard/overview/success-rate-trend-card";
import { ActiveProviders } from "@/components/dashboard/overview/active-providers";
import { RecentActivity } from "@/components/dashboard/overview/recent-activity";

/**
 * 客户端包装器组件
 * 负责管理客户端状态、事件处理和数据获取
 *
 * 职责：
 * - 管理时间范围筛选器状态
 * - 将时间范围传递给各个数据卡片组件
 * - 协调筛选器与数据更新的联动
 */
export function OverviewClient() {
  const [timeRange, setTimeRange] = useState<OverviewTimeRange>("7d");

  const handleTimeRangeChange = (range: OverviewTimeRange) => {
    setTimeRange(range);
  };

  return (
    <>
      {/* 时间范围筛选器 */}
      <FilterBar onTimeRangeChange={handleTimeRangeChange} />

      {/* Stats Grid */}
      <StatsGrid timeRange={timeRange} />

      {/* 响应式指标网格 - 包含主要卡片 */}
      <MetricsGrid>
        {/* 积分消耗概览卡片 */}
        <ConsumptionSummaryCard timeRange={timeRange} />

        {/* Provider 消耗排行榜卡片 */}
        <ProviderRankingCard timeRange={timeRange} />

        {/* 成功率趋势卡片 */}
        <SuccessRateTrendCard timeRange={timeRange} />
      </MetricsGrid>

      {/* Active Providers */}
      <ActiveProviders timeRange={timeRange} />

      {/* Recent Activity */}
      <RecentActivity timeRange={timeRange} />
    </>
  );
}
