# 工作流自动化前端实现

基于 Next.js 和 Tailwind CSS 实现的工作流自动化 UI，采用"数字水墨"视觉风格。

**⚡ 独立全屏页面架构** - 类似 Chat 页面，拥有独立的导航和布局系统。

## 📁 文件结构

```
frontend/
├── app/workflows/                    # 独立页面路由（非 dashboard）
│   ├── layout.tsx                    # 工作流主布局
│   ├── page.tsx                      # 工作流列表/入口页
│   ├── composer/page.tsx             # 编排器页面
│   ├── monitor/[runId]/page.tsx      # 监控台页面
│   └── components/
│       ├── workflow-nav-rail.tsx     # 侧边导航栏
│       ├── workflow-mobile-header.tsx # 移动端顶部导航
│       └── workflow-layout-root-client.tsx
│
├── components/workflow/              # 核心组件
│   ├── workflow-composer.tsx         # 编排器组件
│   ├── workflow-run-monitor.tsx      # 监控台组件
│   ├── status-badge.tsx              # 状态徽章
│   ├── log-terminal.tsx              # 日志终端
│   ├── step-card.tsx                 # 步骤卡片
│   └── index.ts                      # 组件导出
│
└── lib/
    ├── workflow/
    │   ├── styles.ts                 # 视觉基调配置
    │   └── types.ts                  # 类型定义
    └── http/
        └── workflow.ts               # API 调用
```

## 🏗️ 架构特点

### 独立页面设计
- **独立路由**: `/workflows` 而非 `/dashboard/workflows`
- **专属导航**: 左侧垂直导航栏（桌面端）+ 顶部横向导航（移动端）
- **全屏布局**: 类似 Chat 页面，提供沉浸式体验
- **响应式设计**: 完美支持桌面端和移动端

### 导航系统
```
桌面端（左侧导航栏）:
├─ 控制台 (/dashboard)
├─ 工作流 (/workflows)
└─ 编排器 (/workflows/composer)

移动端（顶部导航）:
├─ 返回/菜单按钮
└─ 快捷导航图标
```

## 🎨 视觉基调 (Digital Ink)

采用"数字水墨"风格，以下是核心设计元素：

### 背景色
- **Rice Paper**: `bg-[#F7F9FB]` - 宣纸质感

### 卡片
- **Porcelain**: `bg-white/80 backdrop-blur-md` - 白瓷润泽感

### 墨色
- **浓墨**: `text-slate-800` (标题)
- **淡墨**: `text-slate-500` (正文)

### 状态点睛色
- **Running**: 蓝光 `shadow-[0_0_8px_rgba(96,165,250,0.6)]`
- **Paused**: 朱砂 `shadow-[0_0_8px_rgba(251,146,60,0.6)]`
- **Success**: 翡翠 `bg-emerald-500`
- **Failed**: 红光 `shadow-[0_0_8px_rgba(239,68,68,0.6)]`

## 📄 页面说明

### 1. Workflow Composer (编排器)

**路由**: `/dashboard/workflows/composer`

**布局**: Grid 12列
- 左侧 3列: 工具库 (The Toolbox)
- 右侧 9列: 编排画布 (The Canvas)

**功能**:
- 从工具库添加步骤
- 配置步骤参数
- 设置人工审批
- 保存并运行工作流

### 2. Workflow Run Monitor (监控台)

**路由**: `/dashboard/workflows/monitor/[runId]`

**布局**: 单列居中 (max-w-4xl)

**功能**:
- 实时状态监控 (SSE)
- 步骤日志流
- 人工审批操作
- 重试失败步骤
- 取消运行

### 3. Workflows Index (列表页)

**路由**: `/dashboard/workflows`

**功能**:
- 快速开始入口
- 功能特性介绍

## 🔧 核心组件

### StatusBadge
状态徽章，显示运行状态并带呼吸动画。

```tsx
<StatusBadge status="running" reason="awaiting_approval" />
```

### LogTerminal
日志终端，实时显示执行日志并自动滚动。

```tsx
<LogTerminal logs={['Log line 1', 'Log line 2']} autoScroll />
```

### StepCard
步骤卡片，支持编辑态和运行态两种模式。

```tsx
// 编辑态
<StepCardEdit
  step={step}
  index={0}
  onDelete={() => {}}
  onUpdate={(step) => {}}
/>

// 运行态
<StepCardRun
  step={step}
  state={stepState}
  index={0}
  isCurrent={true}
/>
```

## 🌐 API 集成

所有 API 调用封装在 `lib/http/workflow.ts`:

```typescript
import {
  createWorkflow,
  createWorkflowRun,
  getWorkflowRun,
  resumeWorkflowRun,
  cancelWorkflowRun,
  subscribeWorkflowRunEvents
} from '@/lib/http/workflow';
```

### SSE 事件订阅

```typescript
const unsubscribe = subscribeWorkflowRunEvents(
  runId,
  (event) => {
    console.log('Event:', event);
  },
  (error) => {
    console.error('Error:', error);
  }
);

// 清理
unsubscribe();
```

## 🎯 交互脚本

### 编排时
- **空画布**: "从左侧点击工具，开始编排你的自动化流程。"
- **添加工具**: 显示淡入动画
- **设置审批**: "该步骤执行前，系统将暂停并通知您。"

### 运行时
- **等待审批**: "Waiting for your signal..." (橙色高亮)
- **执行失败**: "Execution hit a snag. Check logs below." (红色提示)
- **日志流**: 使用 JetBrains Mono 字体，12px

## 🚀 使用示例

1. 访问 `/dashboard/workflows` 查看功能介绍
2. 点击"开始编排"进入 Composer
3. 从左侧工具库添加步骤
4. 配置参数和审批设置
5. 点击"保存并运行"
6. 自动跳转到 Monitor 页面实时监控

## 📝 类型定义

所有类型定义在 `lib/workflow/types.ts`:

```typescript
import type {
  Workflow,
  WorkflowSpec,
  WorkflowRun,
  WorkflowStep,
  StepState,
  WorkflowRunEvent,
  BridgeAgent,
  BridgeTool
} from '@/lib/workflow/types';
```

## ✅ 实现状态

- [x] 视觉基础样式配置
- [x] 核心 UI 组件
- [x] Workflow Composer 页面
- [x] Workflow Run Monitor 页面
- [x] API 服务封装
- [x] TypeScript 类型定义
- [x] SSE 事件订阅
- [x] 路由配置

## 🔜 后续优化

1. **工具库数据**: 从后端 API 动态加载 Bridge Agents
2. **工作流列表**: 实现历史工作流列表页
3. **参数编辑器**: 增强 JSON 参数编辑体验
4. **错误处理**: 完善网络错误和边界情况处理
5. **性能优化**: 虚拟滚动优化长日志列表
6. **测试覆盖**: 添加单元测试和 E2E 测试

## 📖 参考文档

- 后端文档: `docs/backend/workflow-automation-production-plan.md`
- UI 设计指南: 本 README 中的视觉基调部分
