# 聊天助手 / 历史记录 / 推荐评测（Top3）前端对接指南

本文面向前端实现“像优秀聊天工具一样”的体验：用户有自己的助手（Assistant），每个助手下有自己的会话与聊天历史，并可在看到 baseline 回复后触发“推荐评测”来对比多个模型并提交赢家与原因标签，信号回流到 bandit。

> 说明：本文仅描述对接与体验建议，不包含前端代码实现。

---

## 0. 前置约定

- **认证方式**：所有管理/历史/评测相关接口均为 JWT（`Authorization: Bearer <access_token>`）。
- **Project 概念（MVP）**：`project_id == api_key_id`（项目即 API Key）；后端会校验 project_id 是否存在且归属当前用户，传错会直接 `404 not_found`。
- **性能约束**：历史列表只加载轻量数据，run 详情惰性加载；推荐评测默认最多 3 个模型（baseline + 2 challengers）。

---

## 0.5 当前前端落地进度（代码层）

你后续已经把“聊天模块”的前端基础设施搭起来了，主要落点：

- 页面与组件：`frontend/app/chat/*`、`frontend/components/chat/*`
- 类型：`frontend/lib/api-types.ts`（新增了 chat 相关类型段）
- 请求层：`frontend/http/{assistant,conversation,message,eval,eval-config}.ts`
- 数据层：`frontend/lib/swr/use-{assistants,conversations,messages,evals,eval-config}.ts`
- 状态：`frontend/lib/stores/chat-store.ts`
- 文案：`frontend/lib/i18n/chat.ts`

这些文件的存在说明“前端框架与交互骨架”已落地，但下一步最关键是 **把类型/HTTP 方法/响应结构与后端契约对齐**（见第 8 节）。

---

## 1. 功能清单（前端应该实现什么）

### 1) 助手（Assistants）

- 创建/编辑助手（system prompt、默认模型、model preset）
- 助手归档（隐藏于列表，不影响历史数据）
- 删除助手（硬删除，会级联删除该助手下的会话与消息）

### 2) 会话（Conversations）

- 在某个助手下创建会话
- 会话列表（按 `last_activity_at` 倒序）
- 会话归档（从列表隐藏，但仍可通过会话 ID 读取历史）
- 删除会话（硬删除，级联删除会话消息与 run/eval 数据）

### 3) 消息 / Run（History & Lazy Loading）

- 发送一条用户消息，后端同步执行 baseline（non-stream）并返回 `baseline_run` 摘要
- 消息列表分页：只返回每条 user message 对应的 run **摘要**
- 用户点开某个 run 再加载 run **全文详情**

### 4) 推荐评测（Evals）

- 基于 baseline run 触发评测（challengers 后台执行）
- 展示“为什么挑这些 challenger 来对比”的解释（规则/Project AI）
- 轮询刷新 challengers 状态
- 用户选择赢家 + 原因标签提交评分

### 5) 项目配置（Project Eval Config，管理员）

- 开关：是否启用推荐评测
- 候选模型池：`candidate_logical_models`
- Provider 可见范围：`provider_scopes`（private/shared/public）
- 频率控制：`cooldown_seconds`
- Project AI：`project_ai_enabled` + `project_ai_provider_model`（用于解释/兜底特征）

---

## 2. 需要对接的 API（一览）

以 `NEXT_PUBLIC_API_BASE_URL` 为前缀，路径如下（均为 JWT）：

### Assistants

- `GET /v1/assistants?project_id=&cursor=&limit=`
- `POST /v1/assistants`
- `GET /v1/assistants/{assistant_id}`
- `PUT /v1/assistants/{assistant_id}`（支持 `archived: true/false`）
- `DELETE /v1/assistants/{assistant_id}`

### Conversations

- `POST /v1/conversations`
- `GET /v1/conversations?assistant_id=&cursor=&limit=`（默认不返回 archived）
- `PUT /v1/conversations/{conversation_id}`（支持 `archived: true/false`、可选改 `title`）
- `DELETE /v1/conversations/{conversation_id}`

### Messages / Runs

- `POST /v1/conversations/{conversation_id}/messages`（同步跑 baseline）
- `GET /v1/conversations/{conversation_id}/messages?cursor=&limit=`（分页 + run 摘要）
- `GET /v1/runs/{run_id}`（惰性加载 run 全文详情）

### Evals

- `POST /v1/evals`
- `GET /v1/evals/{eval_id}`
- `POST /v1/evals/{eval_id}/rating`
  - 可选：`POST /v1/evals` 支持 `streaming=true`（SSE 返回 challenger 执行过程）

### Project Eval Config（管理员配置页）

