"use client";

import { useState, useMemo } from "react";
import { FilterBar, type TimeRange, type Transport, type StreamFilter } from "@/app/dashboard/overview/_components/filters/filter-bar";
import { HealthBadge } from "@/app/dashboard/overview/_components/badge/health-badge";
import { SystemKPICardsGrid } from "./system-kpi-cards-grid";
import {
  RequestsErrorsChart,
  LatencyPercentilesChart,
  TokenUsageChart,
} from "@/app/dashboard/overview/_components/charts";
import { TopModelsTable } from "@/app/dashboard/overview/_components/tables";
import { ProviderStatusList } from "./provider-status-list";
import { ErrorState } from "@/app/dashboard/overview/_components/error-state";
import { EmptyState } from "@/app/dashboard/overview/_components/empty-state";
import {
  useSystemDashboardKPIs,
  useSystemDashboardPulse,
  useSystemDashboardTokens,
  useSystemDashboardTopModels,
  useSystemDashboardProviders,
} from "@/lib/swr/use-dashboard-v2";
import { useI18n } from "@/lib/i18n-context";

/**
 * Dashboard 系统页 - 客户端容器组件
 * 
 * 职责：
 * - 管理筛选器状态（时间范围、传输方式、流式）
 * - 调用所有系统页 SWR Hooks 获取数据
 * - 将数据传递给各个子组件
 * - 处理加载态、错误态、空态
 * 
 * 验证需求：7.1, 7.4, 8.1, 8.2
 */
export function SystemDashboardClient() {
  const { t } = useI18n();

  // 筛选器状态
  const [timeRange, setTimeRange] = useState<TimeRange>("7d");
  const [transport, setTransport] = useState<Transport>("all");
  const [isStream, setIsStream] = useState<StreamFilter>("all");

  // 构建筛选器参数（使用 useMemo 避免重复创建对象）
  const filters = useMemo(
    () => ({
      timeRange,
      transport,
      isStream,
    }),
    [timeRange, transport, isStream]
  );

  // Pulse 筛选器（不包含 timeRange）
  const pulseFilters = useMemo(
    () => ({
      transport,
      isStream,
    }),
    [transport, isStream]
  );

  // 获取所有数据
  const kpisResult = useSystemDashboardKPIs(filters);
  const pulseResult = useSystemDashboardPulse(pulseFilters);
  const tokensResult = useSystemDashboardTokens(filters, "hour");
  const topModelsResult = useSystemDashboardTopModels(filters, 10);
  const providersResult = useSystemDashboardProviders();

  // 提取 KPI 数据
  const kpiData = kpisResult.data;
  const errorRate = kpiData?.error_rate ?? 0;
  const latencyP95Ms = kpiData?.latency_p95_ms ?? 0;

  // 计算总的估算请求数（从所有 token 数据点中累加）
  const totalEstimatedRequests = tokensResult.points.reduce(
    (sum, point) => sum + (point.estimated_requests ?? 0),
    0
  );

  return (
    <div className="space-y-6">
      {/* 顶部工具条 */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold">
            {t("dashboardV2.system.title")}
          </h1>
          <HealthBadge
            errorRate={errorRate}
            latencyP95Ms={latencyP95Ms}
            isLoading={kpisResult.loading}
          />
        </div>
        <FilterBar
          timeRange={timeRange}
          transport={transport}
          isStream={isStream}
          onTimeRangeChange={setTimeRange}
          onTransportChange={setTransport}
          onStreamChange={setIsStream}
        />
      </div>

      {/* 层级 1 - KPI 卡片（4 张） */}
      <section>
        <SystemKPICardsGrid
          data={kpiData}
          isLoading={kpisResult.loading}
          error={kpisResult.error}
        />
      </section>

      {/* 层级 2 - 核心趋势图（2 张大图并排） */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          {pulseResult.error ? (
            <ErrorState
              title={t("dashboard.errors.loadFailed")}
              message={pulseResult.error.message}
              onRetry={pulseResult.refresh}
            />
          ) : pulseResult.points.length === 0 && !pulseResult.loading ? (
            <EmptyState message={t("dashboard.errors.noData")} />
          ) : (
            <RequestsErrorsChart
              data={pulseResult.points}
              isLoading={pulseResult.loading}
            />
          )}
        </div>
        <div>
          {pulseResult.error ? (
            <ErrorState
              title={t("dashboard.errors.loadFailed")}
              message={pulseResult.error.message}
              onRetry={pulseResult.refresh}
            />
          ) : pulseResult.points.length === 0 && !pulseResult.loading ? (
            <EmptyState message={t("dashboard.errors.noData")} />
          ) : (
            <LatencyPercentilesChart
              data={pulseResult.points}
              isLoading={pulseResult.loading}
            />
          )}
        </div>
      </section>

      {/* 层级 3 - Token 使用 */}
      <section>
        {tokensResult.error ? (
          <ErrorState
            title={t("dashboard.errors.loadFailed")}
            message={tokensResult.error.message}
            onRetry={tokensResult.refresh}
          />
        ) : tokensResult.points.length === 0 && !tokensResult.loading ? (
          <EmptyState message={t("dashboard.errors.noData")} />
        ) : (
          <TokenUsageChart
            data={tokensResult.points}
            bucket="hour"
            isLoading={tokensResult.loading}
            estimatedRequests={totalEstimatedRequests}
          />
        )}
      </section>

      {/* 层级 4 - 排行榜和 Provider 状态 */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 热门模型排行榜 */}
        <div>
          {topModelsResult.error ? (
            <ErrorState
              title={t("dashboard.errors.loadFailed")}
              message={topModelsResult.error.message}
              onRetry={topModelsResult.refresh}
            />
          ) : topModelsResult.items.length === 0 && !topModelsResult.loading ? (
            <EmptyState message={t("dashboard.errors.noData")} />
          ) : (
            <TopModelsTable
              data={topModelsResult.items}
              isLoading={topModelsResult.loading}
            />
          )}
        </div>

        {/* Provider 状态列表 */}
        <div>
          <ProviderStatusList
            data={providersResult.items}
            isLoading={providersResult.loading}
            error={providersResult.error}
            onRetry={providersResult.refresh}
          />
        </div>
      </section>
    </div>
  );
}
