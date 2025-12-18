"use client";

import {
  TotalRequestsCard,
  CreditsSpentCard,
  LatencyP95Card,
  ErrorRateCard,
  TotalTokensCard,
} from "../cards";

interface KPICardsGridProps {
  data?: {
    total_requests: number;
    credits_spent: number;
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
 * KPI 卡片响应式网格布局
 * 
 * 职责：
 * - 展示 5 张 KPI 卡片（总请求数、Credits 花费、P95 延迟、错误率、Token 总量）
 * - 实现响应式布局：
 *   - 桌面端（≥1024px）：四列布局
 *   - 平板端（768-1023px）：两列布局
 *   - 移动端（<768px）：单列布局
 * - 统一处理加载态和错误态
 * 
 * 验证需求：1.1, 9.1, 9.2, 9.3
 */
export function KPICardsGrid({ data, isLoading, error }: KPICardsGridProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <TotalRequestsCard
        value={data?.total_requests ?? 0}
        isLoading={isLoading}
        error={error}
      />
      <CreditsSpentCard
        value={data?.credits_spent ?? 0}
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
