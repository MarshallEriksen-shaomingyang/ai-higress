# 文生图后端：同步接口、OSS 短链、Celery 异步化与会话历史融合（方案）

本文档面向后端开发，说明当前仓库已实现的文生图能力，以及如何在**不破坏现有 `/v1/images/generations`（API Key 模式）**的前提下，进一步把文生图与**会话历史（chat_messages/chat_runs）**融合，并支持通过 **Celery** 异步执行上游请求。

> 说明：本文档包含“已实现能力”和“建议方案（待实现）”两部分；其中“待实现”不代表代码中已存在对应路由/字段。

---

## 1. 已实现能力（现状）

### 1.1 文生图 API（OpenAI 兼容）

- 接口：`POST /v1/images/generations`
- 认证：网关 API Key（`Authorization: Bearer <token>` / `X-API-Key`），实现依赖 `backend/app/auth.py` 的 `require_api_key`
- 实现位置：
  - 路由：`backend/app/api/v1/image_routes.py`
  - 核心逻辑：`backend/app/services/image_app_service.py`

**上游两条 lane（已实现）**
- OpenAI lane：调用 OpenAI-compatible Provider 的 `images/generations`（路径推导逻辑见 `backend/app/services/image_app_service.py` 的 `_derive_openai_images_path`）
- Google lane：调用 Gemini Developer API 的 `v1beta/models/{model}:generateContent`，并将 `inlineData.data`（base64）转换为 OpenAI Images Response（同上文件）

**模型能力约束（已实现）**
- 通过逻辑模型 `capabilities` 强约束 `image_generation`，不具备能力则直接 400（`backend/app/services/image_app_service.py`）

### 1.2 图片存储（阿里 OSS 私有桶 + 网关签名短链）

当请求 `response_format="url"` 时：

- 若配置了对象存储（`IMAGE_STORAGE_PROVIDER` + `IMAGE_OSS_*`）：后端将图片写入对应存储（默认阿里 OSS；可选 S3/R2），并返回网关域名下短链：`/media/images/{object_key}?expires=...&sig=...`
- 若未配置 OSS：后端会退化为 `data:image/...;base64,...` 的 Data URL（仍可直接渲染）

实现位置：
- 存储/签名：`backend/app/services/image_storage_service.py`
- 短链读取：`backend/app/api/v1/media_routes.py`（`GET /media/images/{object_key:path}`）

签名与安全：
- `sig` 使用 `settings.secret_key` 做 HMAC-SHA256（见 `backend/app/services/image_storage_service.py` 的 `_hmac_signature`）
- 通过 `IMAGE_OSS_PREFIX` 限制 object_key 前缀，避免该接口变成通用 OSS 代理（见 `verify_signed_image_request`）

相关配置键（已存在）：
- OSS：`.env.example` 中 `IMAGE_OSS_ENDPOINT/BUCKET/ACCESS_KEY_ID/ACCESS_KEY_SECRET/IMAGE_OSS_PREFIX`
- 短链 TTL：`.env.example` 中 `IMAGE_SIGNED_URL_TTL_SECONDS`
- 对外网关域名：`backend/app/settings.py` 的 `GATEWAY_API_BASE_URL`（短链构造默认用它；见 `build_signed_image_url`）

### 1.3 现状限制：未与会话历史融合

当前 `POST /v1/images/generations` 是“网关 API Key 模式”的独立能力：
- 不会向 `chat_messages` 写入用户 prompt / assistant 图片结果；
- 因此“聊天历史页（JWT 模式）”刷新、跨端同步、分页拉取都看不到文生图结果。

会话历史的 DB 模型与写入方式：
- 消息表：`backend/app/models/message.py`（`chat_messages`，字段 `role/content/sequence`）
- 运行表：`backend/app/models/run.py`（`chat_runs`，字段 `status/request_payload/response_payload/output_text...`）
- 历史写入：`backend/app/services/chat_history_service.py`（如 `create_user_message` / `create_assistant_message_placeholder_after_user` / `finalize_assistant_message_after_user_sequence`）

---

## 2. 可选：用 Celery 执行“生图上游请求”吗？

可以，而且仓库里已有成熟范式（chat run）可直接复用：

- Celery App：`backend/app/celery_app.py`
- Chat 的 worker 任务：`backend/app/tasks/chat_run.py`
- 事件真相/回放：`backend/app/models/run_event.py`、`backend/app/repositories/run_event_repository.py`、`backend/app/services/run_event_bus.py`
- Chat 的 SSE（支持 DB replay + Redis 热通道）：`backend/app/api/v1/assistant_routes.py`（`create_message_endpoint` 的 streaming 分支）

Celery 配置键（已存在）：
- `.env.example`：`CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND`
- `backend/app/settings.py`：`CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND`、`CELERY_TASK_DEFAULT_QUEUE`、`CELERY_TIMEZONE`

---

## 3. 建议方案（待实现）：会话内文生图 + Celery 异步执行 + 写入历史

目标：用户在 Chat 页发起“文生图”后，结果像普通 assistant 消息一样进入 `GET /v1/conversations/{conversation_id}/messages` 历史列表，并能复用现有的“占位/终态更新/事件流”机制。

