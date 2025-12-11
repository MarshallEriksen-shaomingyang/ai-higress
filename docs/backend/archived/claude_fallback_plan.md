# Claude Messages 兼容兜底方案

## 目标
1. `/v1/messages` 对外始终保持 Claude/Anthropic 的请求与响应格式。
2. 当映射到的上游不支持 `/v1/message(s)` 时，自动切换到该提供商的 `/v1/chat/completions`，并把 OpenAI 风格响应转换回 Claude 风格。
3. 非流式与流式路径均需兜底；流式 fallback 需继续输出 Claude SSE 事件（`message_start`、`content_block_delta` 等）。
4. 方案应与动态模型路由、session 绑定、上下游日志复用，以最小入侵方式集成。

## 设计要点
### 1. Provider/LogicalModel 元数据
- 在 `ProviderConfig` 和动态发现的 `PhysicalModel` 中补充“Claude Messages 支持能力”。
  - 新增 `messages_path: Optional[str]` 字段，默认 `/v1/message`，可通过 `providers.messages_path` 列配置。
  - 对仅有 Chat Completions 的提供商将该字段置空，表示需要 fallback。
- 更新 `app/provider/config.py` 解析逻辑：读取数据库中的 `messages_path`，允许存储空字符串并转换为 `None`。
- 静态 Redis 逻辑模型结构中同样透传 `messages_path`，便于后续扩展（本方案先只在动态逻辑模型中使用）。

### 2. 路由入口调整
- `claude_messages_endpoint` 继续写 `_apiproxy_api_style="claude"`，并额外带上 `_apiproxy_messages_path`（首选路径）与 `_apiproxy_fallback_chat_path`（默认 `/v1/chat/completions`）。
- `chat_completions` 在拆解 payload 时保留上述 hint，供候选 upstream 循环使用。

### 3. Fallback 决策逻辑
- 在非流式和流式循环中，记录 `base_endpoint`，根据 hint 判断：
  - 首次尝试：若 provider 指定了 `messages_path`，使用 `_apply_upstream_path_override` 替换路径。
  - 当返回 404 / 400（包含 `Invalid URL` 文本）/ 405 时，且 `api_style="claude"`、`messages_path` 非空，即触发 fallback。
  - fallback 之前复用同一 headers/session 绑定逻辑。
- fallback 请求体：用 `_claude_messages_to_openai_chat_payload` 把 Claude 消息转换为 OpenAI `messages`。
- fallback 响应：
  - 非流式：`_openai_chat_to_claude_response` -> `JSONResponse`。
  - 流式：`OpenAIToClaudeStreamAdapter` 解析 `chat.completion.chunk`，输出 Claude SSE 事件。
- 出错处理：
  - fallback 请求若仍返回可重试错误，允许循环到下一个 provider。
  - fallback 请求若产生非重试错误，直接 502，并将错误写入 context store。

### 4. Gemini 适配
- 将现有 Gemini -> OpenAI 的转换函数抽到 helper 区域，供主流程与 fallback 复用。
- 在非流式/流式主循环中，仅当 `api_style=="openai"` 时触发 Gemini 适配，避免 Claude 流程误用。

### 5. 工具函数组织
- 在 `app/routes.py` 顶部集中 helper：
  - `_apply_upstream_path_override`
  - Claude/OpenAI 相互转换函数
  - `OpenAIToClaudeStreamAdapter`
- 若文件过大，可在后续迭代抽成独立模块；当前优先完成功能。

### 6. 测试计划
1. **/v1/messages 路径覆盖**：mock provider 仅实现 `/v1/message`，请求 `/v1/messages` 应命中该路径。
2. **Fallback（非流式）**：`/v1/message` 返回 404，fallback 到 `/v1/chat/completions`，最终响应仍为 Claude JSON。
3. **Fallback（流式）**：`/v1/message` 在 streaming handshake 前抛 404，fallback 后输出 Claude SSE 事件序列。
4. **Gemini 适配回归**：非流式/流式各 1 个测试，确保 `_build_openai_completion_from_gemini` 与流式 adapter 正常。
5. **动态逻辑模型**：验证 `_build_dynamic_logical_model_for_group` 按 `api_style` 选择默认路径（Claude -> `/v1/messages`，OpenAI -> `/v1/chat/completions`）。
6. **鉴权回归**：已有 X-API-Key 测试可保留，确认变更不影响。

### 7. 实施步骤
1. 更新 provider 配置（新增 `messages_path`）、`.env` 示例与 README 配置表。
2. 在 `app/routes.py` 新增 helper/adapters。
3. 调整 `chat_completions`：
   - 解析 `_apiproxy_messages_path` / `_apiproxy_fallback_chat_path`。
   - 在非流式与流式循环中加入 fallback 分支，处理 session 绑定与 context 保存。
4. 重构 Gemini 相关函数，确保 fallback 也可复用。
5. 编写/更新测试（必要时拆分文件），覆盖以上场景。
6. 本地自检（不执行 `pytest`），提示用户运行 `pytest tests/test_chat_greeting.py`。
