# APIProxy - AI 网关

[English README](README.md)

APIProxy 是一个基于 FastAPI 构建的高性能 AI 代理网关。它为上游 AI 服务提供了统一、兼容 OpenAI 标准的接口，并内置了多提供商路由、模型缓存、会话管理、格式转换和跨厂商故障转移等能力，帮助你在一个出口下接入多家大模型服务。

---

## 功能特性

- **兼容 OpenAI 的 API**  
  提供 `/v1/chat/completions`、`/v1/responses` 和 `/models` 端点，以便您可以重用现有的 OpenAI SDK 和工具。

- **动态多提供商路由**  
  - **逻辑模型**: 将多个物理提供商模型映射到单个逻辑模型（例如，“fast-model” -> OpenAI 的 `gpt-3.5-turbo`、Gemini 的 `gemini-pro`）。
  - **零配置模型路由**: 如果请求的模型未被显式映射，网关会自动发现支持该模型的提供商，并动态创建路由组。
  - **基于权重和指标的调度**: 根据配置的权重和运行时性能指标分配流量。

- **跨提供商故障转移**  
  在流式和非流式请求中，当遇到可重试的错误（例如 429、5xx）时，自动在另一家提供商上重试请求。

- **请求格式适配器**  
  - 自动将不同的请求格式转换为统一的 OpenAI 风格的 `messages` 结构。
  - 支持 Gemini 风格的 `input`、Claude 风格的请求以及 OpenAI Responses API (`/v1/responses`)。
  - 处理带前缀的模型名称（例如 `my-provider/some-model`），以简化路由逻辑。

- **会话粘性**  
  通过 `X-Session-Id` 头将对话绑定到首次选择的提供商，以在多消息对话中保持上下文。

- **模型列表聚合与缓存**  
  从所有已配置的提供商处获取模型列表，将其规范化为 OpenAI 风格的 `/models` 响应，并缓存在 Redis 中。

- **支持流式与非流式响应**  
  通过 `stream: true` 或 `Accept: text/event-stream` 头自动检测客户端对流式响应的需求。

- **会话上下文存储**  
  使用 `X-Session-Id` 头将请求/响应片段持久化到 Redis，以便通过 HTTP 端点检查简单的对话历史。

- **灵活配置**  
  上游地址、API 密钥、Redis URL、提供商权重和故障转移行为都通过环境变量进行控制。

- **Docker 友好**  
  包含一个 `docker-compose.yml` 文件，可通过单个命令启动 API 网关和 Redis。

---

## 技术栈

- Web 框架：FastAPI
- ASGI 服务器：Uvicorn
- HTTP 客户端：HTTPX
- 缓存与存储：Redis
- 配置管理：Pydantic Settings
- 依赖管理：uv / pip

---

## 🚀 快速开始

推荐优先使用 Docker 进行部署，保证本地与服务器环境一致。

### 先决条件

- Docker 与 Docker Compose
- Git

### 1. 使用 Docker 部署（推荐）

1. 克隆项目：

   ```bash
   git clone https://github.com/MarshallEriksen-shaomingyang/ai-higress.git
   cd APIProxy
   ```

2. 创建并配置 `.env`：

   ```bash
   cp .env.example .env
   ```

3. 编辑 `.env` 配置文件：

   ```env
   # Redis地址（使用docker-compose启动时可用默认值）
   REDIS_URL=redis://redis:6379/0

   # ⚠️ 重要：设置你的认证token
   APIPROXY_AUTH_TOKEN=timeline

   # 添加你想用的AI服务提供商
   LLM_PROVIDERS=openai,gemini,claude

   # OpenAI配置
   LLM_PROVIDER_openai_NAME=OpenAI
   LLM_PROVIDER_openai_BASE_URL=https://api.openai.com/v1
   LLM_PROVIDER_openai_API_KEY=你的OpenAI密钥

   # Gemini配置
   LLM_PROVIDER_gemini_NAME=Gemini
   LLM_PROVIDER_gemini_BASE_URL=https://generativelanguage.googleapis.com/v1
   LLM_PROVIDER_gemini_API_KEY=你的Gemini密钥

   # Claude配置
   LLM_PROVIDER_claude_NAME=Claude
   LLM_PROVIDER_claude_BASE_URL=https://api.anthropic.com
   LLM_PROVIDER_claude_API_KEY=你的Claude密钥
   ```

