# Top Models Table 组件

## 概述

Top Models Table 组件用于展示最受欢迎的模型排行榜，显示模型名称、请求量和 Token 总量。

## 功能特性

- ✅ 显示模型名称、请求量、Token 总量
- ✅ 自动按请求量降序排序
- ✅ 支持加载态（Skeleton）
- ✅ 支持错误处理
- ✅ 支持空数据状态
- ✅ 完整的国际化支持
- ✅ 响应式设计

## 使用方法

```tsx
import { TopModelsTable } from "@/app/dashboard/overview/_components/tables/top-models-table"
import { useUserDashboardTopModels } from "@/lib/swr/use-dashboard-v2"

export function MyComponent() {
  const { data, isLoading, error } = useUserDashboardTopModels({
    time_range: "7d",
    limit: 10,
  })

  return (
    <TopModelsTable
      data={data?.models || []}
      isLoading={isLoading}
      error={error}
    />
  )
}
```

## Props

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `data` | `DashboardV2TopModelItem[]` | 是 | 模型数据数组 |
| `isLoading` | `boolean` | 是 | 是否正在加载 |
| `error` | `Error` | 否 | 错误对象 |

## 数据类型

```typescript
interface DashboardV2TopModelItem {
  model: string          // 模型名称
  requests: number       // 请求量
  tokens_total: number   // Token 总量
}
```

## 排序规则

组件会自动按 `requests` 字段降序排序，确保请求量最多的模型排在最前面。

## 状态处理

### 加载中
显示 5 行 Skeleton 占位符，避免布局抖动。

### 错误状态
显示错误提示卡片，包含错误消息。

### 空数据
显示"暂无数据"占位符。

### 正常状态
显示完整的表格，包含表头和数据行。

## 国际化

组件使用以下 i18n keys：

- `dashboardV2.topModels.title` - 标题
- `dashboardV2.topModels.modelName` - 模型名称列
- `dashboardV2.topModels.requests` - 请求量列
- `dashboardV2.topModels.totalTokens` - Token 总量列
- `dashboardV2.error.loadFailed` - 加载失败提示
- `dashboardV2.error.noData` - 无数据提示

## 演示页面

访问 `/dashboard/overview/top-models-demo` 查看组件的各种状态演示。

## 设计规范

- 使用 `@/components/ui/card` 作为容器
- 使用 `@/components/ui/table` 展示数据
- 数字使用 `toLocaleString()` 格式化，添加千位分隔符
- 右对齐数字列，左对齐文本列
- 支持暗色模式

## 验证需求

- ✅ 需求 6.1: 显示 Top Models 列表
- ✅ 需求 6.3: 展示模型名称、请求量、Token 总量
- ✅ 需求 6.4: 按 requests 降序排列

## 正确性属性

- **Property 9**: Top Models 数据完整性 - 每个模型应显示名称、请求量、Token 总量
- **Property 10**: Top Models 排序一致性 - 模型应按 requests 降序排列
