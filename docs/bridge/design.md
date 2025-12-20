分布式 AI 网关与 MCP 伴侣（AI Bridge）架构设计文档
版本: v1.1
状态: 规划中

核心目标
- 在浏览器无法运行/直连用户本地 MCP 的前提下，通过“反向隧道 + 本地 Agent”让 Web 端安全调用用户本地/内网 MCP 工具。
- 必须支持流式回显（stdout/stderr 实时输出），并支持 1 用户同时连接多台 Agent（1-to-Many），按 `agent_id` 精准路由。

重要边界（本仓库落地约束）
- Web 前端只负责展示与交互：不直连 Agent，不直接接入 MCP。
- 现有后端（FastAPI）继续负责鉴权/计费/会话/审计与 LLM 编排（agent loop），并以 SSE 向前端推送事件。
- MCP/隧道能力使用 Go：包含“隧道连接层（Tunnel Gateway）”与“本地/服务器 Agent（Bridge Agent）”，逻辑上应可拆为独立项目；短期可同仓维护。

---

## 1. 核心设计理念
- 反向外连: Agent 主动向云端发起 WSS（出站连接），解决防火墙/NAT/无公网 IP。
- 去中心化配置: 用户敏感信息仅存在本地配置文件/环境变量中，云端不保存明文。
- 分层解耦:
  - Tunnel Gateway 负责“连接与转发”（有状态：持有 WS 长连接）。
  - Backend Orchestrator 负责“业务编排”（可保持业务无状态并水平扩展）。
- 可靠性分层:
  - 日志流（CHUNK）尽力而为：允许丢失，但必须可观测（上报丢弃计数）。
  - 终态结果（RESULT）强可靠：至少一次投递 + 云端幂等去重，保证不会因断线丢失终态。

### 1.1 技术选型（Go，确定版）
命令行框架:
- Cobra（`github.com/spf13/cobra`）：支持子命令（如 `agent start` / `agent status` / `gateway serve`）。

配置管理:
- Viper（`github.com/spf13/viper`）：配合 Cobra，统一处理“配置文件 vs 环境变量 vs 命令行参数”的优先级。
- 推荐优先级: CLI flags > ENV > config file > defaults。
- ENV 前缀建议: `AI_BRIDGE_`（例如 `AI_BRIDGE_SERVER_TOKEN`）。

MCP SDK:
- 首选（官方，固定）：`github.com/modelcontextprotocol/go-sdk`
  - 使用其 `mcp` 包实现 MCP client/server 与 session 管理。
  - 传输（Transport）优先级建议:
    1) 本地子进程: `StdioTransport` / `CommandTransport`（最稳定、最通用）
    2) 远程服务: SDK 提供的 HTTP/SSE/Streamable 相关实现（以实际接入的 MCP server transport 为准）
- 备选（社区成熟）：`github.com/mark3labs/mcp-go`
  - 仅在官方 SDK 无法覆盖特定 transport/特性时启用（避免长期双栈维护）。

自定义逻辑边界（仍需自研，但不重复造轮子）:
- 聚合: 多 MCP server 并发初始化与 tools/list 汇总
- 命名空间: 工具名前缀 `{server}__{tool}`（避免冲突，满足上游 name 字符集限制）
- 路由: `tools/call` 按前缀转发到对应子 server
- 流式日志: stdout/stderr -> CHUNK，上报 dropped 计数
- 可靠终态: RESULT 缓存/重传，直到收到 RESULT_ACK

日志:
- 默认使用 Go 1.21+ 内置 `log/slog`（结构化日志），生产可选切换 Zap（`go.uber.org/zap`）。
- 关键要求: 日志不直接写入 stdout（stdout 预留给业务输出/管道/协议数据）；CLI 默认将日志写入 stderr。
- 设计要求: 定义一个 Logger 抽象/接口或统一封装层：
  - CLI 通过 `slog.TextHandler`/`JSONHandler` 输出到 stderr；
  - GUI（未来）通过自定义 handler/adapter 将日志事件发送到前端组件（而不是直接 `fmt.Println`）。

其他依赖（建议）:
- WebSocket: `nhooyr.io/websocket` 或 `github.com/gorilla/websocket`
- Redis（可选，仅云端 HA/多实例时需要）: `github.com/redis/go-redis/v9`

---

## 2. 系统架构拓扑
说明: Browser 永远不直接连接 Agent；所有远程执行都通过云端控制平面路由。