4. 🔑 生成API密钥（非常重要！）：

   ```bash
   uv run scripts/encode_token.py timeline
   ```

   会输出类似这样的内容：
   ```
   dGltZWxpbmU=  # 这就是你的加密token
   ```

   **保存这个加密后的token** - 调用API时需要用到！

5. 启动服务：

   ```bash
   docker-compose up -d
   ```

   服务将在 `http://localhost:8000` 上启动。

6. 使用curl测试：

   ```bash
   curl -X POST "http://localhost:8000/v1/chat/completions" \
     -H "Authorization: Bearer dGltZWxpbmU=" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "gpt-3.5-turbo",
       "messages": [{"role": "user", "content": "你好！"}]
     }'
   ```

7. 查看日志（可选）：

   ```bash
   docker-compose logs -f api
   ```

8. 停止服务：

   ```bash
   docker-compose down
   ```

### 2. 本地开发环境

1. 克隆项目并安装依赖：

   ```bash
   git clone <https://github.com/MarshallEriksen-shaomingyang/ai-higress.git>
   cd APIProxy
   python -m venv .venv
   source .venv/bin/activate
   pip install .
   ```

2. 配置 `.env`：

   ```bash
   cp .env.example .env
   ```

   - 将 `REDIS_URL` 指向本地 Redis；
   - 配置 `APIPROXY_AUTH_TOKEN` 作为外部调用本网关的 API token（可用 `uv run scripts/encode_token.py <token>` 生成 Base64；客户端需要携带其 Base64 编码）；
   - 配置 `LLM_PROVIDERS` 与 `LLM_PROVIDER_{id}_*`；
   - 如需自定义重试状态码，设置 `LLM_PROVIDER_{id}_RETRYABLE_STATUS_CODES`。

3. 启动开发服务器：

   ```bash
   apiproxy
   # 或
   uvicorn main:app --reload
   ```

   默认监听 `http://localhost:8000`。

---

## 配置说明

应用通过环境变量配置，通常从 `.env` 文件加载。完整配置示例见 `.env.example` 和 `docs/configuration.md`。

常用环境变量：

| 变量名                          | 说明                                                                 | 默认值                    |
| ------------------------------- | -------------------------------------------------------------------- | ------------------------- |
| `REDIS_URL`                     | Redis 连接字符串                                                     | `redis://redis:6379/0`    |
| `APIPROXY_AUTH_TOKEN`           | 网关对外认证 token（可用 `uv run scripts/encode_token.py <token>` 生成 Base64），客户端需在 Authorization 头中携带其 Base64 编码 | `timeline`                |
| `MODELS_CACHE_TTL`              | 模型列表缓存过期时间（秒）                                           | `300`                     |
| `MASK_AS_BROWSER`               | 是否伪装为浏览器（附加 UA/Origin/Referer 等头）                      | `True`                    |
| `MASK_USER_AGENT`               | 伪装为浏览器时使用的 User-Agent                                     | 见 `.env.example`         |
| `MASK_ORIGIN`                   | 可选，伪装为浏览器时附加的 Origin                                   | `None`                    |
| `MASK_REFERER`                  | 可选，伪装为浏览器时附加的 Referer                                  | `None`                    |
| `LOG_LEVEL`                     | 网关日志级别（`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`）          | `INFO`                    |
| `LOG_TIMEZONE`                  | 日志时间戳使用的时区（如 `Asia/Shanghai`，缺省为系统本地时区）      | 系统本地时区              |
| `LLM_PROVIDERS`                 | 逗号分隔的提供商 ID 列表，例如 `openai,gemini,claude`               | `None`                    |
| `LLM_PROVIDER_{id}_NAME`        | 提供商显示名称                                                       | 必填                      |
| `LLM_PROVIDER_{id}_BASE_URL`    | 提供商 API 基础地址                                                 | 必填                      |
| `LLM_PROVIDER_{id}_API_KEY`     | 访问该提供商的密钥或 token                                           | 必填                      |
| `LLM_PROVIDER_{id}_MODELS_PATH` | 模型列表路径，通常为 `/v1/models`                                   | `/v1/models`              |
| `LLM_PROVIDER_{id}_WEIGHT`      | 路由基础权重（影响流量分配）                                         | `1.0`                     |
| `LLM_PROVIDER_{id}_REGION`      | 区域标签，如 `global`、`us-east`                                    | `None`                    |
| `LLM_PROVIDER_{id}_MAX_QPS`     | 提供商允许的最大 QPS                                                | `None`                    |
| `LLM_PROVIDER_{id}_RETRYABLE_STATUS_CODES` | 可重试的 HTTP 状态码列表或区间，例如 `429,500,502-504`。如不配置，则对 `openai` / `gemini` / `claude/anthropic` 使用默认的 `[429,500,502,503,504]` | `None`（按内置默认或通用规则） |

