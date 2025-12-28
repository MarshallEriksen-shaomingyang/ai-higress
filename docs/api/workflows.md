# Workflows（工作流自动化 / 可执行 SOP）API

本模块用于将“步骤卡片（Spec）”持久化为可复用模版（Workflow），并创建可恢复的执行实例（WorkflowRun）。执行过程通过 SSE 事件流透明展示，并支持暂停、恢复与取消。

## 认证

所有接口均需要 JWT：

```http
Authorization: Bearer <access_token>
```

## 数据结构（v0）

### WorkflowSpec（工作流定义）

- `title`: string
- `description?`: string
- `variables?`: object（v0 预留）
- `steps`: WorkflowStep[]

### WorkflowStep（步骤）

- `id`: string（前端生成，用于定位）
- `name`: string
- `type`: `"tool_call"`（v0 仅支持 tool_call）
- `tool_config`:
  - `agent_id`: string
  - `tool_name`: string
  - `arguments`: object
  - `timeout_ms?`: number
  - `stream?`: boolean
- `approval_policy`: `"auto" | "manual"`
- `on_error`: `"stop" | "continue"`

### WorkflowRun（执行实例）

- `status`: `"running" | "paused" | "completed" | "failed" | "canceled"`
- `paused_reason?`:
  - `awaiting_approval`：等待人工确认
  - `step_failed`：步骤失败暂停（“红色暂停”，可重试）
  - `user_cancel`：用户取消
  - `engine_interrupted`：引擎中断（进程重启时 startup sweep 标记）
- `current_step_index`: number
- `steps_state`: `Record<step_id, { status, approved?, attempts[] }>`

## 接口

### POST `/v1/workflows`

创建 Workflow 模版（保存 Spec）。

请求体：

```json
{
  "title": "示例工作流",
  "description": "可选描述",
  "spec": {
    "title": "示例工作流",
    "description": "可选描述",
    "steps": [
      {
        "id": "step_1",
        "name": "调用工具",
        "type": "tool_call",
        "tool_config": {
          "agent_id": "agent_xxx",
          "tool_name": "mcp/fs/read",
          "arguments": { "path": "/tmp/a.txt" }
        },
        "approval_policy": "auto",
        "on_error": "stop"
      }
    ]
  }
}
```

返回：`WorkflowResponse`

### POST `/v1/workflow-runs`

创建并启动一次执行实例（Run）。

请求体：

```json
{ "workflow_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" }
```

返回：`WorkflowRunResponse`

### GET `/v1/workflow-runs/{run_id}`

获取 Run 当前状态与 `steps_state` 快照。

返回：`WorkflowRunResponse`

### POST `/v1/workflow-runs/{run_id}/resume`

从 `paused` 恢复执行（CAS：仅当 `status='paused'` 时成功）。

- 若 `paused_reason='awaiting_approval'`，该操作等价于“批准当前步骤并继续”。
- 若 `paused_reason='step_failed'`，该操作等价于“重试当前步骤”（会追加一次 attempt）。

失败：`409 conflict`（Run 不在 paused 状态）

### POST `/v1/workflow-runs/{run_id}/cancel`

取消执行（best-effort）。服务会：

- 将 Run 标记为 `canceled`；
- 尝试 cancel 当前正在执行的 Bridge 工具（若存在 req_id）。

请求体：

```json
{ "reason": "user_cancel" }
```

返回：`WorkflowRunResponse`

## SSE：执行事件流

### GET `/v1/workflow-runs/{run_id}/events?after_seq=0&limit=200`

说明：

- 支持断线重连回放：先 DB replay（after_seq 之后），再订阅 Redis 热通道；
- Envelope 复用 `type: "run.event"`，便于前端复用现有 run/tool 事件 store。

事件示例（SSE）：

```text
event: tool.result
data: {"type":"run.event","run_id":"...","seq":12,"event_type":"tool.result","created_at":"...","payload":{"type":"tool.result","req_id":"wf_xxx","state":"done","ok":true}}
```

### v0 事件类型（event_type / payload.type）

- `tool.status`：工具开始（state=`running`）
- `tool.log`：日志片段（服务端会按大小/时间聚合后输出）
- `tool.result`：工具终态（state=`done|failed|timeout|canceled`）
- `step.progress`：步骤状态变化（status=`running|failed` 等）
- `step.paused`：流程暂停（包含 `paused_reason`）
- `step.completed`：步骤完成
- `run.completed` / `run.failed`：Run 终态