```mermaid
graph TD
  subgraph "Public Cloud (云端)"
    WebUI[Web Browser / PWA]
    Backend[Backend Orchestrator (FastAPI)\nAuth/Billing/LLM Loop/SSE]
    Tunnel[Tunnel Gateway (Go)\nWSS/Conn Map/Heartbeat]
    Redis[(Redis (Optional)\nRegistry + Streams + PubSub)]
    LLM[LLM Providers\n(OpenAI/Claude/DeepSeek...)]
  end

  subgraph "User Private Environment (本地/内网)"
    Agent[Bridge Agent (Go CLI)]
    Config[config.yaml]
    subgraph "Local MCP Servers"
      PyScript[Python MCP Server (stdio/SSE)]
      DockerDB[Docker MCP (stdio)]
      NodeApp[Node.js MCP Server (stdio)]
    end
  end

  WebUI -->|HTTPS| Backend
  Backend -->|SSE text/event-stream| WebUI
  Backend -->|HTTP/SSE| LLM

  Backend <--> |Redis (Optional)| Redis
  Tunnel <--> |Redis (Optional)| Redis

  Agent -->|WSS Outbound| Tunnel
  Agent -.->|Read| Config
  Agent <--> |stdio/SSE| PyScript
  Agent <--> |stdio| DockerDB
  Agent <--> |stdio| NodeApp
```

---

## 3. 核心组件职责

### 3.1 Backend Orchestrator（FastAPI）
职责:
- 接收 Web 请求，完成鉴权/计费/会话/审计。
- 执行 LLM 编排（agent loop）：
  - 将工具定义注入 LLM；
  - 解析 LLM 的 tool_calls；
  - 向指定 `agent_id` 下发 INVOKE；
  - 接收工具流式日志与 RESULT，将工具结果回填给 LLM，直至生成最终回复。
- 将 Agent 侧事件映射为 SSE 事件推送前端（`tool_log` / `tool_result` / `tool_status` 等）。

### 3.2 Tunnel Gateway（Go，连接层）
职责:
- 作为 WebSocket Server 接入 Agent（示例端点: `/bridge/tunnel`），维护进程内连接表 `map[agent_id]*Conn`。
- 心跳保活与断线检测（ws ping/pong + 应用层 PING/PONG）。
- 多实例路由:
  - 将 `agent_id -> gateway_instance_id/conn_session_id` 写入 Redis Registry（TTL 续租）；
  - 从 Redis 接收后端下发指令并路由至本地 WS 连接；
  - 将 Agent 上行事件写入 Redis（CHUNK 尽力、RESULT 强可靠）。

重要说明:
- Tunnel Gateway **不是无状态服务**（长连接即本地状态）。K8s 多副本下必须依赖 Registry + 消息投递实现跨实例路由。

### 3.3 Bridge Agent（Go，运行在用户机器/服务器）
职责:
- MCP 聚合器: 启动/管理多个 MCP 子进程（stdio/SSE），汇总工具列表并命名空间化。
- 路由器: 收到 INVOKE 后，根据工具名前缀路由到具体 MCP 子进程。
- 流式回显: 实时采集子进程 stdout/stderr，转换为 CHUNK 上行。
- 背压控制: 网络慢时使用有界队列，避免阻塞工具进程；上报丢弃计数。
- 可靠终态: RESULT 缓存直至收到 RESULT_ACK；断线重连后可补发未确认 RESULT。
- 断线重连: 指数退避 + 抖动（避免大面积同时重连打爆服务端）。

---

## 4. 隧道协议（WS 信封协议）

### 4.1 信封格式（JSON）
```json
{
  "v": 1,
  "type": "INVOKE",
  "agent_id": "aws-dev-server",
  "req_id": "req_7f0f7b1d6b5b4f4dbf...",
  "conn_session_id": "ws_2c7b...",
  "seq": 123,
  "ts": 1712345678,
  "payload": {}
}
```

字段语义:
- `agent_id`: 路由目标（1 用户多 Agent 的核心键）。
- `req_id`: 一次工具调用的全局幂等键（必须唯一）；用于去重、取消、结果确认。
- `conn_session_id`: 单次 WS 连接会话 id（重连会变化），用于诊断/安全绑定（可选）。
- `seq`: 连接内递增序号（用于观测与排错，不作为可靠传输前提）。

### 4.2 消息类型（v1 最小集合）
- `HELLO`（Agent -> Gateway）: 版本、agent 元信息、可选恢复信息（如未 ack 的 req_id 摘要）。
- `AUTH`（Agent -> Gateway）: token + 设备指纹（可选）。
- `PING` / `PONG`（双向）: 应用层心跳（同时建议启用 ws ping/pong）。
- `TOOLS`（Agent -> Gateway）: 上报聚合后的工具列表（用于后端注入 LLM）。
- `INVOKE`（Gateway -> Agent）: 下发工具调用（含超时、是否流式、可选回程地址）。
- `INVOKE_ACK`（Agent -> Gateway）: 快速确认“已接收/拒绝”（拒绝原因如工具不存在/权限禁止）。
- `CHUNK`（Agent -> Gateway）: 日志分片（stdout/stderr），允许丢弃并上报 `dropped_bytes/lines`。
- `RESULT`（Agent -> Gateway）: 终态结果（结构化 JSON、退出码、错误信息、是否 canceled）。
- `RESULT_ACK`（Gateway -> Agent）: 确认终态已被云端持久化/接收，Agent 可释放缓存。
- `CANCEL`（Gateway -> Agent）: 请求取消某 `req_id`。
- `CANCEL_ACK`（Agent -> Gateway）: 确认“将尝试取消/无法取消”（如已完成）。

