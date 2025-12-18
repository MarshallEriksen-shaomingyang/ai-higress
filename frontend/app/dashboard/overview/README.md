# Dashboard 用户页 - 概览页面

## 概述

Dashboard 用户页是一个完整的监控仪表盘，让用户在 5 秒内了解系统健康状况、Token 使用情况和成本花费。

## 页面结构

```
/dashboard/overview
├── page.tsx                          # 服务端页面组件
└── _components/
    ├── overview-client.tsx           # 客户端容器组件（主要逻辑）
    ├── index.ts                      # 组件导出
    ├── badge/                        # 健康徽章
    │   └── health-badge.tsx
    ├── filters/                      # 筛选器
    │   └── filter-bar.tsx
    ├── kpis/                         # KPI 网格布局
    │   └── kpi-cards-grid.tsx
    ├── cards/                        # KPI 卡片
    │   ├── total-requests-card.tsx
    │   ├── credits-spent-card.tsx
    │   ├── latency-p95-card.tsx
    │   ├── error-rate-card.tsx
    │   └── total-tokens-card.tsx
    ├── charts/                       # 图表组件
    │   ├── requests-errors-chart.tsx
    │   ├── latency-percentiles-chart.tsx
    │   ├── token-usage-chart.tsx
    │   └── cost-by-provider-chart.tsx
    ├── tables/                       # 表格组件
    │   └── top-models-table.tsx
    ├── error-state.tsx               # 错误状态组件
    └── empty-state.tsx               # 空状态组件
```

## 页面布局

页面采用 4 层布局结构：

### 顶部工具条
- 页面标题 + 健康状态徽章
- 时间范围筛选器（today/7d/30d）
- 传输方式筛选器（all/http/sdk/claude_cli）
- 流式筛选器（all/true/false）

### 层级 1 - KPI 卡片（5 张）
- 总请求数（Total Requests）
- Credits 花费（Credits Spent）
- P95 延迟（Avg Latency P95）
- 错误率（Error Rate）
- Token 总量（Total Tokens，内含 Input/Output）

### 层级 2 - 核心趋势图（2 张大图并排）
- 请求 & 错误趋势（Requests & Errors Trend）- 近 24h
- 延迟分位数趋势（Latency Percentiles Trend）- 近 24h

### 层级 3 - 成本 & Token（2 张卡片）
- 成本结构（Cost by Provider）- Donut 图
- Token 输入 vs 输出（Token Usage）- 堆叠柱状图

### 层级 4 - 排行榜
- 热门模型（Popular Models / Top Models）- 表格

## 数据流

1. **页面加载** → 初始化筛选器状态（默认 7d）
2. **筛选器变化** → 触发所有 SWR Hook 重新获取数据
3. **数据获取** → 多个 Hook 并行调用后端 API
4. **数据缓存** → SWR 缓存数据（TTL 60s），避免重复请求
5. **UI 更新** → 各组件根据数据状态（loading/error/success）渲染

## 使用的 SWR Hooks

- `useUserDashboardKPIs` - 获取 KPI 指标
- `useUserDashboardPulse` - 获取近 24h 脉搏数据
- `useUserDashboardTokens` - 获取 Token 趋势数据
- `useUserDashboardTopModels` - 获取热门模型排行
- `useUserDashboardCostByProvider` - 获取按 Provider 的成本结构

## 响应式布局

- **桌面端（≥1024px）**：KPI 卡片四列布局，图表并排显示
- **平板端（768-1023px）**：KPI 卡片两列布局，图表并排显示
- **移动端（<768px）**：KPI 卡片单列布局，图表堆叠显示

## 国际化

所有文案通过 `useI18n()` Hook 获取，支持中英文切换。文案定义在 `frontend/lib/i18n/dashboard.ts` 中。

## 错误处理

- **API 请求失败**：显示错误提示卡片，提供重试按钮
- **数据为空**：显示"暂无数据"占位符
- **网络超时**：显示超时提示，自动重试（SWR 内置）

## 开发指南

### 添加新的 KPI 卡片

1. 在 `_components/cards/` 中创建新的卡片组件
2. 在 `_components/cards/index.ts` 中导出
3. 在 `overview-v2-client.tsx` 中引入并使用
4. 在 `kpi-cards-grid.tsx` 中添加到网格布局

### 添加新的图表

1. 在 `_components/charts/` 中创建新的图表组件
2. 在 `_components/charts/index.ts` 中导出
3. 在 `overview-v2-client.tsx` 中引入并使用
4. 根据需要添加到对应的层级中

### 添加新的筛选器

1. 在 `filter-bar.tsx` 中添加新的筛选器选项
2. 在 `overview-v2-client.tsx` 中添加状态管理
3. 更新 `filters` 对象，传递给相关的 SWR Hook

## 验证需求

本页面实现了以下需求：

- **需求 1.1**：显示 5 张 KPI 卡片
- **需求 2.1**：显示请求 & 错误趋势图
- **需求 3.1**：显示延迟分位数趋势图
- **需求 4.1**：显示 Token 使用趋势图
- **需求 5.1**：显示成本结构图
- **需求 6.1**：显示 Top Models 列表
- **需求 7.1**：提供时间范围筛选器
- **需求 8.1**：提供传输方式和流式筛选器
- **需求 9.1-9.3**：响应式布局
- **需求 10.1**：显示健康状态徽章
- **需求 11.1**：国际化支持
- **需求 12.1-12.3**：错误处理

## 相关文档

- [需求文档](/.kiro/specs/dashboard-overview-refactor/requirements.md)
- [设计文档](/.kiro/specs/dashboard-overview-refactor/design.md)
- [任务列表](/.kiro/specs/dashboard-overview-refactor/tasks.md)
