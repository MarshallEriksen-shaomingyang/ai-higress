# 工作流自动化（Spec Editor + 执行监控）前端设计文档（v0）

## 目标与范围

面向“AI 版 Zapier / 可执行 SOP”的最小闭环 UI：

1) 用户可手工编排 Workflow（步骤卡片）并保存为模版  
2) 用户可创建 WorkflowRun 并执行  
3) 用户可在 Monitor 页面看到每步状态、实时日志（SSE）、失败后可 Resume/Retry、支持 Cancel  

非目标（v0 不做）：

- MCP 自动发现 / 安装（仅使用现有 Bridge 的 agents/tools 列表）
- DAG 并发执行（严格串行）
- 复杂机器验收（JSONPath 断言等）

## 相关后端接口（对齐点）

文档：`docs/api/workflows.md`

- `POST /v1/workflows`：创建模版
- `POST /v1/workflow-runs`：创建并启动 Run
- `GET /v1/workflow-runs/{run_id}`：获取状态快照（含 `steps_state`）
- `POST /v1/workflow-runs/{run_id}/resume`：CAS 恢复（paused -> running）
- `POST /v1/workflow-runs/{run_id}/cancel`：取消
- `GET /v1/workflow-runs/{run_id}/events`：SSE 事件流（`type: "run.event"`）

## 路由与信息架构

建议新增导航入口：

- `nav.workflows` → `/dashboard/workflows`

页面结构：

1) **Workflow Composer**：`/dashboard/workflows`  
   - 左侧：Bridge Agents/Tools（可搜索）  
   - 右侧：步骤时间线（Card 列表）  
   - 顶部：Workflow 元信息（title/description）  
   - 底部：`Save Workflow`、`Run Workflow`

2) **Workflow Run Monitor**：`/dashboard/workflow-runs/[runId]`  
   - 垂直步骤卡片（只读为主）
   - 当前 step 自动展开，显示实时日志（SSE）
   - 根据 `paused_reason` 显示 `Resume / Approve / Retry / Cancel`

## 组件拆分（遵循 repo 规范）

```
frontend/app/dashboard/workflows/
├── page.tsx                  (服务端组件：布局)
└── components/
    ├── workflow-composer-client.tsx   ("use client"：容器，数据与交互)
    ├── workflow-step-editor.tsx       (步骤编辑卡片：选择 tool + 参数)
    └── tool-picker-dialog.tsx         (选择 agent/tool 的 Dialog)

frontend/app/dashboard/workflow-runs/[runId]/
├── page.tsx                  (服务端组件：读取 runId + 布局)
└── components/
    ├── workflow-run-monitor-client.tsx ("use client"：订阅 SSE + 渲染卡片)
    └── workflow-run-step-card.tsx      (单步卡片：状态/日志/按钮)
```

UI 组件：一律使用 `@/components/ui/*`（Card/Button/Select/Dialog/Tabs/Textarea/Badge/ScrollArea 等），避免裸 HTML。

## 数据获取与状态管理（SWR + SSE）

### SWR Hooks（新增）

新增 `frontend/lib/swr/use-workflows.ts`：

- `useCreateWorkflow()` → `POST /v1/workflows`
- `useCreateWorkflowRun()` → `POST /v1/workflow-runs`
- `useWorkflowRun(runId)` → `GET /v1/workflow-runs/{runId}`
- `useResumeWorkflowRun(runId)` → `POST /v1/workflow-runs/{runId}/resume`
- `useCancelWorkflowRun(runId)` → `POST /v1/workflow-runs/{runId}/cancel`

Bridge 工具列表复用既有：

- `useBridgeAgents()` / `useBridgeTools(agentId)`（见 `frontend/lib/swr/use-bridge.ts`）

### SSE（复用现有 run-event 消费逻辑）

现有 `frontend/lib/hooks/use-run-tool-events.ts` 默认订阅 `/v1/runs/{runId}/events`。  
建议将其改为可传入 `eventsUrl`（默认保持原行为），以便 Workflow Monitor 复用：

- Workflow：`/v1/workflow-runs/${runId}/events?after_seq=...`

处理策略：

- `tool.status/tool.log/tool.result`：继续走现有 store（可直接复用工具调用 UI/气泡）
- `step.progress/step.paused/step.completed/run.*`：在 `workflow-run-monitor-client.tsx` 里单独处理（更新步骤卡片状态、控制按钮展示）

## 交互与视觉规范 (对应 ui-prompt.md v2.0)

- **新中式数字水墨风格**：页面背景使用极淡冷灰蓝 (`#F7F9FB`)，卡片采用纯白圆角设计 (`rounded-xl`)。
- **便当盒布局 (Bento Grid)**：Workflow 步骤采用卡片拼接网格布局，通过弥散阴影 (`box-shadow`) 营造悬浮感，不使用硬边框。
- **状态感知 (Glow Dots)**：
  - `running`：使用带蓝色光晕的呼吸点 (Glow Dots)。
  - `paused`：橙色发光点。
  - `completed`：静止的淡墨绿圆点。
- **毛玻璃特效 (Glassmorphism)**：Monitor 顶部的状态栏和操作栏使用 `backdrop-filter: blur(12px); background: rgba(255, 255, 255, 0.85);`。
- **动效反馈**：点击步骤卡片时有微弱的回弹效果 (`scale: 0.98`)，步骤入场采用渐进式浮动淡入。
- **日志区域**：采用磨砂玻璃背景，等宽字体，保持通透感而非沉重的黑盒。

## 国际化（i18n）约定

新增模块文件建议：`frontend/lib/i18n/workflows.ts`，并在 `frontend/lib/i18n/index.ts` 合并导出。

最小 key 列表（示例）：

- `nav.workflows`
- `workflows.title` / `workflows.subtitle`
- `workflows.composer.save` / `workflows.composer.run`
- `workflows.step.add` / `workflows.step.approval_toggle`
- `workflows.run.status.running|paused|completed|failed|canceled`
- `workflows.run.paused_reason.awaiting_approval|step_failed|engine_interrupted|user_cancel`
- `workflows.run.actions.resume|approve|retry|cancel`
- `workflows.run.logs.title` / `workflows.run.logs.copy` / `workflows.run.logs.clear`

## 错误处理与边界条件

- `POST /resume` 返回 409：提示“任务不在暂停状态”，并刷新 run 状态（SWR mutate/refresh）。
- Run 处于 `paused_reason=engine_interrupted`：按钮文案偏“恢复执行（从断点继续）”。
- Step 失败：卡片红色 + 显示最后一次 attempt 的 `error/result_preview`；按钮显示 `Retry`（复用 resume）。

## 验收清单（v0）

- 可以手工新增/删除/排序步骤，并保存为 Workflow
- Run 启动后，页面能实时看到 `tool.log` 与 `tool.result`
- 遇到 manual step 能暂停并点击 Approve 继续
- 遇到失败能暂停并点击 Retry 继续（attempt 递增）
- Cancel 后 Run 变为 canceled，UI 不再继续推进