### 3.1 接口形态建议（不绑定具体路径名）

新增一个“会话内文生图”接口（JWT 鉴权，作用域为某个 conversation）：
- 鉴权：与聊天接口一致（`backend/app/api/v1/assistant_routes.py` 使用的 `require_jwt_token`）
- 输入：prompt + image params（`model/size/n/response_format` 等，可直接复用 `backend/app/schemas/image.py` 的 `ImageGenerationRequest`）
- 输出：
  - 非流式：立即返回“已入队”的标识（例如 run_id / message_id），并可选择阻塞等待终态（类似 chat 的非流式分支等待 terminal event）
  - 流式：`Accept: text/event-stream` 或请求体里显式开关触发 SSE（复用 chat 的判定方式）

> 对外的“网关 API Key 模式”仍保留 `POST /v1/images/generations`；会话内接口只是为前端 Chat 体验服务，两者并存。

### 3.2 数据落库建议（尽量不改前端/不新增 content type）

为了最小化前端改动，建议仍然把 assistant 的 message.content 存为“文本型”结构：

- user 消息：`{"type": "text", "text": "<用户提示词>"}`（现成写法见 `create_user_message`）
- assistant 消息：`{"type": "text", "text": "<包含图片 URL 的文本>"}`，其中每张图片 URL 单独成行，例如：
  - 第一行：`https://<gateway>/media/images/...`（或 Data URL）
  - 第二行：下一张 URL（如 n>1）

这样前端现有渲染能直接显示图片：
- 前端会把 content 结构 normalize 成字符串（`frontend/lib/normalizers/chat-normalizers.ts` 的 `normalizeMessageContent`）
- `MessageContent` 会把“单独一行的图片 URL”自动嵌入为图片（`frontend/components/chat/message-content.tsx` 的 `autoEmbedImageUrls`）

同时，建议把 OpenAI Images Response 原样落在 `chat_runs.response_payload`，便于审计与 Debug：
- request_payload：请求的 `ImageGenerationRequest`
- response_payload：返回的 `ImageGenerationResponse`（其中 `data[*].url` 推荐为短链）

### 3.3 Celery 任务执行流建议（复用 chat_run）

建议新增一个专用任务文件（结构参考 `backend/app/tasks/chat_run.py`）：

1) API 层：创建 user message + assistant placeholder（可选）+ run 记录（`status=queued`）  
2) API 层：向 `RunEvent` 写入 `message.created`（或复用已有事件类型），并发布到 Redis 热通道（参考 `create_message_endpoint` 的 streaming 分支）  
3) worker：拉取 run + conversation + project context（chat_run 已有完整样例）  
4) worker：使用 `CurlCffiClient`（`backend/app/http_client.py`）构造 httpx-compatible client，并调用 `ImageAppService.generate_image()`  
5) worker：将生成结果写入：
   - OSS（`backend/app/services/image_storage_service.py`）
   - `chat_runs`（status/response_payload/latency/error_code...）
   - assistant message.content（写成“图片 URL 多行文本”）
6) worker：写入终态 RunEvent（例如 `message.completed` / `message.failed`）并发布  

> 事件类型命名建议沿用现有 chat 的 `message.*`，这样前端 SSE 处理逻辑可最大复用（见 `frontend/lib/swr/use-messages.ts` 对 `message.created/message.delta/message.completed/message.failed` 的处理）。

### 3.4 失败重试与限流（建议）

- 上游失败的重试策略：
  - 业务内已有 provider key 的成功/失败记录与冷却（见 `backend/app/services/image_app_service.py` 对 `record_key_success/record_key_failure` 的使用）
  - Celery 层可针对网络类异常做 retry/backoff（实现时需注意幂等：同一个 run 不应重复写多条终态消息）
- 任务并发与队列：
  - 可复用 `CELERY_TASK_DEFAULT_QUEUE`，或为生图单独队列（实现时决定）
  - 生图任务可能比 chat 更重，建议与 chat 分队列/独立 worker 以免互相挤占

---

## 4. 运维与调试指引（现成能力）

### 4.1 启动 Celery worker

在 `backend/` 目录下：

```bash
celery -A app.celery_app.celery_app worker -l info
```

### 4.2 事件流真相与排障

- 事件真相表：`chat_run_events`（模型见 `backend/app/models/run_event.py`）
- Redis 热通道 channel：`run_events:{run_id}`（见 `backend/app/services/run_event_bus.py` 的 `run_event_channel`）
- DB 回放：`backend/app/repositories/run_event_repository.py` 的 `list_run_events`

---

## 5. 相关文件索引（快速定位）

- 文生图入口：`backend/app/api/v1/image_routes.py`、`backend/app/services/image_app_service.py`
- OSS/短链：`backend/app/services/image_storage_service.py`、`backend/app/api/v1/media_routes.py`
- Celery 基础：`backend/app/celery_app.py`、`backend/app/tasks/chat_run.py`
- 会话历史写入：`backend/app/services/chat_history_service.py`
- SSE 与 RunEvent：`backend/app/api/v1/assistant_routes.py`、`backend/app/models/run_event.py`、`backend/app/services/run_event_bus.py`