- `GET /v1/projects/{project_id}/eval-config`
- `PUT /v1/projects/{project_id}/eval-config`

后端接口细节可直接参考：`docs/api/assistants.md`、`docs/api/evals.md`、`docs/api/project-eval-config.md`。

---

## 3. 推荐的页面/交互链路（最小但体验优先）

### A. 助手与会话入口（左侧导航）

1. 进入聊天模块时先拉助手列表：`GET /v1/assistants?project_id=...`
2. 用户选择某助手后拉会话列表：`GET /v1/conversations?assistant_id=...`
3. “新建会话”：`POST /v1/conversations`

建议交互：
- 助手列表项展示：名称 + 默认模型（或显示 auto）
- 会话列表项展示：title（可为空）+ `last_activity_at` +（可选）`is_pinned/unread_count/last_message_content`（后端已提供，能显著提升“秒开感”）
- 删除与归档必须二次确认（Dialog），避免误操作

### B. 会话内聊天与历史加载（避免卡顿）

1. 打开会话只拉消息分页：`GET /v1/conversations/{id}/messages?cursor=&limit=`
2. 发送消息：`POST /v1/conversations/{id}/messages`
   - 立即将 user message 插入 UI（乐观更新）
   - 收到 baseline run 摘要后渲染 assistant 回复（正文在 message.content，run 仅作为可展开详情）
3. 用户点开某个 run：`GET /v1/runs/{run_id}`（再展示请求/响应/全文）

### C. 推荐评测闭环（Top3：baseline + 2 challengers）

1. baseline 回复出现后，展示“推荐评测”按钮（不打断主流程）
2. 点击触发：`POST /v1/evals`
   - UI 立即渲染 challenger 卡片占位（running）
   - 展示 explanation（`summary` + 可选 `evidence`）
3. 刷新方式二选一：
   - 轮询：`GET /v1/evals/{eval_id}`（直到 `status=ready/rated` 或 challengers 全部结束）
   - SSE：`POST /v1/evals` 带 `streaming=true`，按事件流增量更新（`eval.created` / `run.delta` / `eval.completed` / `[DONE]`）
4. 选择赢家 + 原因标签：`POST /v1/evals/{eval_id}/rating`
   - 提交成功后可立即隐藏评测面板或展示“已提交反馈”

原因标签建议（MVP，枚举/多选）：`accurate/complete/concise/safe/fast/cheap`。

---

## 4. 归档/删除的前端行为建议（重要）

### 会话归档

- 调用：`PUT /v1/conversations/{conversation_id}`，`{"archived": true}`
- 归档后：
  - 会话不会出现在 `GET /v1/conversations?assistant_id=...` 列表
  - **仍可读取历史**：`GET /v1/conversations/{conversation_id}/messages`
  - **不可继续发送新消息**：`POST /v1/conversations/{conversation_id}/messages` 会返回 404（前端应显示“会话已归档/不可继续对话”并禁用输入框）

> 当前后端未提供“列出已归档会话”的接口；如果需要“已归档”分组页，建议后续增加 `include_archived` 查询参数或单独接口。

### 会话删除

- 调用：`DELETE /v1/conversations/{conversation_id}`
- 删除后：
  - 会话与消息/run/eval 将级联删除
  - 前端应清空当前会话 UI，并跳回会话列表

### 助手归档 vs 删除

- 归档：`PUT /v1/assistants/{assistant_id}`，`{"archived": true}`（仅从列表隐藏）
- 删除：`DELETE /v1/assistants/{assistant_id}`（硬删除 + 级联删除其会话/历史）

---

## 5. 性能优化要点（必须做）

### 1) 分页与缓存策略

- 列表分页都使用 `cursor/limit`，不要一次性拉全量。
- 建议 SWR 缓存策略：
  - 助手列表：`static` 或 `frequent`
  - 会话列表：`frequent`（新消息会更新 last_activity）
  - 消息列表：`frequent`（分页加载更多）
  - eval 状态轮询：自行轮询（不要用 `revalidateOnFocus` 触发抖动）
  - run 详情：`default`（点开才取）

### 2) 历史数据“轻量优先”

- 消息列表接口只返回 run 摘要（`output_preview/status/latency/error_code`），避免把大 payload（request/response/output_text）压到列表请求里。
- run 详情只在用户需要时加载（展开/切换模型/查看 debug）。

### 3) 评测轮询节流

- 建议轮询间隔：1s → 2s → 3s 递增退避；到 `ready/rated` 立即停止。
- challengers 出错不应阻塞 UI：卡片显示失败态与错误摘要即可。

### 4) 大会话渲染

- 消息超过一定数量后，建议做虚拟列表或“只渲染可视窗口”。
- 反复切换会话时避免重复创建 SWR key 对象（用稳定的字符串 key + params）。

