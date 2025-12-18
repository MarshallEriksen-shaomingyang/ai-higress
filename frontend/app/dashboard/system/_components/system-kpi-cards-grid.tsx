"use client";

import {
  TotalRequestsCard,
  LatencyP95Card,
  ErrorRateCard,
  TotalTokensCard,
} from "@/app/dashboard/overview/_components/cards";

interface SystemKPICardsGridProps {
  data?: {
    total_requests: number;
    latency_p95_ms: number;
    error_rate: number;
    tokens: {
      input: number;
      output: number;
      total: number;
    };
  };
  isLoading: boolean;
  error?: Error;
}

/**
 * 系统页 KPI 卡片响应式网格布局
 * 
 * 职责：
 * - 展示 4 张 KPI 卡片（总请求数、P95 延迟、错误率、Token 总量）
 * - 注意：系统页没有 Credits 花费卡片
 * - 实现响应式布局：
 *   - 桌面端（≥1024px）：四列布局
 *   - 平板端（768-1023px）：两列布局
 *   - 移动端（<768px）：单列布局
 * - 统一处理加载态和错误态
 * 
 * 验证需求：1.1, 9.1, 9.2, 9.3
 */
export function SystemKPICardsGrid({ data, isLoading, error }: SystemKPICardsGridProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <TotalRequestsCard
        value={data?.total_requests ?? 0}
        isLoading={isLoading}
        error={error}
      />
      <LatencyP95Card
        value={data?.latency_p95_ms ?? 0}
        isLoading={isLoading}
        error={error}
      />
      <ErrorRateCard
        value={data?.error_rate ?? 0}
        isLoading={isLoading}
        error={error}
      />
      <TotalTokensCard
        inputTokens={data?.tokens.input ?? 0}
        outputTokens={data?.tokens.output ?? 0}
        totalTokens={data?.tokens.total ?? 0}
        isLoading={isLoading}
        error={error}
      />
    </div>
  );
}
