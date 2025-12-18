# Dashboard v2 图表组件

本目录包含 Dashboard v2 用户页的所有图表组件。

## 组件列表

### RequestsErrorsChart

请求 & 错误趋势图表，展示近 24 小时的请求和错误数据（展示组件）。

### RequestsErrorsChartLive

请求 & 错误趋势图表的实时版本，自动连接 API 获取数据（容器组件）。

### LatencyPercentilesChart

延迟分位数趋势图表，展示近 24 小时的 P50/P95/P99 延迟数据（展示组件）。

### LatencyPercentilesChartLive

延迟分位数趋势图表的实时版本，自动连接 API 获取数据（容器组件）。

### TokenUsageChart

Token 使用趋势图表，展示输入和输出 Token 的堆叠柱状图（展示组件）。

### CostByProviderChart

成本结构图表，展示按 Provider 的成本分布（Donut 图）。

**功能特性：**
- 使用 Recharts ComposedChart 组合折线图和堆叠柱状图
- 折线图展示总请求数趋势
- 堆叠柱状图展示 4xx/5xx/429/timeout 错误分布
- 自动补零处理缺失的分钟数据
- 支持加载态、错误态和空态显示
- 完全国际化支持

**Props：**
```typescript
interface RequestsErrorsChartProps {
  data: DashboardV2PulseDataPoint[];  // Pulse 数据点数组
  isLoading: boolean;                  // 加载状态
  error?: Error;                       // 错误对象
}
```

**使用示例（展示组件）：**
```tsx
import { RequestsErrorsChart } from "@/app/dashboard/overview/_components/charts";
import { useUserDashboardPulse } from "@/lib/swr/use-dashboard-v2";

function MyComponent() {
  const { points, loading, error } = useUserDashboardPulse({
    transport: "all",
    isStream: "all",
  });

  return (
    <RequestsErrorsChart
      data={points}
      isLoading={loading}
      error={error}
    />
  );
}
```

**使用示例（实时组件，推荐）：**
```tsx
import { RequestsErrorsChartLive } from "@/app/dashboard/overview/_components/charts";

function MyComponent() {
  return (
    <RequestsErrorsChartLive
      transport="all"
      isStream="all"
    />
  );
}
```

**数据补零逻辑：**

组件会自动检测数据中缺失的分钟，并补零以确保图表连续显示。例如：
- 输入数据：`[{time: "10:00", ...}, {time: "10:02", ...}]`
- 补零后：`[{time: "10:00", ...}, {time: "10:01", requests: 0, ...}, {time: "10:02", ...}]`

**颜色配置：**

图表使用 CSS 变量配置颜色，自动适配亮色/暗色主题：
- 总请求数（折线）：`hsl(var(--chart-1))` - 主色
- 4xx 错误（柱状）：`hsl(var(--chart-4))` - 橙色系
- 5xx 错误（柱状）：`hsl(var(--destructive))` - 红色系
- 429 错误（柱状）：`hsl(var(--warning))` - 黄色系
- Timeout 错误（柱状）：`hsl(var(--chart-5))` - 灰色系

---

### LatencyPercentilesChart 详细说明

**功能特性：**
- 使用 Recharts LineChart 展示三条延迟曲线
- P50（中位数）、P95、P99 三条折线
- Y 轴显示延迟单位 (ms)
- 自动补零处理缺失的分钟数据
- 支持加载态、错误态和空态显示
- 完全国际化支持

**Props：**
```typescript
interface LatencyPercentilesChartProps {
  data: DashboardV2PulseDataPoint[];  // Pulse 数据点数组
  isLoading: boolean;                  // 加载状态
  error?: Error;                       // 错误对象
}
```

**使用示例（展示组件）：**
```tsx
import { LatencyPercentilesChart } from "@/app/dashboard/overview/_components/charts";
import { useUserDashboardPulse } from "@/lib/swr/use-dashboard-v2";

function MyComponent() {
  const { data, isLoading, error } = useUserDashboardPulse({
    transport: "all",
    is_stream: "all",
  });

  return (
    <LatencyPercentilesChart
      data={data?.data || []}
      isLoading={isLoading}
      error={error}
    />
  );
}
```

**使用示例（实时组件，推荐）：**
```tsx
import { LatencyPercentilesChartLive } from "@/app/dashboard/overview/_components/charts";

function MyComponent() {
  return (
    <LatencyPercentilesChartLive
      transport="all"
      isStream="all"
    />
  );
}
```

**颜色配置：**

