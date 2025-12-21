# Evals API（推荐评测：baseline + challengers）

> 认证：JWT（`Authorization: Bearer <access_token>`）

## POST `/v1/evals`

基于已存在的 baseline_run 触发推荐评测，创建 challenger runs（默认最多 2 个）并异步执行。

Request:
```json
{
  "project_id": "uuid",
  "assistant_id": "uuid",
  "conversation_id": "uuid",
  "message_id": "uuid",
  "baseline_run_id": "uuid",
  "streaming": false
}
```

Response（`streaming=false`，默认）:
```json
{
  "eval_id": "uuid",
  "status": "running",
  "baseline_run_id": "uuid",
  "challengers": [
    {
      "run_id": "uuid",
      "requested_logical_model": "gpt-4.1-mini",
      "status": "queued",
      "output_preview": null
    }
  ],
  "explanation": {
    "summary": "…",
    "evidence": {
      "policy_version": "ts-v1",
      "exploration": true
    }
  }
}
```

Response（`streaming=true`，SSE / `text/event-stream`）:
- 每条 SSE 帧同时包含：
  - `event: <type>`（标准 SSE event name，便于客户端按事件类型分发）
  - `data: <json>`（JSON 内仍包含 `type` 字段，兼容只解析 `data` 的客户端）
- 首包：`type=eval.created`（包含 eval_id、challengers、explanation）
- 过程中：`type=run.delta`（每条 challenger run 的增量/状态；包含 `provider_id`/`provider_model`/`cost_credits` 等元信息）
- 单条 run 结束：`type=run.completed`（包含 full_text、latency_ms 等）
- 错误：`type=run.error` / `type=eval.error`
- 心跳：`type=heartbeat`（用于保持连接与中间状态刷新）
- 结束：`type=eval.completed`，并以 `event: done` + `data: [DONE]` 结束
  - `eval.completed.status` 以数据库中 eval 的最终状态为准：通常为 `ready`（全部 challenger 结束）或 `rated`（用户已提交评分）
  - 若同一个 `baseline_run_id` 对应的 eval 已存在，服务端不会重复执行已结束的 challenger run，而是优先发送已落库的 `run.completed/run.error` 快照并结束（queued 的 run 仍会被执行）

示例（SSE data 行内 JSON）：
```text
event: eval.created
data: {"type":"eval.created","eval_id":"...","challengers":[...],"explanation":{...}}

event: run.delta
data: {"type":"run.delta","run_id":"...","status":"running","provider_id":"...","provider_model":"...","cost_credits":1,"delta":"..."}

event: run.completed
data: {"type":"run.completed","run_id":"...","status":"succeeded","provider_id":"...","provider_model":"...","cost_credits":1,"latency_ms":123,"full_text":"..."}

event: heartbeat
data: {"type":"heartbeat","ts":1730000000}

event: eval.completed
data: {"type":"eval.completed","eval_id":"...","status":"ready"}

event: done
data: [DONE]
```

说明：
- 若项目配置启用 `project_ai_enabled=true` 且设置了 `project_ai_provider_model`，后端会尝试调用该模型生成解释；失败会自动降级为规则解释（不会影响评测主流程）。
- `streaming=true` 仅影响 challenger 的返回方式；评分仍使用 `POST /v1/evals/{eval_id}/rating`。

Errors:
- `403 forbidden` + `detail.error = "forbidden"`：项目未启用推荐评测
- `429` + `detail.error = "PROJECT_EVAL_COOLDOWN"`：触发过于频繁

## GET `/v1/evals/{eval_id}`

查询评测状态与 challenger 列表（用于轮询刷新）。

## POST `/v1/evals/{eval_id}/rating`

提交 winner + 原因标签（winner 必须属于 baseline/challengers）。

Request:
```json
{
  "winner_run_id": "uuid",
  "reason_tags": ["accurate", "complete"]
}
```

Response:
```json
{
  "eval_id": "uuid",
  "winner_run_id": "uuid",
  "reason_tags": ["accurate"],
  "created_at": "2025-12-19T00:00:00Z"
}
```

## GET `/admin/evals`（管理员：评测结果列表，无内容）

> 认证：JWT（`Authorization: Bearer <access_token>`）  
> 权限：仅超级管理员（`current_user.is_superuser=true`）

用于管理员查看全站评测结果列表（分页），**不返回任何聊天内容/模型输出文本**（不包含 `output_text` / `output_preview`）。

Query（可选）：
- `cursor`: offset 游标（整数，默认 `0`）
- `limit`: 每页条数（1~100，默认 `30`）
- `status`: 按状态过滤（`running` / `ready` / `rated`）
- `project_id`: 按项目过滤（MVP: `project_id == api_key_id`）
- `assistant_id`: 按助手过滤

Response:
```json
{
  "items": [
    {
      "eval_id": "uuid",
      "status": "ready",
      "project_id": "uuid",
      "assistant_id": "uuid",
      "baseline_run_id": "uuid",
      "baseline_run": {
        "run_id": "uuid",
        "requested_logical_model": "gpt-4.1-mini",
        "status": "succeeded",
        "selected_provider_id": "provider-x",
        "selected_provider_model": "model-y",
        "latency_ms": 123,
        "cost_credits": 2,
        "error_code": null,
        "created_at": "2025-12-21T00:00:00Z",
        "updated_at": "2025-12-21T00:00:00Z"
      },
      "challengers": [
        {
          "run_id": "uuid",
          "requested_logical_model": "gpt-4.1-mini",
          "status": "failed",
          "selected_provider_id": "provider-x",
          "selected_provider_model": "model-y",
          "latency_ms": 456,
          "cost_credits": 3,
          "error_code": "UPSTREAM_ERROR",
          "created_at": "2025-12-21T00:00:00Z",
          "updated_at": "2025-12-21T00:00:00Z"
        }
      ],
      "explanation": {
        "summary": "…",
        "evidence": {
          "exploration": true
        }
      },
      "rated_at": null,
      "rating": null,
      "created_at": "2025-12-21T00:00:00Z",
      "updated_at": "2025-12-21T00:00:00Z"
    }
  ],
  "next_cursor": "30"
}
```

## GET `/admin/evals/{eval_id}`（管理员：单条评测详情，无内容）

同 `GET /admin/evals` 的单条结构，用于在管理端查看某次评测（同样不返回聊天内容/模型输出文本）。
