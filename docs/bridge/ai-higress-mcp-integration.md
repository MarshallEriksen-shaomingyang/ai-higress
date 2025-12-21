AI-Higress-Gateway 接入 MCP（Bridge）设计说明
========================================

本文档描述“本项目（AI-Higress-Gateway）如何接入 MCP 能力”的落地设计，基于 `docs/bridge/design.md` 的通用架构方案，强调与本仓库现有技术栈（FastAPI + Next.js）之间的边界与集成点。

配置安全说明（方案 A，当前确定）:
- Web 配置向导在浏览器内生成 `config.yaml` 并下载；敏感信息不上传、不经过云端。
- 用户需手动导入/放置该配置文件以让 Agent 生效。
- 未来如需要“一键远程下发配置”，可再评估端到端加密（E2EE）方案，但不作为当前 MVP 范围。
目标与边界
----------

目标:
- 让 Web 端在浏览器沙箱限制下仍可调用用户本地/内网 MCP 工具（包含长耗时任务的流式日志回显）。
- 支持 1 个用户同时连接多台 Agent（`agent_id` 精准路由）。
- 支持“方案 A”：网页生成 `config.yaml`，用户下载并本地导入；后端不触碰用户密钥明文。

边界:
- Web 前端只展示与交互，不直连 Agent，不运行 MCP。
- FastAPI 后端负责鉴权/计费/会话/审计与 LLM 编排（agent loop），并向前端输出 SSE。
- Go Bridge（Agent + Tunnel Gateway）负责连接层与 MCP 聚合/执行，未来可拆为独立仓库。

组件映射（到本仓库）
-------------------

- `frontend/`:
  - 配置向导：在浏览器内生成 `config.yaml` 并下载（方案 A）。
  - Chat UI：展示 LLM 回复；展示工具执行日志流（stdout/stderr）与最终结果；支持取消。
- `backend/`（FastAPI）:
  - Chat 编排层：接收用户消息，调用 LLM；当出现 tool_calls 时向指定 `agent_id` 下发执行并回填 tool result。
  - SSE 输出：将“工具执行日志/状态/终态结果”以 SSE 事件推送给前端。
- `bridge/`（Go，已落地 MVP）:
  - `cmd/bridge`：单入口 CLI（`bridge config|agent|gateway`）。
  - `bridge agent start`：Bridge Agent（运行在用户机器/服务器）连接云端并执行 MCP（已支持配置多 MCP 子 server；同时保留内置 `bridge__echo` 用于端到端验证）。
  - `bridge gateway serve`：Tunnel Gateway（云端连接层）维护 Agent WSS 连接与路由（默认单实例无 Redis；可选启用云端 Redis 做 HA/持久化）。

数据流（端到端）
--------------

1) 配置与启动（方案 A，不触碰密钥）
- 用户在 Web 配置页填写 MCP server 配置（包含 token/env）。
- 浏览器生成并下载 `config.yaml`（敏感信息仅存在浏览器内存与下载文件中）。
- 一键安装 Bridge CLI（推荐）：
  - macOS/Linux：`curl -fsSL https://raw.githubusercontent.com/MarshallEriksen-Neura/AI-Higress-Gateway/master/scripts/install-bridge.sh | bash`
  - Windows（PowerShell）：`irm https://raw.githubusercontent.com/MarshallEriksen-Neura/AI-Higress-Gateway/master/scripts/install-bridge.ps1 | iex`
- 用户运行（示例）:
  - 可选：写入默认路径并校验：`bridge config apply --file ./config.yaml` / `bridge config validate`
  - 或放在仓库根目录：`<repo>/.ai-bridge/config.yaml`（`bridge` 会从当前目录向上查找，直到 `.git`）
  - 启动：`bridge agent start`
- Agent 与云端 Tunnel Gateway 建立 WSS 连接并注册 `agent_id`，上报工具列表（TOOLS）。

2) 聊天调用工具（流式）
- 前端发送聊天请求到后端（建议携带 `agent_id`，用于精准路由）。
- 后端调用 LLM；当 LLM 返回 tool_calls：
  - 后端根据 `agent_id` 向 Tunnel Gateway 下发 `INVOKE(req_id, tool_name, args, stream=true)`。