> 注意：`LLM_PROVIDERS` 中的 id 必须和下面变量中的 `{id}` 一一对应。  
> 例如：
> ```env
> LLM_PROVIDERS=a4f
> LLM_PROVIDER_a4f_NAME=a4f
> LLM_PROVIDER_a4f_BASE_URL=https://api.a4f.co
> ```
> 如果写成：
> ```env
> LLM_PROVIDERS=a4f
> LLM_PROVIDER_openai_NAME=a4f
> ```
> 那么 `a4f` 这个 provider 会被视为「缺少配置」而被跳过，最终 `/models` 可能返回空列表。

---

## 主要 API

网关对外暴露的主要端点包括：

### 基础网关接口

- `GET /health`：健康检查。
- `GET /models`：聚合后的模型列表（OpenAI 兼容格式，需要认证）。
- `POST /v1/chat/completions`：统一聊天补全端点（需要认证），支持：
  - OpenAI 风格请求；
  - Claude 风格请求；
  - Gemini 风格 `input` 自动转换；
  - 流式与非流式模式；
  - 多提供商智能路由与跨厂商故障转移。
- `POST /v1/responses`：OpenAI Responses API 兼容端点，自动将 `instructions`/`input` 映射到 `messages`，并复用上述路由/流式能力。
- `GET /context/{session_id}`：查询指定会话的历史上下文（需要认证）。

### 多提供商管理与路由接口

- `GET /providers`：查看所有已配置的提供商。
- `GET /providers/{provider_id}`：查看某个提供商的配置。
- `GET /providers/{provider_id}/models`：查看某个提供商的模型列表（从缓存或上游刷新）。
- `GET /providers/{provider_id}/health`：对单个提供商做轻量健康检查。
- `GET /providers/{provider_id}/metrics`：查看某个提供商的路由统计指标。
- `GET /logical-models`：列出所有逻辑模型。
- `GET /logical-models/{logical_model_id}`：查看单个逻辑模型。
- `GET /logical-models/{logical_model_id}/upstreams`：查看逻辑模型对应的物理上游列表。
- `POST /routing/decide`：对某个逻辑模型计算一次路由决策，返回选中的上游及候选得分。
- `GET /routing/sessions/{conversation_id}`：查看某个会话与提供商/模型的绑定关系。
- `DELETE /routing/sessions/{conversation_id}`：删除会话绑定（取消会话粘连）。

更多字段与数据结构说明见 `specs/001-model-routing/data-model.md`。

---

## 测试

项目使用 `pytest` 和 `pytest-asyncio` 进行测试。  
推荐本地执行：

```bash
pytest
```

或仅运行某个测试文件：

```bash
pytest tests/test_chat_greeting.py
```

---

## 贡献

欢迎通过 Issue 和 Pull Request 参与贡献。请在提交前：

- 为新增功能补充或更新测试；
- 本地运行 `pytest` 确认测试通过；
- 遵循现有的提交信息风格（中英文均可，如 `添加跨厂商故障转移` 或 `Add cross-provider failover`）。

---

## 许可证

本项目使用 MIT 许可证，详情参见 `LICENSE` 文件。
