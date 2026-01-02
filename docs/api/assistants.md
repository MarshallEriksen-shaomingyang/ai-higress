# Assistants / Conversations / Messages API

> 认证：JWT（`Authorization: Bearer <access_token>`）

## Assistants

### GET `/v1/assistants`

查询当前用户的助手列表（支持按项目过滤）。

Query:
- `project_id` (optional): UUID（MVP: project_id == api_key_id）
- `cursor` (optional): string（当前实现为 offset 游标）
- `limit` (optional): 1-100

Response:
```json
{
  "items": [
    {
      "assistant_id": "uuid",
      "project_id": "uuid",
      "name": "默认助手",
      "system_prompt": "你是一个严谨的助手",
      "default_logical_model": "gpt-4.1",
      "title_logical_model": "gpt-4.1",
      "created_at": "2025-12-19T00:00:00Z",
      "updated_at": "2025-12-19T00:00:00Z"
    }
  ],
  "next_cursor": "30"
}
```

### POST `/v1/assistants`

创建助手。

说明：
- `default_logical_model` 支持设置为 `"auto"`：表示由 Bandit（Thompson Sampling）在项目配置的 `candidate_logical_models` 中选择一个模型作为本次 baseline 的实际模型（单路执行，不并行）。
- 若项目未配置 `candidate_logical_models`，则 `"auto"` 会返回 400。
- `project_id`（MVP: project_id == api_key_id）可为空；若传入，则后端会校验该项目是否存在且归属当前用户。
- `default_logical_model` 也支持设置为 `"__project__"`：表示跟随项目级默认模型（见 Project Chat Settings）。

Request:
```json
{
  "project_id": "uuid",
  "name": "默认助手",
  "system_prompt": "你是一个严谨的助手",
  "default_logical_model": "gpt-4.1",
  "title_logical_model": "gpt-4.1",
  "model_preset": {"temperature": 0.2}
}
```

说明：
- `title_logical_model`（可选）：会话标题生成模型。
  - 当创建会话时不传 `title`，并且在该会话发送第一条用户消息后，后端会使用该模型基于“首问”自动生成 `Conversation.title`（尽力而为，不影响主聊天流程）。
  - 若不传该字段，则不会自动生成标题（保持 `title` 为空，前端可按无标题展示）。
  - 传 `"__project__"`：跟随项目级标题模型（见 Project Chat Settings）。

Errors:
- `404 not_found`：项目不存在或无权访问（`project_id` 传错）

### GET `/v1/assistants/{assistant_id}`

获取助手详情。

### PUT `/v1/assistants/{assistant_id}`

更新助手（支持归档 `archived=true`）。

可选字段（部分）：
- `title_logical_model`: string | null
  - 传具体模型：开启会话首问自动命名。
  - 传 `null`：关闭自动命名（恢复为跟随/不启用）。

### DELETE `/v1/assistants/{assistant_id}`

删除助手（硬删除，会级联删除该助手下的会话与消息历史）。

## Conversations

### POST `/v1/conversations`

创建会话（按助手分组）。

Request:
```json
{
  "assistant_id": "uuid",
  "project_id": "uuid",
  "title": "可选标题"
}
```

Errors:
- `404 not_found`：项目不存在或无权访问（`project_id` 传错）
- `403 forbidden`：助手不属于当前项目

