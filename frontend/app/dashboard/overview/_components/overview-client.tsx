"use client";

import { useState, useMemo, memo } from "react";
import { FilterBar, type TimeRange, type Transport, type StreamFilter } from "./filters/filter-bar";
import { HealthBadge } from "./badge/health-badge";
import { KPICardsGrid } from "./kpis/kpi-cards-grid";
import {
  RequestsErrorsChart,
  LatencyPercentilesChart,
  TokenUsageChart,
  CostByProviderChart,
  AppsUsageChart,
} from "./charts";
import { TopModelsTable } from "./tables";
import { ErrorState } from "./error-state";
import { EmptyState } from "./empty-state";
import {
  useUserDashboardKPIs,
  useUserDashboardPulse,
  useUserDashboardTokens,
  useUserDashboardTopModels,
  useUserDashboardCostByProvider,
} from "@/lib/swr/use-dashboard-v2";
import { useUserOverviewApps } from "@/lib/swr/use-user-overview-metrics";
import { useI18n } from "@/lib/i18n-context";

// 使用 memo 优化图表组件，避免不必要的重渲染
const MemoizedRequestsErrorsChart = memo(RequestsErrorsChart);
const MemoizedLatencyPercentilesChart = memo(LatencyPercentilesChart);
const MemoizedTokenUsageChart = memo(TokenUsageChart);
const MemoizedCostByProviderChart = memo(CostByProviderChart);
const MemoizedAppsUsageChart = memo(AppsUsageChart);
const MemoizedTopModelsTable = memo(TopModelsTable);

/**
 * Dashboard 用户页 - 客户端容器组件
 * 
 * 职责：
 * - 管理筛选器状态（时间范围、传输方式、流式）
 * - 调用所有 SWR Hooks 获取数据
 * - 将数据传递给各个子组件
 * - 处理加载态、错误态、空态
 * 
 * 验证需求：1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1
 */
export function OverviewClient() {
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

  // 成本结构筛选器（只包含 timeRange）
  const costFilters = useMemo(
    () => ({
      timeRange,
    }),
    [timeRange]
  );

  // 获取所有数据
  const kpisResult = useUserDashboardKPIs(filters);
  const pulseResult = useUserDashboardPulse(pulseFilters);
  const tokensResult = useUserDashboardTokens(filters, "hour");
  const topModelsResult = useUserDashboardTopModels(filters, 10);
  const costResult = useUserDashboardCostByProvider(costFilters, 12);
  const appsResult = useUserOverviewApps({ time_range: timeRange, limit: 10 });

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
            {t("dashboard.title")}
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

      {/* 层级 1 - KPI 卡片（5 张） */}
      <section>
        <KPICardsGrid
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
            <MemoizedRequestsErrorsChart
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
            <MemoizedLatencyPercentilesChart
              data={pulseResult.points}
              isLoading={pulseResult.loading}
            />
          )}
        </div>
      </section>

      {/* 层级 3 - 成本 & Token（2 张卡片） */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          {costResult.error ? (
            <ErrorState
              title={t("dashboard.errors.loadFailed")}
              message={costResult.error.message}
              onRetry={costResult.refresh}
            />
          ) : costResult.items.length === 0 && !costResult.loading ? (
            <EmptyState message={t("dashboard.errors.noData")} />
          ) : (
            <MemoizedCostByProviderChart
              data={costResult.items}
              isLoading={costResult.loading}
            />
          )}
        </div>
        <div>
          {tokensResult.error ? (
            <ErrorState
              title={t("dashboard.errors.loadFailed")}
              message={tokensResult.error.message}
              onRetry={tokensResult.refresh}
            />
          ) : tokensResult.points.length === 0 && !tokensResult.loading ? (
            <EmptyState message={t("dashboard.errors.noData")} />
          ) : (
            <MemoizedTokenUsageChart
              data={tokensResult.points}
              bucket="hour"
              isLoading={tokensResult.loading}
              estimatedRequests={totalEstimatedRequests}
            />
          )}
        </div>
      </section>

      {/* 层级 4 - 排行榜 */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          {appsResult.error ? (
            <ErrorState
              title={t("dashboard.errors.loadFailed")}
              message={appsResult.error.message}
              onRetry={appsResult.refresh}
            />
          ) : (appsResult.apps?.items?.length || 0) === 0 && !appsResult.loading ? (
            <EmptyState message={t("dashboard.errors.noData")} />
          ) : (
            <MemoizedAppsUsageChart
              data={appsResult.apps?.items || []}
              isLoading={appsResult.loading}
              limit={10}
            />
          )}
        </div>
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
            <MemoizedTopModelsTable
              data={topModelsResult.items}
              isLoading={topModelsResult.loading}
            />
          )}
        </div>
      </section>
    </div>
  );
}
