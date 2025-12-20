这是一份完整的技术架构设计文档，整合了我们之前讨论的所有核心决策：反向隧道架构、Go 语言实现、CLI 优先策略 以及 YAML 配置标准。

您可以直接将此文档用于项目归档、团队协作或作为开发开发的指导手册。

分布式 AI 网关与 MCP 本地伴侣 (AI Bridge) 架构设计文档
版本: v1.0 状态: 规划中 核心目标: 实现 Web 端 AI 聊天应用与用户本地（或内网）MCP 工具的安全、无缝连接。

1. 核心设计理念
本系统采用 "反向 WebSocket 隧道 (Reverse WebSocket Tunnel)" 架构，配合 "本地聚合器 (Local Aggregator)" 模式。

去中心化配置: 用户的敏感数据（API Key、数据库密码）仅存在于本地配置文件中，云端不保存。

网络穿透: 通过边缘端（Agent）主动外连云端的方式，穿透防火墙和 NAT，无需用户拥有公网 IP。

多端兼容: 核心组件使用 Go 编写，一次编译，覆盖 Windows, macOS, Linux (x86/ARM)。

CLI 优先: 优先交付命令行工具，后续通过 Wails/Fyne 封装 GUI。

2. 系统架构拓扑
代码段

graph TD
    subgraph "Public Cloud (云端)"
        WebUI[Web Browser / PWA]
        Gateway[Go AI Gateway (Host)]
        LLM[DeepSeek / OpenAI API]
    end

    subgraph "User Private Environment (本地/内网)"
        Bridge[AI Bridge (Go CLI)]
        Config[config.yaml]
        
        subgraph "Local MCP Servers"
            PyScript[Python FastMCP Script]
            DockerDB[Docker: Postgres]
            NodeApp[Node.js Service]
        end
    end

    %% 连接流向
    WebUI -->|1. WebSocket/HTTP| Gateway
    Gateway -->|2. Prompt + Tool Defs| LLM
    
    %% 关键隧道
    Bridge -->|3. Init WSS Tunnel| Gateway
    Gateway <==>|4. JSON-RPC Tunneling| Bridge
    
    %% 本地聚合
    Bridge -.->|Read| Config
    Bridge <==>|5. Stdio/SSE| PyScript
    Bridge <==>|6. Stdio| DockerDB
    Bridge <==>|7. Stdio| NodeApp
3. 核心组件定义
3.1 云端网关 (Cloud Gateway)
职责: * 作为 WebSocket Server 监听 /tunnel 端点。

维护 User_ID -> WebSocket_Connection 的路由表。

将 LLM 的工具调用请求（Tool Call）路由给对应的用户连接。

特性: 无状态（Stateless），只负责转发，不执行具体工具逻辑。

3.2 边缘伴侣 (AI Bridge / Agent)
职责:

聚合器 (Aggregator): 启动并管理多个本地 MCP 子进程（Python, Node, Docker 等）。

路由器 (Router): 接收云端指令，根据工具名称前缀（如 fs_readFile）分发给对应的子进程。

保活 (Keep-Alive): 维护与云端的长连接，处理断线重连。

形态: 单个二进制文件 (CLI)，支持通过 YAML 配置。

4. 通信协议 (Tunnel Protocol)
在 WebSocket 之上定义轻量级信封协议，用于区分控制消息和业务消息。

消息结构 (JSON):

JSON

{
  "type": "MCP_REQUEST",  // 类型: AUTH, PING, MCP_REQUEST, MCP_RESPONSE, ERROR
  "id": "req_xyz123",     // 请求ID，用于异步匹配响应
  "payload": { ... }      // 具体的 MCP JSON-RPC 内容
}
交互流程:

Auth: Bridge 连接成功后，立即发送 {"type": "AUTH", "token": "sk-..."}。

Tool List: 认证通过后，Bridge 将本地聚合后的工具列表（Tools Definition）发送给 Cloud。

