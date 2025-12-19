# 项目 AI 推荐评测（Top3）——前端对接说明（仅文档，不含代码）

> 说明：本功能已并入“聊天助手/历史/评测”整体链路；更完整的对接与契约请以
> `docs/frontend/chat-assistants-history-eval-integration.md` 为准。本文保留为“推荐评测”视角的补充说明。

## 目标体验（用户体验最优的默认策略）

- 用户正常聊天只看到 baseline（当前选择/默认模型）
- baseline 回复出现后，出现“推荐评测”按钮（不打断主流程）
- 点击后立即出现两个 challenger 的占位卡片（running），并展示“为什么挑它们来对比”的解释
- challenger 完成后用户选择赢家 + 原因标签（可选“跳过”）

> 解释文案要避免断言“谁更好”，推荐语义是“用于对比采样”，减少引导偏置。

## 数据加载策略（避免卡顿）

### 1) 会话列表：只取摘要

- 使用 `GET /v1/conversations?assistant_id=...&cursor=...&limit=...`
- 列表项只渲染轻量字段（title/last_activity_at/last_message_content/unread_count/is_pinned）

### 2) 消息列表：分页 + run 摘要

- 使用 `GET /v1/conversations/{id}/messages?cursor=...&limit=...`
- 每条 message 只返回 run 的 `output_preview/status`，不要直接返回 `output_full`

### 3) run 全文：点开才取（惰性加载）

- 用户切换到某个模型结果/展开详情时，再调用 `GET /v1/runs/{run_id}`

## 推荐评测交互（闭环）

### 触发

- 前提：已经有 baseline run（即用户已看到 baseline 回复）
- 调用：`POST /v1/evals`（携带 `project_id/assistant_id/conversation_id/message_id/baseline_run_id`）
- 说明：后端会基于“用户可访问的 provider（自有/分享给我/公共池）+ API Key 限制”来选 challenger 并执行评测；前端无需自行判断权限，但需要展示明确错误提示。

### 展示

- 立即在 UI 上插入两个 challenger 卡片（status=running）
- 轮询 `GET /v1/evals/{eval_id}` 或基于 run 状态刷新（具体机制由前端选型）

### 评分

- 用户选择 winner + reason_tags 提交：`POST /v1/evals/{eval_id}/rating`
- 推荐 reason_tags（MVP）：`accurate/complete/concise/safe/fast/cheap`

## 推荐理由（Project AI）展示建议

展示三段式，增强信任与可解释：

1) **摘要**：一句话说明“为什么挑这两个 challenger 对比 baseline”
2) **证据**：同类样本数、是否仍在探索（exploration=true/false）
3) **约束**：成本/延迟/稳定性等约束条件（例如“排除了失败率>阈值的候选”）

## 错误处理（前端需要显式提示）

- `PROJECT_EVAL_DISABLED`：提示“该项目未启用推荐评测”
- `PROJECT_EVAL_COOLDOWN`：提示“评测太频繁，请稍后再试”
- `PROJECT_EVAL_BUDGET_EXCEEDED`：提示“项目预算不足，无法触发评测”
- `PROVIDER_ACCESS_DENIED`（如后端提供）：提示“当前账号/Key 无权访问该提供商”