### 4.3 流式时序（典型）
- `INVOKE(req_id)` ->
- `INVOKE_ACK(req_id)` ->
- `CHUNK(req_id)` * N ->
- `RESULT(req_id)` ->
- `RESULT_ACK(req_id)`

可靠性约束（必须满足业务诉求）:
- CHUNK: 尽力而为（可丢），但要可观测（`dropped_*`）。
- RESULT: 强可靠（不可丢）。Agent 必须缓存未 ACK 的 RESULT，重连后可补发。

### 4.4 背压（Backpressure）策略（MVP 推荐）
- Agent 将 stdout/stderr 转 CHUNK 的发送路径使用“有界缓冲队列”（按 bytes 上限，如 2–8MB）。
- 队列满时丢弃并累计计数（`dropped_bytes/lines`），后续 CHUNK 中持续上报。
- CHUNK 分片建议 4–16KB，避免单帧过大导致 WS 缓冲/内存抖动。
- 不允许因为网络慢而阻塞工具进程 IO（否则会影响真实执行时长与交互体验）。

### 4.5 取消（Cancel）竞争态规则
- CANCEL 是“请求取消”，不保证成功；最终以 Agent 首次发出的 RESULT 为准（云端以 `req_id` 幂等去重）。
- 用户点停止时若 Agent 已完成并发出 RESULT：Agent 返回 `CANCEL_ACK(will_cancel=false, reason="already_finished")`；云端 UI 显示“已完成/无法取消”。

---

## 5. 多实例路由与 Redis 设计（建议）

> 重要：Redis 不属于“用户安装依赖”。用户侧只需要安装并运行 Agent 二进制即可。
>
> MVP（推荐先做）可以采用 **Tunnel Gateway 单实例** 部署，不引入 Redis：
> - Tunnel Gateway 内存维护连接表；
> - 后端通过内网 HTTP/gRPC 直接下发 INVOKE/CANCEL；
> - RESULT 强可靠依赖 `RESULT_ACK` + Agent 端缓存/重传。
>
> 当进入 K8s 多副本/HA 后，再引入 Redis（或 NATS/Kafka 等）实现跨实例路由与可靠队列。

当前实现状态（本仓库）:
- 已实现“单实例无 Redis MVP”（内存连接表 + 内网 HTTP 下发 + SSE events 回传）。
- 云端 Redis（Registry/Streams/PubSub）接入属于后续扩展阶段；Redis 仅部署在云端，不要求用户本地安装。

### 5.1 Registry（在线注册）
- Key: `agent_online:{agent_id}`
- Value（示例）: `{ "gateway_id": "gw-pod-3", "conn_session_id": "ws_...", "user_id": "...", "updated_at": 1712345678 }`
- TTL: 30s（由心跳续租；过期视为离线，避免僵尸路由）

### 5.2 指令下发（INVOKE/CANCEL）
为避免 Pub/Sub 丢消息，建议使用 Redis Streams 做“至少一次投递”:
- Stream: `bridge:cmd:{gateway_id}`（后端先查 registry 得到 gateway_id）
- 消费者: 对应 gateway 实例（consumer group）
- 消息体包含: `req_id/agent_id/type(INVOKE|CANCEL)/payload/reply_to`

### 5.3 事件回传（CHUNK/RESULT）
- CHUNK（尽力）: Pub/Sub
  - Channel: `bridge:evt:{reply_to}`（reply_to 由后端发起调用时生成，指向当前 API 实例/请求）
- RESULT（强可靠）: KV 或 Streams（任选其一）
  - KV: `bridge:result:{req_id}`（TTL 24h）+ 可选 Pub/Sub 通知
  - 或 Streams: `bridge:results`（append-only，便于审计/重放）

备注:
- 这个“reply_to”机制用于解决“Agent 连接在某个 gateway 实例，但发起 SSE 的后端实例可能不同”的跨实例回传问题。

---

## 6. 本地配置规范（YAML）
默认路径: `~/.ai-bridge/config.yaml`

### 6.1 Web 配置接入（方案 A：下载文件，零后端触碰敏感信息）
目标: 在不让后端接触用户密钥（Notion/GitHub/DB 密码等）的前提下，提供“网页引导配置”的接入体验。

