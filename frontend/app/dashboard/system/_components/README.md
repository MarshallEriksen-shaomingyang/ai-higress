# System Dashboard Components

系统仪表盘页面的私有组件。

## ProviderStatusList

Provider 状态列表组件，使用网格布局展示所有 Provider 的状态卡片。

### Props

```typescript
interface ProviderStatusListProps {
  data: ProviderStatusItem[];  // Provider 状态数据数组
  isLoading: boolean;          // 加载状态
  error?: Error;               // 错误信息
  onRetry?: () => void;        // 重试回调函数
}
```

### 响应式布局

- **桌面 (≥1024px)**: 3 列网格
- **平板 (768-1023px)**: 2 列网格
- **移动 (<768px)**: 1 列网格

### 状态处理

#### 加载态
显示 6 个 Skeleton 占位符卡片，避免布局抖动。

#### 错误态
显示错误提示卡片，包含：
- 错误图标 (AlertCircle)
- 错误标题和消息
- 重试按钮（如果提供了 onRetry 回调）

#### 空数据态
显示友好的空状态占位符，包含：
- 提示图标
- "暂无 Provider" 标题
- 描述文案

#### 正常数据态
显示 Provider 状态卡片网格，包含：
- 标题和 Provider 总数
- 响应式网格布局
- 每个 Provider 一张状态卡片

### 使用示例

```tsx
import { ProviderStatusList } from "./_components/provider-status-list";
import { useSystemDashboardProviders } from "@/lib/swr/use-dashboard-v2";

export function SystemDashboard() {
  const { items, loading, error, refresh } = useSystemDashboardProviders();

  return (
    <ProviderStatusList
      data={items}
      isLoading={loading}
      error={error}
      onRetry={refresh}
    />
  );
}
```

### 国际化

组件使用 `useI18n()` Hook 获取文案，支持中英文切换。使用的 i18n keys：
- `dashboardV2.provider.title` - 标题
- `dashboardV2.provider.totalCount` - Provider 总数
- `dashboardV2.provider.noData` - 空数据标题
- `dashboardV2.provider.noDataDescription` - 空数据描述
- `error.loadFailed` - 加载失败
- `error.unknownError` - 未知错误
- `common.retry` - 重试按钮

### 依赖组件

- `ProviderStatusCard` - Provider 状态卡片
- `@/components/ui/card` - Card 组件
- `@/components/ui/button` - Button 组件
- `@/lib/i18n-context` - 国际化 Hook
- `lucide-react` - 图标库 (AlertCircle, Loader2)

### 设计规范

- 使用 Tailwind CSS 网格布局
- 支持暗色模式
- 加载态使用 Skeleton 动画
- 错误态使用 destructive 颜色
- 空态使用 muted 颜色

## ProviderStatusCard

Provider 状态卡片组件，用于显示单个 Provider 的运行状态、健康状态、审核状态和最后检查时间。

### Props

```typescript
interface ProviderStatusCardProps {
  providerId: string;                                    // Provider ID
  operationStatus: "active" | "inactive" | "maintenance"; // 运行状态
  healthStatus: "healthy" | "degraded" | "unhealthy";    // 健康状态
  auditStatus: "approved" | "pending" | "rejected";      // 审核状态
  lastCheck: string;                                     // 最后检查时间 (ISO 8601)
}
```

### 状态颜色映射

#### 运行状态 (Operation Status)
- **active (运行中)**: 绿色
- **inactive (未运行)**: 灰色
- **maintenance (维护中)**: 黄色

#### 健康状态 (Health Status)
- **healthy (健康)**: 绿色
- **degraded (降级)**: 黄色
- **unhealthy (不健康)**: 红色

#### 审核状态 (Audit Status)
- **approved (已批准)**: 绿色
- **pending (待审核)**: 蓝色
- **rejected (已拒绝)**: 红色

### 使用示例

```tsx
import { ProviderStatusCard } from "./_components/provider-status-card";

export function SystemDashboard() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <ProviderStatusCard
        providerId="openai-gpt4"
        operationStatus="active"
        healthStatus="healthy"
        auditStatus="approved"
        lastCheck={new Date().toISOString()}
      />
    </div>
  );
}
```

### 时间格式化

组件会自动将 ISO 8601 格式的时间转换为相对时间：
- 小于 1 分钟: "刚刚"
- 小于 1 小时: "X 分钟前"
- 小于 24 小时: "X 小时前"
- 大于 24 小时: "X 天前"

### 国际化

组件使用 `useI18n()` Hook 获取文案，支持中英文切换。所有文案定义在 `frontend/lib/i18n/dashboard.ts` 中。

### 依赖组件

- `@/components/ui/card` - Card 组件
- `@/components/ui/badge` - Badge 组件
- `@/lib/i18n-context` - 国际化 Hook
- `@/lib/utils` - 工具函数

### 设计规范

遵循设计文档中定义的颜色规范：
- 使用 Tailwind CSS 的颜色类
- 支持暗色模式
- 使用 `border-transparent` 移除 Badge 的边框
- 卡片支持 hover 效果 (`hover:shadow-md`)