延迟图表使用渐进式颜色区分三条曲线：
- P50（折线）：`hsl(var(--chart-2))` - 浅色
- P95（折线）：`hsl(var(--chart-3))` - 中色
- P99（折线）：`hsl(var(--chart-4))` - 深色

---

### TokenUsageChart 详细说明

**功能特性：**
- 使用 Recharts BarChart 展示堆叠柱状图
- 输入 Token 和输出 Token 堆叠显示
- 支持 hour 和 day 两种时间粒度
- 显示估算请求提示 tooltip（当 estimated_requests > 0 时）
- 支持加载态、错误态和空态显示
- 完全国际化支持

**Props：**
```typescript
interface TokenUsageChartProps {
  data: DashboardV2TokenDataPoint[];  // Token 数据点数组
  bucket: "hour" | "day";              // 时间粒度
  isLoading: boolean;                  // 加载状态
  error?: Error;                       // 错误对象
  estimatedRequests?: number;          // 估算请求数量
}
```

**使用示例：**
```tsx
import { TokenUsageChart } from "@/app/dashboard/overview/_components/charts";
import { useUserDashboardTokens } from "@/lib/swr/use-dashboard-v2";

function MyComponent() {
  const { data, isLoading, error } = useUserDashboardTokens({
    timeRange: "7d",
    bucket: "day",
    transport: "all",
    isStream: "all",
  });

  return (
    <TokenUsageChart
      data={data?.data || []}
      bucket="day"
      isLoading={isLoading}
      error={error}
      estimatedRequests={data?.estimated_requests || 0}
    />
  );
}
```

**颜色配置：**
- Input Tokens（堆叠柱）：`hsl(var(--chart-2))` - 蓝色系
- Output Tokens（堆叠柱）：`hsl(var(--chart-3))` - 紫色系

---

### CostByProviderChart 详细说明

**功能特性：**
- 使用 Recharts PieChart 展示 Donut 图
- 自动按 credits_spent 降序排序 Provider
- 显示每个 Provider 的 credits_spent 和占比
- 使用 CSS 变量循环分配颜色（支持最多 5 种颜色）
- 自定义图例显示详细信息
- 支持加载态、错误态和空态显示
- 完全国际化支持

**Props：**
```typescript
interface CostByProviderChartProps {
  data: DashboardV2ProviderCostItem[];  // Provider 成本数据数组
  isLoading: boolean;                    // 加载状态
  error?: Error;                         // 错误对象
}
```

**使用示例：**
```tsx
import { CostByProviderChart } from "@/app/dashboard/overview/_components/charts";
import { useUserDashboardCostByProvider } from "@/lib/swr/use-dashboard-v2";

function MyComponent() {
  const { data, isLoading, error } = useUserDashboardCostByProvider({
    timeRange: "7d",
    limit: 12,
  });

  return (
    <CostByProviderChart
      data={data?.items || []}
      isLoading={isLoading}
      error={error}
    />
  );
}
```

**数据排序：**

组件会自动按 `credits_spent` 降序排序 Provider，确保花费最多的 Provider 排在前面。

**颜色配置：**

成本图表使用循环颜色分配：
- Provider 1：`hsl(var(--chart-1))`
- Provider 2：`hsl(var(--chart-2))`
- Provider 3：`hsl(var(--chart-3))`
- Provider 4：`hsl(var(--chart-4))`
- Provider 5：`hsl(var(--chart-5))`
- Provider 6+：循环使用上述颜色

**自定义图例：**

图例显示每个 Provider 的：
- Provider ID（名称）
- Credits Spent（格式化为千位分隔符，保留 2 位小数）
- 占比百分比（保留 1 位小数）

## 开发指南

### 添加新图表

1. 在本目录创建新的 `.tsx` 文件
2. 使用 `ChartContainer` 包裹 Recharts 组件
3. 配置 `chartConfig` 对象定义颜色和标签
4. 使用 `useI18n()` 获取国际化文案
5. 处理加载态、错误态和空态
6. 在 README 中添加文档

### 测试图表

使用 `*-demo.tsx` 文件进行独立测试：
```bash
# 在浏览器中访问
http://localhost:3000/dashboard/overview/demo
```

### 性能优化

- 使用 `useMemo` 缓存图表数据转换
- 避免在渲染时创建新对象
- 合理设置动画时长（建议 800ms）
- 大数据集时考虑采样或分页

## 相关文档

- [设计文档](/.kiro/specs/dashboard-overview-refactor/design.md)
- [需求文档](/.kiro/specs/dashboard-overview-refactor/requirements.md)
- [Recharts 文档](https://recharts.org/)