Call: 当 LLM 需要调用工具时，Cloud 发送 MCP_REQUEST。

Exec: Bridge 执行本地逻辑，返回 MCP_RESPONSE。

5. 本地配置规范 (YAML)
使用 YAML 作为标准配置文件，路径默认为 ~/.ai-bridge/config.yaml。

YAML

version: "1.0"

# 连接云端的凭证
server:
  url: "wss://api.your-ai-chat.com/v1/tunnel"
  token: "sk-user-specific-token"
  reconnect_interval: 5s

# 本地 MCP 服务聚合配置
mcp_servers:
  # 1. 简单的 Python 脚本 (使用 FastMCP)
  - name: "calculator"
    command: "python3"
    args: ["/Users/me/scripts/math_tools.py"]
    
  # 2. 运行 Docker 容器 (如数据库操作)
  - name: "my_db"
    command: "docker"
    args: 
      - "run"
      - "-i"
      - "--rm"
      - "-e" 
      - "POSTGRES_PASSWORD=secret"
      - "mcp/postgres"

  # 3. 环境变量注入
  - name: "git_bot"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "ghp_xxxxxxxxxxxx"
6. 项目代码结构 (Go Clean Architecture)
Plaintext

ai-bridge/
├── cmd/
│   ├── cli/            # CLI 入口 (Cobra)
│   │   └── main.go
│   └── gui/            # GUI 入口 (未来预留 Wails)
│       └── main.go
├── internal/
│   ├── config/         # Viper 配置加载与结构定义
│   ├── tunnel/         # WebSocket 客户端、心跳、重连逻辑
│   ├── mcp/            # MCP 进程管理、聚合逻辑、JSON-RPC 处理
│   └── app/            # 核心 Service，组装 Tunnel 和 MCP
├── pkg/                # 可被外部引用的通用库 (Logger 等)
├── go.mod
└── config.yaml.example
7. 开发路线图 (Roadmap)
第一阶段：核心连通 (MVP)
[ ] 目标: 实现 Echo 功能。

[ ] 任务:

搭建 Cloud WebSocket Server (Go)。

开发 Bridge CLI 基础框架 (Cobra)。

实现 Bridge -> Cloud 的连接、鉴权、心跳、断线重连。

验证：Cloud 发送字符串，Bridge 接收并打印，原样返回。

第二阶段：MCP 聚合与执行
[ ] 目标: 跑通“浏览器控制本地 Python 脚本”。

[ ] 任务:

引入 mark3labs/mcp-go SDK。

Bridge 实现 mcp_servers 配置解析。

Bridge 实现子进程启动 (os/exec) 和 Stdio 管道接管。

实现工具列表合并逻辑（为工具名添加 name 前缀）。

实现路由逻辑：收到请求 -> 解析前缀 -> 转发给对应子进程。

第三阶段：Web 端集成
[ ] 目标: 完整闭环。

[ ] 任务:

Web 前端检测到 WebSocket 连接后，更新 UI 显示“本地服务已连接”。

将 Bridge 上报的工具列表注入到 LLM 的 Context 中。

处理 LLM 返回的 Tool Call，封装成 Tunnel 消息发给 Bridge。

第四阶段：用户体验优化 (可选项)
[ ] 封装 GUI 版本 (Wails)。

[ ] 增加安装脚本 (Shell/PowerShell)。

[ ] 支持 Windows 系统托盘运行。

8. 安全与风控清单
Token 强校验: Cloud 必须严格验证 Bridge 传入的 Token，防止恶意用户接入他人会话。

指令白名单 (建议): 在 Bridge 端增加确认机制。对于高危操作（如 rm 或 drop table），Bridge 可以在日志中告警，甚至在未来 GUI 版本中弹窗要求用户“点击确认”。

TLS 传输: 生产环境必须强制使用 wss://，禁止明文 ws://。