流程:
1. 用户在网页配置向导中填写 MCP servers、路径、环境变量等配置项。
2. 网页端在浏览器内生成 `config.yaml`（包含敏感信息的仅在前端内存中出现）。
3. 用户下载 `config.yaml` 到本地。
4. 用户将文件放置到默认路径 `~/.ai-bridge/config.yaml`，或通过 CLI 导入并写入到默认路径。
5. 用户重启 Agent（或触发 reload）使配置生效。

CLI 约定（示例）:
- 写入默认路径: `bridge config apply --file ./config.yaml`
- 验证配置（仅读取/不启动）: `bridge config validate --file ./config.yaml`
- 查看当前生效配置路径: `bridge config path`

安全注意事项:
- `config.yaml` 可能包含敏感信息，建议用户将文件权限设置为仅自己可读（例如 `chmod 600 ~/.ai-bridge/config.yaml`）。
- CLI/Agent 日志必须避免打印敏感字段（token/password 等），仅输出“字段存在/长度/已脱敏”级别信息。

```yaml
version: "1.0"

server:
  url: "wss://api.your-ai-chat.com/bridge/tunnel"
  token: "sk-user-or-device-token"
  reconnect_initial: 1s
  reconnect_max: 60s

agent:
  id: "aws-dev-server"
  label: "AWS Dev Server"

mcp_servers:
  - name: "calculator"
    command: "python3"
    args: ["/Users/me/scripts/math_tools.py"]

  - name: "my_db"
    command: "docker"
    args:
      - "run"
      - "-i"
      - "--rm"
      - "-e"
      - "POSTGRES_PASSWORD=secret"
      - "mcp/postgres"

  - name: "git_bot"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "ghp_xxxxxxxxxxxx"
```

命名空间建议:
- 对每个 MCP server 的工具名增加前缀：`{server_name}__{tool_name}`（避免冲突；尽量使用上游普遍支持的字符集，如字母/数字/下划线）

---

## 7. 同仓（暂时）代码结构建议
说明: MCP/隧道作为“可拆分项目”暂时放在本仓库，建议使用独立 Go module，未来拆仓成本低。

```text
bridge/                    # (Go) MCP/隧道相关，未来可独立仓库
├── cmd/
│   ├── agent/             # Bridge Agent（二进制分发给用户）
│   └── tunnel-gateway/    # 云端 Tunnel Gateway（WSS 终止层）
├── internal/
│   ├── config/            # YAML 配置加载
│   ├── protocol/          # 信封协议/编解码
│   ├── mcp/               # MCP 子进程管理、stdio/SSE 转发
│   ├── backpressure/      # 有界队列、丢弃计数
│   └── reliable/          # RESULT 缓存与重传（待 ACK）
└── go.mod
backend/                   # 现有 FastAPI（编排/鉴权/计费/SSE）
frontend/                  # 现有 Next.js（展示/交互）
```

---

## 8. 开发路线图（Roadmap）

第一阶段：核心连通（Echo + 在线注册）
- Tunnel Gateway（Go）WSS Server + AUTH/HELLO/PING/PONG
- Agent（Go）连接、重连、Registry 续租（TTL）
- 验证：下发 INVOKE(ECHO) -> CHUNK/RESULT 回传

第二阶段：MCP 聚合与流式执行
- Agent 子进程管理（stdio/SSE）
- 工具列表聚合并上报 TOOLS
- CHUNK 背压（有界队列 + 丢弃计数）
- RESULT 强可靠（缓存 + RESULT_ACK + 重连补发）
- CANCEL 支持（尽力取消）

第三阶段：后端编排闭环（LLM tool_calls）
- 后端获取工具列表并注入 LLM
- 实现 agent loop：tool_calls -> INVOKE -> tool_result -> 继续生成
- 前端 SSE 展示：tool_log / tool_result / tool_status
- 多 Agent 选择：会话绑定默认 agent_id + 可切换

---

## 9. 安全与风控清单
- Token 强校验: 建议短期 token + 可吊销/轮换；可选绑定 `user_id + agent_id + 设备指纹`。
- 最小权限: 默认只开放安全工具；禁止默认提供“任意 shell/任意命令”能力。
- 参数校验: Agent 端对工具与入参做 allowlist/校验，避免云端指令越权。
- 高危确认: 提供本地确认模式（MVP 可用 CLI `--require-confirm`）。
- 输出控制: 对工具输出是否允许回传 LLM/前端要有策略（默认最小化、可配置脱敏/截断）。
- 审计: 记录谁在何时对哪个 agent 调用了哪个工具（参数摘要、耗时、状态、错误码/退出码）。
- 传输安全: 生产环境强制 `wss://`，禁止明文 `ws://`。
