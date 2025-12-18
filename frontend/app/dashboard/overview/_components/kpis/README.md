# KPI 卡片网格布局组件

本目录包含 Dashboard v2 用户页的 KPI 卡片网格布局组件。

## 组件说明

### KPICardsGrid - KPI 卡片响应式网格

展示 5 张 KPI 卡片，并实现响应式布局。

#### 响应式布局规则

- **桌面端（≥1024px）**：四列布局（`lg:grid-cols-4`）
- **平板端（768-1023px）**：两列布局（`md:grid-cols-2`）
- **移动端（<768px）**：单列布局（`grid-cols-1`）

#### 使用示例

```tsx
import { KPICardsGrid } from "@/app/dashboard/overview/_components/kpis";
import { useUserDashboardKPIs } from "@/lib/swr/use-dashboard-v2";

export function DashboardOverview() {
  const { data, isLoading, error } = useUserDashboardKPIs({
    timeRange: "7d",
    transport: "all",
    isStream: "all",
  });

  return (
    <div className="space-y-6">
      <h1>Dashboard Overview</h1>
      <KPICardsGrid
        data={data}
        isLoading={isLoading}
        error={error}
      />
    </div>
  );
}
```

#### Props

```typescript
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
```

**参数说明：**

- `data` - KPI 数据对象（可选）
  - `total_requests` - 总请求数
  - `credits_spent` - Credits 花费
  - `latency_p95_ms` - P95 延迟（毫秒）
  - `error_rate` - 错误率（0-1 之间的小数）
  - `tokens` - Token 数据
    - `input` - 输入 Token 数量
    - `output` - 输出 Token 数量
    - `total` - Token 总量
- `isLoading` - 是否加载中
- `error` - 错误对象（可选）

## 设计原则

1. **响应式优先**：使用 Tailwind CSS 响应式类实现自适应布局
2. **统一数据源**：所有卡片共享同一个数据源和加载/错误状态
3. **组件复用**：复用已实现的 5 个 KPI 卡片组件
4. **布局一致性**：使用 `gap-4` 保持卡片间距一致

## 验证需求

- **需求 1.1**：显示 5 张 KPI 卡片
- **需求 9.1**：桌面端四列布局（≥1024px）
- **需求 9.2**：平板端两列布局（768-1023px）
- **需求 9.3**：移动端单列布局（<768px）

## Tailwind CSS 响应式断点

本组件使用的 Tailwind CSS 响应式断点：

- `grid-cols-1`：默认单列（移动端，<768px）
- `md:grid-cols-2`：平板端两列（≥768px）
- `lg:grid-cols-4`：桌面端四列（≥1024px）

这些断点与 Tailwind CSS 默认配置一致：
- `md`: 768px
- `lg`: 1024px

## 测试建议

1. **桌面端测试**：在浏览器中将窗口宽度调整到 ≥1024px，验证四列布局
2. **平板端测试**：将窗口宽度调整到 768-1023px，验证两列布局
3. **移动端测试**：将窗口宽度调整到 <768px，验证单列布局
4. **加载态测试**：验证所有卡片同时显示 Skeleton 占位符
5. **错误态测试**：验证所有卡片同时显示错误提示

## 注意事项

1. **数据可选性**：`data` 参数是可选的，当数据未加载时，卡片会显示默认值 0
2. **错误处理**：错误状态会传递给所有卡片，每个卡片独立显示错误提示
3. **加载态**：加载状态会传递给所有卡片，确保布局不会抖动
4. **间距统一**：使用 `gap-4` 确保卡片间距在所有屏幕尺寸下保持一致