- Agent 执行 MCP `tools/call`：
  - 执行过程 stdout/stderr 实时上报为 `CHUNK(req_id, channel, data)`；
  - 执行结束上报 `RESULT(req_id, ok, exit_code, result_json, error?)`，并等待 `RESULT_ACK`。
- 后端将 CHUNK/RESULT 映射为 SSE 推给前端，并将 `result_json` 回填给 LLM 继续生成最终回复。

3) 取消（Cancel）
- 前端点击“停止”后端发起取消请求（针对 `req_id`）。
- 后端向 Tunnel Gateway 下发 `CANCEL(req_id)`；Agent 尽力取消并最终以 `RESULT` 终态收敛。

关于 Redis：用户侧不需要安装
--------------------------

用户安装与运行 Bridge Agent 不需要 Redis。Redis（或替代消息系统）仅在云端用于“多实例路由/投递解耦/可靠队列”。

当前实现状态（本仓库）:
- 已实现“单实例无 Redis MVP”：Tunnel Gateway 内存连接表 + 内网 HTTP 下发 + SSE events 回传。
- 已实现“可选云端 Redis 模式”（Redis 只部署在云端，不影响用户侧安装即用）：
  - Registry：`agent_online:{agent_id}`（TTL 续租）
  - Commands：消费 `bridge:cmd:{gateway_id}` Streams（用于跨实例下发）
  - Events：Pub/Sub（`bridge:evt` / `bridge:evt:agent:{agent_id}`）
  - Results：KV 持久化（`bridge:result:{req_id}` + TTL），并以“写入成功”为准发送 `RESULT_ACK`
  - 通过 `bridge gateway serve --redis-url <redis_url>` 启用

MVP（推荐先做，零额外依赖）:
- Tunnel Gateway 单实例部署（内存连接表）。
- 后端通过内网 HTTP/gRPC 直接请求 Tunnel Gateway 下发 INVOKE/CANCEL。
- RESULT 强可靠依赖 `RESULT_ACK` + Agent 端缓存重传（断线重连后补发未确认 RESULT）。

扩展（K8s 多副本/HA）:
- 引入 Redis（Registry + Streams/PubSub）或 NATS/Kafka 以支持跨实例投递与回传解耦。
- 该依赖属于“云端部署复杂度”，不影响用户侧使用体验。

接口与事件（建议约定）
--------------------

前端 -> 后端:
- 聊天请求需携带 `agent_id`（可作为 header 或字段；MVP 选最少改动的方式）。
- 取消请求需携带 `req_id`。

后端 -> 前端（SSE 事件建议）:
- `tool_status`: {req_id, state: "sent"|"acked"|"running"|"canceled"|"done"|"error"}
- `tool_log`: {req_id, channel: "stdout"|"stderr", data, dropped_bytes?, dropped_lines?}
- `tool_result`: {req_id, ok, exit_code, result_json, error?, canceled?}

Tunnel Gateway / Agent（WS 协议）:
- 以 `docs/bridge/design.md` 中的 `HELLO/AUTH/TOOLS/INVOKE/INVOKE_ACK/CHUNK/RESULT/RESULT_ACK/CANCEL/CANCEL_ACK` 为准。

安全落地要点（本项目特有）
------------------------

- 方案 A 下，后端不接触用户密钥明文：配置在浏览器生成并下载，由用户本地导入。
- Agent/CLI 日志必须避免输出敏感字段（token/password），默认写 stderr。
- 默认不提供“任意 shell/任意命令”类工具；通过 MCP server 列表与 allowlist 控制能力边界。

阶段性交付建议
--------------

阶段 1（可用最小闭环）:
- 单实例 Tunnel Gateway + Agent 连接与工具上报
- 后端完成 agent loop 的“单个工具调用 + CHUNK + RESULT”
- 前端展示日志流与最终结果 + 取消按钮

阶段 2（多 Agent 与更好体验）:
- 会话绑定默认 `agent_id`，支持切换
- 工具列表缓存与分页展示（仅展示，不泄露敏感配置）

阶段 3（云端高可用）:
- 增加 Redis/NATS 等消息层，实现多实例路由与可靠队列
