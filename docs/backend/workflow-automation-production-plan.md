# 工作流自动化（Workflow Automation）v0 已实现总结 & 生产化规划

本文档用于对齐当前“最小可用版本（v0）”已经打通的后端链路，并给出后续走向“完整生产模式”的任务清单与里程碑规划。

## 1. 当前已实现（v0，最小链路打通）

### 1.1 数据模型与迁移

- 新增表：
  - `workflows`：工作流模版（Spec 持久化）
  - `workflow_runs`：执行实例（状态机 + spec 快照 + 步骤执行快照）
  - `workflow_run_events`：事件溯源（SSE replay 真相来源）
- 迁移脚本：`backend/alembic/versions/0055_add_workflow_automation_tables.py`
- ORM 模型：
  - `backend/app/models/workflow.py`
  - `backend/app/models/workflow_run.py`
  - `backend/app/models/workflow_run_event.py`

### 1.2 API（Workflow/Run/SSE）

路由实现：`backend/app/api/v1/workflow_routes.py`

- `POST /v1/workflows`：创建工作流模版
- `POST /v1/workflow-runs`：创建并启动 Run（进程内引擎）
- `GET /v1/workflow-runs/{run_id}`：获取 Run 状态与 `steps_state`
- `POST /v1/workflow-runs/{run_id}/resume`：CAS 恢复（仅 `paused -> running` 成功，防重复 resume）
- `POST /v1/workflow-runs/{run_id}/cancel`：取消（best-effort）
- `GET /v1/workflow-runs/{run_id}/events`：SSE（DB replay + Redis 热通道），Envelope 复用 `type: "run.event"`

### 1.3 引擎与 Bridge 事件分发

- 严格串行引擎（`current_step_index` 指针、每步可选审批、失败默认“红色暂停”）：`backend/app/services/workflow_engine.py`
- Bridge 全局分发器（单进程单连接消费 Gateway 事件，按 `req_id` 分发并写入 `workflow_run_events`）：`backend/app/services/workflow_bridge_dispatcher.py`
- 运行时单例与生命周期管理：`backend/app/services/workflow_runtime.py`

### 1.4 应用启动行为

接入点：`backend/app/routes.py`

- startup sweep：将 `workflow_runs.status='running'` 的记录标记为 `paused/engine_interrupted`（用于“进程重启后可恢复”的 v0 语义）
- 启动 `WorkflowRuntime`（Bridge 分发器）

### 1.5 文档与前端对齐

- API 文档：`docs/api/workflows.md`
- 前端 v0 设计文档：`docs/fronted/features/workflow-automation.md`

## 2. v0 现状边界与已知风险

### 2.1 运行时形态（进程内任务）

当前 Run 的执行由 API 进程内 `asyncio.create_task(...)` 驱动；优点是落地快，但存在天然限制：

- Pod/进程重启会中断正在执行的任务（v0 用 startup sweep 将其标记为 `engine_interrupted`，用户可点 resume 重跑）
- 多副本部署下，如果多个 Pod 启动都执行 sweep，可能误伤其他 Pod 正在执行的 run（生产化需要改造 sweep 策略）

### 2.2 安全与多租户（关键缺口）

当前 Workflow 的 tool_call 依赖 Bridge 能力，但 Bridge 侧仍处于“链路打通优先”的阶段（`backend/app/api/v1/bridge_routes.py` 中也有注释：未来需要把 `agent_id` 与用户身份绑定校验）。

结论：生产化必须补上“用户对 agent_id 的所有权/授权校验”，否则存在越权调用风险。

### 2.3 事件与日志的持久化策略

- v0 仅持久化 `log_preview`（截断）与 tool 终态摘要；完整日志与中间产物（artifact）尚未落盘为可检索资源。
- `workflow_run_events` 会持续增长，缺少保留策略与归档策略。

## 3. 生产模式（v1）目标定义

“完整生产模式”建议满足以下条件：

- 多副本/滚动发布下，run 不会被误 sweep、不会双引擎并发、不会出现“DB 显示 running 但实际无人执行”的不可解释状态
- tool 调用与 user/agent 的授权绑定完整（最小权限、可审计）
- 执行引擎从 API 生命周期解耦（Worker/队列/调度），支持恢复、取消、超时与限流
- 事件与日志可回放、可追溯、可控增长（保留/归档）

## 4. 生产化任务清单（建议按里程碑推进）

### Milestone A（v0.5）：让 v0 更“可部署”

- 改造 startup sweep：从“全量 running -> paused”改为“只 sweep stale run”
  - 需要 `workflow_runs.last_activity_at` 作为依据（v0 已有字段）
  - 建议新增阈值配置（例如 `stale_seconds`），并在文档中明确语义
- `/resume` 幂等与按钮语义进一步明确：
  - 将“审批”与“恢复”拆成显式接口（建议新增：`POST /v1/workflow-runs/{id}/approve`），避免未来引入更多 paused_reason 时语义混淆
- 引擎内状态机完善：
  - 明确终态集合（completed/failed/canceled）
  - `on_error=continue` 时，不应发出 `step.paused`（v0 已避免，但需补齐测试）
- 增补最小测试：
  - 运行/暂停/审批/失败暂停/重试 attempt 递增/SSE replay 基本链路

### Milestone B（v1.0）：执行与连接解耦（Worker 化）

- 引擎执行从 API 进程迁移到 Worker（Celery 或其他任务系统）
  - API：只负责创建 run、订阅事件、发出 resume/cancel 指令
  - Worker：负责推进状态机（tick），并写入 `workflow_run_events`
- BridgeStreamDispatcher 的位置调整：
  - 方案 1：仍由 Worker 统一消费 Gateway events，并分发到等待中的 invocation（推荐）
  - 方案 2：将结果由 Gateway 持久化并提供 replay/poll（需要改动 Gateway，属于更大工程）
- 取消与超时：
  - 统一由 Worker 处理 tool 超时，并向 Gateway 发 `cancel`（best-effort）
  - 记录为明确的 tool/state（timeout/canceled）

### Milestone C（v1.1）：安全/权限与可观测性

- Bridge 多租户绑定：
  - `agent_id` 只能被其 owner 用户或授权用户使用
  - 所有 invoke/cancel 必须校验 user ↔ agent 关系
- 审计与证据链：
  - 记录 `approved_by/approved_at`（目前仅有 `approved_at`）
  - 记录每个 tool invocation 的输入快照与结果摘要（v0 已有 attempts 雏形）
- 指标与告警：
  - run/step 耗时分布、失败率、tool 调用次数、超时次数

### Milestone D（v1.2）：Artifacts（产物）与保留策略

- 新增 artifact 体系：
  - 完整日志存储（OSS/S3）+ `log_ref`
  - 大结果/二进制产物（截图、文件、diff）落盘并可引用
- 事件/运行记录保留策略：
  - `workflow_run_events` 归档/清理（按天/月）
  - “只保留摘要 + artifact ref”的策略化落地

## 5. 前端实施建议（依赖后端里程碑）

前端 v0 以 `docs/fronted/features/workflow-automation.md` 为准；生产化阶段建议额外支持：

- Run 列表/历史：需要新增后端 `GET /v1/workflow-runs`（建议新增接口）
- 更强的“证据面板”：Artifacts（日志/结果/文件）可视化
- 权限提示与风险标识：tool 风险等级/外联/写操作标记（需要后端补齐元信息）

