# Dashboard Overview Components

Dashboard v2 用户页的组件目录。

## 组件列表

### 错误处理组件

#### ErrorState
错误状态组件，用于显示数据加载失败时的错误提示。

**特性：**
- 显示错误图标和错误信息
- 提供重试按钮
- 支持自定义标题和描述
- 使用国际化文案

**使用示例：**
```tsx
import { ErrorState } from "./_components/error-state";

// 基础用法
<ErrorState
  onRetry={() => mutate()}
/>

// 自定义标题和描述
<ErrorState
  title="加载失败"
  message="无法连接到服务器，请检查网络连接"
  onRetry={() => mutate()}
/>

// 不显示重试按钮
<ErrorState
  message="权限不足"
  showRetry={false}
/>
```

**Props：**
- `title?: string` - 错误标题（默认使用 i18n）
- `message?: string` - 错误描述（默认使用 i18n）
- `onRetry?: () => void` - 重试回调函数
- `showRetry?: boolean` - 是否显示重试按钮（默认 true）
- `className?: string` - 自定义类名

#### EmptyState
空状态组件，用于显示数据为空时的占位符。

**特性：**
- 显示空状态图标和提示信息
- 支持自定义图标
- 支持自定义标题和描述
- 使用国际化文案

**使用示例：**
```tsx
import { EmptyState } from "./_components/empty-state";
import { Inbox } from "lucide-react";

// 基础用法
<EmptyState />

// 自定义标题和描述
<EmptyState
  title="暂无数据"
  message="当前时间范围内没有数据，请尝试调整筛选条件"
/>

// 自定义图标
<EmptyState
  icon={<Inbox className="size-12 text-muted-foreground/50" />}
  title="收件箱为空"
/>
```

**Props：**
- `title?: string` - 空状态标题（默认使用 i18n）
- `message?: string` - 空状态描述
- `icon?: React.ReactNode` - 自定义图标
- `className?: string` - 自定义类名

### KPI 卡片组件

位于 `kpis/` 目录，包含：
- `kpi-cards-grid.tsx` - KPI 卡片网格容器（响应式布局）
- 各个 KPI 卡片组件

### 图表组件

位于 `charts/` 目录，包含：
- 请求 & 错误趋势图
- 延迟分位数趋势图
- Token 使用趋势图
- 成本结构图

### 表格组件

位于 `tables/` 目录，包含：
- Top Models 排行榜

## 设计原则

1. **组件化**：每个功能独立封装为组件
2. **可复用**：组件支持自定义配置
3. **国际化**：所有文案通过 i18n 管理
4. **类型安全**：使用 TypeScript 类型定义
5. **响应式**：适配不同设备尺寸
6. **主题适配**：支持亮色/暗色模式

## 目录结构

```
_components/
├── README.md              # 本文档
├── error-state.tsx        # 错误状态组件
├── empty-state.tsx        # 空状态组件
├── kpis/                  # KPI 卡片组件
│   ├── kpi-cards-grid.tsx
│   └── ...
├── charts/                # 图表组件
│   └── ...
└── tables/                # 表格组件
    └── ...
```

## 相关文档

- [需求文档](../../../../.kiro/specs/dashboard-overview-refactor/requirements.md)
- [设计文档](../../../../.kiro/specs/dashboard-overview-refactor/design.md)
- [任务列表](../../../../.kiro/specs/dashboard-overview-refactor/tasks.md)
