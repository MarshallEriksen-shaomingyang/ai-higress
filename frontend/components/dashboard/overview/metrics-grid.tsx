"use client";

import { ReactNode } from "react";

interface MetricsGridProps {
  children: ReactNode;
  /**
   * 网格间距（Tailwind gap 类）
   * 默认 "gap-6"
   */
  gap?: string;
}

/**
 * 响应式指标网格组件
 *
 * 职责：
 * - 提供响应式布局容器
 * - 支持桌面端四列、平板端两列、移动端单列布局
 * - 使用 Tailwind CSS 响应式类实现
 *
 * 验证需求：7.1, 7.2, 7.3
 * 验证属性：Property 19, 20, 21
 *
 * 布局规则：
 * - 移动端 (<768px)：单列布局 (grid-cols-1)
 * - 平板端 (768-1023px)：两列布局 (md:grid-cols-2)
 * - 桌面端 (≥1024px)：四列布局 (lg:grid-cols-4)
 *
 * 使用示例：
 * ```tsx
 * <MetricsGrid>
 *   <ConsumptionSummaryCard />
 *   <ProviderRankingCard />
 *   <SuccessRateTrendCard />
 *   <AlertCard />
 * </MetricsGrid>
 * ```
 */
export function MetricsGrid({
  children,
  gap = "gap-4",
}: MetricsGridProps) {
  return (
    <div className={`grid grid-cols-1 lg:grid-cols-3 ${gap}`}>
      {children}
    </div>
  );
}
