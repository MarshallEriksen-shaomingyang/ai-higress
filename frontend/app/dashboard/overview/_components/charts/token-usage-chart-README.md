# Token 使用趋势图表组件

## 概述

`TokenUsageChart` 组件用于展示 Token 输入和输出的使用趋势，使用 Recharts 的堆叠柱状图实现。

## 功能特性

- ✅ 堆叠柱状图展示输入和输出 Token
- ✅ 支持小时和天两种时间粒度
- ✅ 估算请求提示 tooltip（当有估算请求时显示）
- ✅ 响应式设计，适配不同屏幕尺寸
- ✅ 主题适配（亮色/暗色模式）
- ✅ 国际化支持（中英文）
- ✅ 加载态、错误态、空态处理
- ✅ 千位分隔符格式化

## 使用方法

### 基本用法

```tsx
import { TokenUsageChart } from "@/app/dashboard/overview/_components/charts";
import { useUserDashboardTokens } from "@/lib/swr/use-dashboard-v2";

function MyComponent() {
  const { data, isLoading, error } = useUserDashboardTokens({
    time_range: "7d",
    bucket: "hour",
  });

  // 计算总估算请求数
  const estimatedRequests = data?.data_points.reduce(
    (sum, point) => sum + point.estimated_requests,
    0
  ) ?? 0;

  return (
    <TokenUsageChart
      data={data?.data_points ?? []}
      bucket="hour"
      isLoading={isLoading}
      error={error}
      estimatedRequests={estimatedRequests}
    />
  );
}
```

### Props

| 属性 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `data` | `DashboardV2TokenDataPoint[]` | ✅ | - | Token 数据点数组 |
| `bucket` | `"hour" \| "day"` | ✅ | - | 时间粒度（小时/天） |
| `isLoading` | `boolean` | ✅ | - | 是否正在加载 |
| `error` | `Error` | ❌ | - | 错误对象 |
| `estimatedRequests` | `number` | ❌ | `0` | 估算请求总数 |

### 数据格式

```typescript
interface DashboardV2TokenDataPoint {
  window_start: string;        // ISO 8601 时间戳
  input_tokens: number;         // 输入 Token 数量
  output_tokens: number;        // 输出 Token 数量
  total_tokens: number;         // Token 总量
  estimated_requests: number;   // 估算请求数
}
```

## 设计规范

### 颜色配置

组件使用 CSS 变量配置颜色，自动适配主题：

- **输入 Token**: `hsl(var(--chart-2))` - 蓝色系
- **输出 Token**: `hsl(var(--chart-3))` - 紫色系

### 图表配置

- **图表高度**: 256px (h-64)
- **动画时长**: 800ms
- **堆叠方式**: stackId="tokens"
- **圆角**: 顶部圆角 4px

### 估算请求提示

当 `estimatedRequests > 0` 时，组件会在右上角显示一个 ⓘ 图标：

- 鼠标悬停显示 tooltip
- 提示内容："{count} 个请求的 Token 来自估算"
- 位置：卡片标题右侧

## 状态处理

### 加载状态

```tsx
<TokenUsageChart
  data={[]}
  bucket="hour"
  isLoading={true}
  estimatedRequests={0}
/>
```

显示："加载中..."

### 错误状态

```tsx
<TokenUsageChart
  data={[]}
  bucket="hour"
  isLoading={false}
  error={new Error("Failed to fetch data")}
  estimatedRequests={0}
/>
```

显示：错误提示 + 错误消息

### 空数据状态

```tsx
<TokenUsageChart
  data={[]}
  bucket="hour"
  isLoading={false}
  estimatedRequests={0}
/>
```

显示："暂无数据"

## 国际化

组件使用 `useI18n()` Hook 获取文案，支持中英文：

```typescript
// 英文
"dashboard_v2.chart.token_usage.title": "Token Usage"
"dashboard_v2.chart.token_usage.subtitle": "Input vs Output"
"dashboard_v2.chart.token_usage.input_tokens": "Input Tokens"
"dashboard_v2.chart.token_usage.output_tokens": "Output Tokens"
"dashboard_v2.chart.token_usage.estimated_tooltip": "{count} requests have estimated token counts"

// 中文
"dashboard_v2.chart.token_usage.title": "Token 使用趋势"
"dashboard_v2.chart.token_usage.subtitle": "输入 vs 输出"
"dashboard_v2.chart.token_usage.input_tokens": "输入 Token"
"dashboard_v2.chart.token_usage.output_tokens": "输出 Token"
"dashboard_v2.chart.token_usage.estimated_tooltip": "{count} 个请求的 Token 来自估算"
```

## 演示页面

访问 `/dashboard/overview/token-demo` 查看组件的各种状态和场景演示。

## 验证需求

该组件实现了以下需求：

- ✅ **需求 4.1**: 显示"Token 输入 vs 输出"图表
- ✅ **需求 4.2**: 使用堆叠柱状图展示 input_tokens 和 output_tokens
- ✅ **需求 4.4**: 当 Token 数据包含估算请求时，显示 ⓘ tooltip
- ✅ **需求 4.5**: 当 estimated_requests > 0 时，显示 tooltip 提示"部分 Token 来自估算"

## 技术细节

### 时间格式化

- **小时粒度**: HH:mm 格式（如 "14:30"）
- **天粒度**: MM-DD 格式（如 "12-18"）

### Token 数量格式化

使用 `toLocaleString()` 添加千位分隔符：

- 50000 → "50,000"
- 1234567 → "1,234,567"

### 响应式设计

- X 轴最小间隔：
  - 小时粒度：60px
  - 天粒度：30px
- Y 轴宽度：80px（容纳大数字）

## 依赖

- `recharts`: 图表库
- `@/components/ui/card`: 卡片组件
- `@/components/ui/chart`: 图表容器和 tooltip
- `@/components/ui/tooltip`: 估算请求提示
- `lucide-react`: Info 图标
- `@/lib/i18n-context`: 国际化
- `@/lib/api-types`: 类型定义