Response（摘要）:
```json
{
  "conversation_id": "uuid",
  "assistant_id": "uuid",
  "project_id": "uuid",
  "title": "可选标题",
  "last_activity_at": "datetime",
  "archived_at": null,
  "is_pinned": false,
  "last_message_content": null,
  "unread_count": 0,
  "summary_text": null,
  "summary_until_sequence": 0,
  "summary_updated_at": null,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### GET `/v1/conversations?assistant_id=...`

按助手查询会话列表（摘要）。

Query:
- `assistant_id` (required): UUID
- `cursor` (optional): string
- `limit` (optional): 1-100
- `archived` (optional): bool，默认为 `false`（仅返回未归档会话）；传 `true` 返回已归档会话

### PUT `/v1/conversations/{conversation_id}`

更新会话（支持归档/取消归档）。

Request:
```json
{
  "title": "可选新标题",
  "archived": true,
  "summary": "可选摘要（用户可见，可编辑；传 null/空字符串表示清空）"
}
```

说明：
- 归档后会话不会出现在会话列表中，但仍可通过 messages 接口读取历史。
- `summary` 用于“压缩上下文”：服务端会将 `summary_text` 作为 system message 注入上游请求，并仅携带 `summary_until_sequence` 之后的消息作为上下文（等价于在同一会话内重置模型会话）。

### DELETE `/v1/conversations/{conversation_id}`

删除会话（硬删除，会级联删除会话消息与 run/eval 数据）。

## Project Chat Settings

### GET `/v1/projects/{project_id}/chat-settings`

获取项目级聊天设置（MVP: `project_id == api_key_id`）。

Response:
```json
{
  "project_id": "uuid",
  "default_logical_model": "auto",
  "title_logical_model": "gpt-4.1",
  "kb_embedding_logical_model": "your-embedding-logical-model",
  "kb_memory_router_logical_model": "your-memory-router-logical-model"
}
```

说明：
- `default_logical_model`：项目默认聊天模型；当助手的 `default_logical_model` 设置为 `"__project__"` 时生效。
- `title_logical_model`：项目默认标题模型；当助手的 `title_logical_model` 设置为 `"__project__"` 时生效；为空表示不自动命名。
- `kb_embedding_logical_model`：项目级 embedding 模型（用于知识库/向量化能力，例如 Qdrant/RAG）。
  - 当后端配置了 `KB_GLOBAL_EMBEDDING_LOGICAL_MODEL`（全局统一 embedding）时，该字段将被忽略。
  - 为空表示未配置（由上层策略决定是否启用/如何选择）。
- `kb_memory_router_logical_model`：项目级“聊天记忆路由模型”，用于判断是否写入记忆，以及写入 user/system 维度。为空表示由后端选择默认。

### PUT `/v1/projects/{project_id}/chat-settings`

更新项目级聊天设置（只更新传入字段）。

Request:
```json
{
  "default_logical_model": "auto",
  "title_logical_model": "gpt-4.1",
  "kb_embedding_logical_model": "your-embedding-logical-model",
  "kb_memory_router_logical_model": "your-memory-router-logical-model"
}
```

说明：
- 传 `null` 可清空对应字段（恢复默认行为）。

## Memory Route (Dry Run)

### POST `/v1/projects/{project_id}/memory-route/dry-run`

灰测“聊天记忆路由模型”的决策能力：给定一段对话片段，返回模型的原始输出与解析后的决策结果。

Request:
```json
{
  "transcript": "user: ...\\nassistant: ...",
  "router_logical_model": "可选：临时覆盖模型"
}
```

Response:
```json
{
  "project_id": "uuid",
  "router_logical_model": "your-memory-router-logical-model",
  "should_store": true,
  "scope": "user",
  "memory_text": "...\n...",
  "memory_items": [
    {
      "content": "独立陈述句",
      "category": "preference",
      "keywords": ["k1", "k2"]
    }
  ],
  "structured_ops": [
    {
      "op": "UPSERT",
      "scope": "user",
      "category": "preference",
      "key": "response.style",
      "value": "concise",
      "confidence": 0.8,
      "reason": "可选：提取理由"
    }
  ],
  "raw_model_output": "{...}"
}
```

说明：
- `router_logical_model`：优先使用请求里传入的覆盖值；否则使用项目设置 `kb_memory_router_logical_model`。
- `raw_model_output`：便于灰测对齐模型输出格式与边界判断；线上写入流程不建议存储该字段。

## Messages / Runs

### POST `/v1/conversations/{conversation_id}/messages`

发送一条用户消息并执行 baseline。

支持两种模式：
- **默认 non-stream**：等待 baseline run 完成后返回 JSON。
- **streaming=true（SSE）**：以 `text/event-stream` 返回流式事件，前端可实时渲染 assistant 回复。

Request:
```json
{
  "content": "你好",
  "input_audio": {
    "audio_id": "uuid",
    "format": "wav"
  },
  "override_logical_model": "gpt-4.1",
  "model_preset": {"temperature": 0.2},
  "bridge_agent_id": "aws-dev-server",
  "bridge_agent_ids": ["aws-dev-server", "home-nas"],
  "bridge_tool_selections": [
    {"agent_id": "aws-dev-server", "tool_names": ["search", "summarize"]}
  ],
  "streaming": false
}
```

说明：
- `input_audio`（可选）：用户语音输入附件。
  - 先调用 `POST /v1/conversations/{conversation_id}/audio-uploads` 上传语音文件，拿到 `object_key`；
  - 上传响应里会返回 `audio_id`，推荐在发送消息时携带 `input_audio.audio_id` 引用该音频（便于复用/共享）；
  - 当 `input_audio` 存在时，`content` 可为空字符串。
- `bridge_agent_id`（可选，兼容字段）：指定本次对话的目标 Agent，用于开启 MCP/Bridge 的工具调用能力（LLM tool_calls -> Bridge INVOKE -> tool_result -> 继续生成）。
- `bridge_agent_ids`（可选，推荐）：指定本次对话的目标 Agent 列表（多选）。
  - 不传则保持原有“纯聊天 baseline”行为。
  - 当传入多个 Agent 时，后端会合并所有工具并注入模型；为了避免重名，会对工具名做别名映射（模型看到的是别名），实际执行时仍会路由到对应 Agent 的原始工具名。
  - 当前实现为 MVP：工具调用发生时，tool 输出日志通过 `/v1/bridge/events` 或 `/v1/bridge/tool-events` 另行查看。
- `bridge_tool_selections`（可选）：为每个 Agent 指定要注入的工具子集。未提供时默认注入该 Agent 的全部工具。
  - 单次最多 5 个 Agent，每个 Agent 最多 30 个工具名。
  - 当 `bridge_tool_selections` 和 `bridge_agent_id(s)` 同时出现时，Agent 列表取二者并集（去重）。
- `streaming`（可选，默认 `false`）：是否使用 SSE 流式返回。
  - 当提供 `bridge_agent_id` / `bridge_agent_ids` 且该 Agent 存在可用工具时，后端会向模型注入工具并允许 tool_calls；`bridge_tool_selections` 仅用于限制注入的工具子集。
  - 流式模式下：先推送模型的 `message.delta`，若模型触发 tool_calls，会在流式结束后执行工具循环并补充推送最终回复（仍然通过 `message.delta`）。

Response:
```json
{
  "message_id": "uuid",
  "baseline_run": {
    "run_id": "uuid",
    "requested_logical_model": "gpt-4.1",
    "status": "succeeded",
    "output_preview": "…",
    "tool_invocations": [
      {
        "req_id": "req_...",
        "agent_id": "aws-dev-server",
        "tool_name": "filesystem__readFile",
        "tool_call_id": "call_..."
      }
    ]
  }
}
```

说明：
- 当工具循环达到上限或超时，会将 `baseline_run.status` 标记为 `failed`，并在 `baseline_run.error_code` 返回错误码（示例：`TOOL_LOOP_FAILED` / `TOOL_LOOP_MAX_ROUNDS` / `TOOL_LOOP_MAX_INVOCATIONS` / `TOOL_LOOP_TIMEOUT`）。

#### Streaming (SSE) Response

当 `streaming=true`（或请求头包含 `Accept: text/event-stream`）时，返回 `text/event-stream`：

- `event: message.created`：包含 `user_message_id` / `assistant_message_id` / `baseline_run`
  - `request_context`（可选）：本次请求的上下文快照（模型 + 参数 + Bridge 工具选择），用于前端在“对比/重试/断线重连”等场景复用同一套配置。
- `event: message.delta`：增量 token（字段 `delta`）
- `event: message.completed` / `message.failed`：结束事件，包含最终 `baseline_run`
- `event: done` + `data: [DONE]`

### POST `/v1/conversations/{conversation_id}/audio-uploads`

上传用户语音文件（用于语音输入），并落存储（本地/OSS/S3）。

- JWT 鉴权（仅会话所有者可上传）
- 返回 `object_key`（消息发送时引用）与 `url`（网关签名短链，可用于播放/下载：`GET /media/audio/...`）

Request: `multipart/form-data`
- `file`: 音频文件（当前仅支持 WAV/MP3；最大 10MB）

Response:
```json
{
  "object_key": "generated-images/user-audio/<user_id>/2025/01/01/<uuid>.wav",
  "audio_id": "uuid",
  "url": "http://<gateway>/media/audio/... ?expires=...&sig=...",
  "content_type": "audio/wav",
  "size_bytes": 12345,
  "format": "wav"
}
```

### POST `/v1/conversations/{conversation_id}/audio-transcriptions`

会话内语音转文字（STT）：上传音频并返回转写文本（用于“语音输入/听写”）。

- JWT 鉴权（仅会话所有者可调用）
- 不落库、不走 OSS
- 复用网关选路：要求所选逻辑模型具备 `audio` 能力

Request: `multipart/form-data`
- `file`: 音频文件（最大 10MB）
- `model`（可选）：逻辑模型 ID；为空则回退到该会话助手的 `default_logical_model`
- `language`（可选）：例如 `zh` / `zh-CN` / `en`
- `prompt`（可选）：转写提示词（部分上游支持）

Response:
```json
{ "text": "转写后的文本" }
```

### GET `/v1/audio-assets`

音频资产库：列出当前用户可见的音频（自己的 + 他人已分享的 public）。

Query:
- `visibility`（可选）：`all`(默认) | `private`(仅我的) | `public`(仅共享)
- `limit`（可选）：默认 50，最大 200

Response（截断）：
```json
{
  "items": [
    {
      "audio_id": "uuid",
      "owner_id": "uuid",
      "owner_username": "alice",
      "owner_display_name": "Alice",
      "object_key": "generated-images/user-audio/<owner_id>/2025/01/01/<uuid>.wav",
      "url": "http://<gateway>/media/audio/... ?expires=...&sig=...",
      "content_type": "audio/wav",
      "size_bytes": 12345,
      "format": "wav",
      "filename": "input.wav",
      "display_name": "input.wav",
      "visibility": "private | public",
      "created_at": "2026-01-01T00:00:00+00:00",
      "updated_at": "2026-01-01T00:00:00+00:00"
    }
  ]
}
```

### PUT `/v1/audio-assets/{audio_id}/visibility`

切换“分享开关”（`private`/`public`）。仅 owner 可操作。

Request:
```json
{ "visibility": "public" }
```

### DELETE `/v1/audio-assets/{audio_id}`

删除音频资产记录（仅 owner 可删除）。

### POST `/v1/conversations/{conversation_id}/image-generations`

会话内文生图（写入聊天历史），用于在 Chat 页面里“像发消息一样出图”。

特点：
- 认证：JWT（同 Messages）
- 结果会持久化到 `chat_messages`，可用于历史记录/多端同步
- 推荐使用 SSE（等待体验更好）
- 返回内容默认走 `response_format="url"`（本地磁盘或 OSS/S3 + `/media/images` 短链），避免把大体积 base64 写入历史

Request:
```json
{
  "prompt": "a cat sitting on a chair",
  "model": "gpt-image-1",
  "n": 1,
  "size": "1024x1024",
  "response_format": "url",
  "extra_body": {
    "google": {
      "generationConfig": {
        "imageConfig": {"aspectRatio": "16:9"}
      }
    }
  },
  "streaming": true
}
```

说明：
- `streaming=true` 或请求头包含 `Accept: text/event-stream` 时返回 SSE
- `response_format` 当前会被服务端强制为 `url`（历史落库不写 base64）
- `extra_body`（可选）：网关保留扩展字段；当 `model` 触发 Google lane 时，`extra_body.google` 会合并到上游请求体中（覆盖同名字段）

#### Streaming (SSE) Response

- `event: message.created`：包含 `user_message_id` / `assistant_message_id` / `baseline_run`
- `event: message.delta`：阶段提示（字段 `delta`，例如“正在生成图片…”）
- `event: message.completed` / `message.failed`：结束事件，包含最终 `baseline_run`
  - `image_generation`：结构化结果（用于前端渲染图片卡片）
- `event: done` + `data: [DONE]`

`message.completed` 示例（截断）：
```json
{
  "type": "message.completed",
  "conversation_id": "uuid",
  "assistant_message_id": "uuid",
  "baseline_run": { "run_id": "uuid", "requested_logical_model": "gpt-image-1", "status": "succeeded" },
  "kind": "image_generation",
  "image_generation": {
    "type": "image_generation",
    "status": "succeeded",
    "prompt": "a cat sitting on a chair",
    "params": { "model": "gpt-image-1", "n": 1, "size": "1024x1024", "response_format": "url" },
    "images": [{ "url": "https://<gateway>/media/images/<object_key>?expires=...&sig=..." }],
    "created": 1700000000
  }
}
```

#### 历史消息 content（assistant）

拉取消息列表 `GET /v1/conversations/{conversation_id}/messages` 时，assistant 的 `content` 会包含：
```json
{
  "type": "image_generation",
  "status": "pending|succeeded|failed",
  "prompt": "...",
  "params": { "model": "...", "n": 1, "size": "1024x1024", "response_format": "url" },
  "images": [{ "object_key": "...", "url": "https://<gateway>/media/images/...&sig=..." }],
  "error": "..." 
}
```

说明：
- 服务端会基于 `object_key` 动态生成新的 `/media/images` 签名短链 `url`，避免历史里长期存储过期签名。

### POST `/v1/conversations/{conversation_id}/video-generations`

会话内视频生成（写入聊天历史），用于在 Chat 页面里“像发消息一样出视频”。

特点：
- 认证：JWT（同 Messages）
- 结果会持久化到 `chat_messages`，可用于历史记录/多端同步
- 推荐使用 SSE（等待体验更好）
- 返回内容走 `/media/videos` 签名短链，避免把大文件直链长期写入历史

Request:
```json
{
  "prompt": "A cinematic shot of a majestic lion in the savannah.",
  "model": "sora-2 | veo-3.1-generate-preview",
  "size": "1280x720",
  "seconds": 8,
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "negative_prompt": "cartoon, drawing, low quality",
  "extra_body": {
    "google": {
      "parameters": {
        "negativePrompt": "cartoon, low quality"
      }
    }
  },
  "streaming": true
}
```

说明：
- `streaming=true` 或请求头包含 `Accept: text/event-stream` 时返回 SSE
- `extra_body`（可选）：网关保留扩展字段；当选中对应 lane 时会合并到上游请求体中（覆盖同名字段）
  - `negative_prompt` 会自动映射到 Gemini Veo 的 `parameters.negativePrompt`（若 `extra_body.google.parameters.negativePrompt` 已提供，则以扩展字段为准）

#### Streaming (SSE) Response

- `event: message.created`：包含 `user_message_id` / `assistant_message_id` / `baseline_run`
- `event: message.delta`：阶段提示（字段 `delta`，例如“正在生成视频…”）
- `event: message.completed` / `message.failed`：结束事件，包含最终 `baseline_run`
  - `video_generation`：结构化结果（用于前端渲染视频卡片）
- `event: done` + `data: [DONE]`

`message.completed` 示例（截断）：
```json
{
  "type": "message.completed",
  "conversation_id": "uuid",
  "assistant_message_id": "uuid",
  "baseline_run": { "run_id": "uuid", "requested_logical_model": "sora-2", "status": "succeeded" },
  "kind": "video_generation",
  "video_generation": {
    "type": "video_generation",
    "status": "succeeded",
    "prompt": "A cinematic shot of a majestic lion in the savannah.",
    "params": { "model": "sora-2", "size": "1280x720", "seconds": 8 },
    "videos": [{ "url": "https://<gateway>/media/videos/<object_key>?expires=...&sig=..." }],
    "created": 1700000000
  }
}
```

#### 历史消息 content（assistant）

拉取消息列表 `GET /v1/conversations/{conversation_id}/messages` 时，assistant 的 `content` 会包含：
```json
{
  "type": "video_generation",
  "status": "pending|succeeded|failed",
  "prompt": "...",
  "params": { "model": "...", "size": "1280x720", "seconds": 8 },
  "videos": [{ "object_key": "...", "url": "https://<gateway>/media/videos/...&sig=..." }],
  "error": "..." 
}
```

说明：
- 服务端会基于 `object_key` 动态生成新的 `/media/videos` 签名短链 `url`，避免历史里长期存储过期签名。

### POST `/v1/messages/{assistant_message_id}/regenerate`

基于已有的 user 消息重新生成一条 assistant 回复（会清空原 assistant 消息并生成新内容）。

Request（可选 Body，用于显式携带模型参数与工具选择，避免“重试不带工具/参数”）：
```json
{
  "override_logical_model": "gpt-4.1",
  "model_preset": {"temperature": 0.2},
  "bridge_agent_id": "aws-dev-server",
  "bridge_agent_ids": ["aws-dev-server", "home-nas"],
  "bridge_tool_selections": [
    {"agent_id": "aws-dev-server", "tool_names": ["search", "summarize"]}
  ]
}
```

Response:
```json
{
  "assistant_message_id": "uuid",
  "baseline_run": {
    "run_id": "uuid",
    "requested_logical_model": "gpt-4.1",
    "status": "succeeded",
    "output_preview": "..."
  }
}
```

### GET `/v1/conversations/{conversation_id}/messages`

分页返回消息列表（默认只返回 run 摘要；assistant 正文在 message.content）。

### DELETE `/v1/conversations/{conversation_id}/messages`

清空会话消息历史（保留会话本身）。

说明：
- 会删除该会话下的全部消息，并级联删除对应的 run / eval 数据。
- `conversation_id` 不变；会话本身不会被删除。
- 会话的 `last_message_content` 会被清空，`unread_count` 会归零。

成功响应：204 No Content

### GET `/v1/runs/{run_id}`

惰性加载 run 详情（包含 request/response payload 与 output_text）。

### POST `/v1/runs/{run_id}/cancel`

取消一个 run（best-effort）。

行为：
- 写入 Redis cancel 标记，供 worker 及时终止执行；
- 将 `Run.status` 置为 `canceled`，并追加事件：
  - `run.canceled`
  - `message.failed`（用于兼容 `message.*` SSE 订阅方及时收敛终态）

Response：同 `GET /v1/runs/{run_id}`（返回更新后的 RunDetail）。

### GET `/v1/runs/{run_id}/events`

订阅 Run 的执行事件流（SSE replay，用于断线重连回放）。

Query:
- `after_seq`（可选，默认 `0`）：从该序号之后开始回放/续订（用于断线重连）。
- `limit`（可选，默认 `200`，最大 `1000`）：本次从 DB 回放的最大事件数量。

Response（`text/event-stream`）：
- DB 回放阶段：按 `seq` 升序输出事件；每条事件的 `event:` 为该行的 `event_type`（例如 `message.created` / `tool.status` / `message.completed` 等）。
- `event: replay.done`：表示 DB 回放完成，后续进入 Redis 热通道实时订阅；`data.type` 为 `replay.done`。
- `event: heartbeat`：空闲时心跳；`data.type` 为 `heartbeat`。

`data` 结构（每条 run event）：
```json
{
  "type": "run.event",
  "run_id": "uuid",
  "seq": 1,
  "event_type": "message.created",
  "created_at": "2025-12-25T00:00:00+00:00",
  "payload": {
    "type": "message.created"
  }
}
```