---

## 6. 管理员配置页（Project Eval Config）怎么做

目标：管理员可逐步让 Project AI 更重要，但仍保持可开关、可降级。

### 配置项 UI 建议

- `enabled`：启用推荐评测（总开关）
- `candidate_logical_models`：候选模型池（建议 UI 默认推荐最多 3 个，允许更多但后端最多取前 N 并去重）
- `max_challengers`：默认 2（组成 Top3）
- `provider_scopes`：private/shared/public
- `cooldown_seconds`：避免用户频繁刷评测
- `project_ai_enabled`：Project AI 开关
- `project_ai_provider_model`：下拉选择（`{provider_id}/{logical_model}`）

### “Project AI 越来越重要”的落地方式（前端侧）

- 配置页强调：开启 Project AI 后会用于
  - 解释为何挑选 challenger
  - 在规则特征无法判定时兜底补齐 context features（用于 bandit 学习）
- UI 展示层面：
  - explanation 优先展示 Project AI 的 summary（若有），否则展示规则解释
  - 明确提示“解释不等于评判优劣，只用于说明选择原因”

---

## 7. 常见错误与前端提示建议

- 404 会话不存在：会话被删除或已归档且写入接口被拒（发送消息应提示“会话已归档/删除”）
- 404 项目不存在或无权访问：`project_id` 传错/无权访问（常见于把 `user.id` 当成 project_id）
- 403 项目未启用推荐评测：提示“该项目未启用推荐评测”
- 429 评测太频繁（cooldown）：提示“评测太频繁，请稍后再试”

> 建议统一使用前端现有错误标准化层（`ErrorHandler`）来展示 `detail.message` 与 `detail.error`。

---

## 8. 对齐检查（你新增代码后，当前最需要补齐的点）

下面是本次 code review 发现的“前后端不一致/容易踩坑”的清单，建议按优先级修正：

### P0：会直接导致接口 404/405 的不一致

- `project_id` 来源：前端聊天模块当前把 `user.id` 当 `project_id`，但后端约定是 `project_id == api_key_id`。需要在前端提供“当前项目（API Key）选择器”，或复用现有 API Key 管理页的选择结果（存储 `api_key_id`）。
- HTTP 方法：
  - 后端：助手更新是 `PUT /v1/assistants/{assistant_id}`；会话更新是 `PUT /v1/conversations/{conversation_id}`；评测配置更新是 `PUT /v1/projects/{project_id}/eval-config`
  - 前端请求层当前使用了 `PATCH`（会 405）。要么前端改为 `PUT`，要么后端增加 `PATCH` 兼容路由（两者择一）
- 会话详情：前端请求层调用了 `GET /v1/conversations/{conversation_id}`，但后端目前没有这个接口（只有 list + update + messages）。要么删掉这个调用并改为“列表数据即详情”，要么后端补 `GET /v1/conversations/{id}`（两者择一）
- 触发评测：`POST /v1/evals` 的 `message_id` 是必填；前端目前留空/尝试“从 baseline_run_id 推断”会触发 422/400，需要在消息列表中把 `message_id` 一并带上（`POST /v1/conversations/{id}/messages` 本身就会返回 `message_id`）。

### P0：响应结构/类型不一致（会导致渲染错误/运行时报错）

目前后端契约（`docs/api/assistants.md`）与前端 `frontend/lib/api-types.ts` 的 chat 类型段存在明显不一致，典型包括：

- `archived`：后端是 `archived_at`（datetime/null），前端是 boolean
- `message.content`：后端是结构化 dict（如 `{type:'text', text:'...'}`），前端按 string 渲染
- messages 列表：后端每条 message 附带 `runs: RunSummary[]`；前端类型是 `{ message, run? }`
- run 字段：后端是 `latency_ms/cost_credits/request_payload/response_payload`；前端是 `latency/cost/request/response` 等

建议明确“后端契约是源头”，前端在请求层做一次 normalize（或直接改类型与组件渲染逻辑），避免到处写兼容判断。

### P1：性能/体验实现里容易遗漏的点

- SWR key 与预加载：你新增的 cache preloader 如果用 `JSON.stringify(key)`，会和 SWR 对 object key 的序列化不一致，导致预加载失效；应使用与 `useSWR` 完全一致的 key（同样的 object/array key 形状）。
- 消息顺序：后端消息列表当前是倒序分页（新 → 旧）；前端虚拟列表若按数组顺序渲染并“滚到底部”，可能会把“旧消息”放在底部，体验反转。建议在渲染层统一成“旧 → 新”，并调整乐观插入位置与分页合并策略。
