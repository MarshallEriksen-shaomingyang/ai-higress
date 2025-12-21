<p align="center">
  <img src="docs/images/logo.svg" alt="AI-Higress 徽标" width="360" />
</p>

<div align="center">

[![Release](https://img.shields.io/github/v/release/MarshallEriksen-Neura/AI-Higress-Gateway?label=release&style=flat-square)](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/releases)
[![Build](https://img.shields.io/github/actions/workflow/status/MarshallEriksen-Neura/AI-Higress-Gateway/test.yml?branch=main&style=flat-square)](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/actions)
[![License](https://img.shields.io/github/license/MarshallEriksen-Neura/AI-Higress-Gateway?style=flat-square)](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/blob/main/LICENSE)
[![Stars](https://img.shields.io/github/stars/MarshallEriksen-Neura/AI-Higress-Gateway?style=flat-square)](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/stargazers)

</div>

<h1 align="center">AI-Higress-Gateway</h1>

<p align="center"><em>面向生产的 AI 网关：OpenAI 兼容 API、多厂商路由、前后端看板、缓存与故障切换。</em></p>

[English README](README.md#english-overview)

---

## 🌟 核心亮点
- 🔀 多提供商路由与权重调度，健康探测 + 故障切换。
- 🧭 OpenAI 兼容接口（`/v1/chat/completions`, `/v1/responses`, `/models`），内置请求/响应适配器。
- 🧠 会话粘滞：`X-Session-Id` + Redis 保存上下文、模型缓存。
- 💳 积分与计费：用户/Provider 维度的请求计量、额度与交易历史。
- 📊 指标与看板：Provider 排行、成功率趋势、请求历史、用户维度概览。
- 🛡️ 安全内置：鉴权、API Key 发行、角色/权限、中间件安全校验、限流。
- 🧰 研发友好：FastAPI 后端 + Next.js 管理台（App Router + Tailwind + shadcn/ui），docker-compose 一键本地栈。

<p align="center">
  <img src="docs/images/architecture.svg" alt="架构图" width="780" />
</p>

## 📸 截图

<p align="center">
  <img src="docs/images/overview.png" alt="仪表盘截图" width="820" />
</p>

<p align="center">
  <img src="docs/images/provider-overview.png" alt="Provider 管理截图" width="820" />
</p>

## 🧩 功能矩阵
- 网关与 API：OpenAI 兼容（Chat/Responses/Models）、SSE/非流、上下文存储。
- Provider：公共/私有 Provider 注册，预设模板，逻辑模型映射，权重路由，提交与审核流程。
- 路由与控制：路由规则、故障切换/回退、健康探测、缓存失效。
- 身份与访问：JWT 登录、API Key、角色/权限、用户资料与头像。
- 积分与计费：余额/消耗/交易历史，用户 & Provider 维度指标。
- 可观测性：用户/Provider 指标、成功率趋势、请求历史、会话审计片段。
- 运维与管理：系统配置、通知、Provider 审核、网关健康检查。

## 🚀 快速开始

### Docker 镜像（推荐新手）
1) 准备环境变量：
```bash
cp .env.example .env
# 按需修改 .env（尤其是数据库/Redis 密码、SECRET_KEY、OAuth 回调等）
```
2) 启动开发栈（后端镜像 + PostgreSQL + Redis，可选前端容器）：
```bash
IMAGE_TAG=latest docker compose -f docker-compose.develop.yml --env-file .env up -d
```
3) 访问：
- 后端 API: http://127.0.0.1:8000
- 前端管理台（启用 frontend 服务时）: http://127.0.0.1:3000

### 后端源码开发
1) 克隆仓库：
```bash
git clone https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway.git
cd AI-Higress-Gateway
```
2) Python 3.12 环境：
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e backend/
```
3) 启动 PostgreSQL + Redis（Docker）：
```bash
docker compose -f docker-compose.develop.yml --env-file .env up -d postgres redis
```
4) 运行网关（开发模式）：
```bash
cd backend
apiproxy  # 或 uvicorn main:app --reload
```

### 前端
```bash
cd frontend
bun install   # 或 pnpm / npm
bun dev       # 启动 Next.js 管理台
```
前端环境变量示例：`frontend/.env.example`（`NEXT_PUBLIC_API_BASE_URL` 指向后端）。

## ⚙️ 配置
- 核心配置在 `backend/app/settings.py`，推荐使用环境变量。
- 通过系统 API `POST /system/secret-key/generate` 生成 `SECRET_KEY` 写入 `.env`。
- Redis/PostgreSQL 连接信息从 `.env` 读取，可按需调整端口/密码。
- Celery 可复用 Redis 作为 broker/result（参考 `.env` 示例）。
- 常用环境变量：
  - `REDIS_URL`, `REDIS_PASSWORD`
  - `DATABASE_URL`（postgresql+psycopg）
  - `SECRET_KEY`
  - `LOG_LEVEL`（默认 INFO）
  - `AUTO_APPLY_DB_MIGRATIONS`（默认 true）+ `ENABLE_AUTO_MIGRATION=true`（显式开启实际迁移）
  - `ENABLE_CREDIT_CHECK`（启用网关层积分不足拦截）
  - `ENABLE_STREAMING_PRECHARGE`, `STREAMING_MIN_TOKENS`（流式请求预扣开关与估算参数）

## 🧪 测试
后端使用 `pytest` / `pytest-asyncio`（AI Agent 不代跑，请本地执行）：
```bash
cd backend
pytest
```

## 🐳 容器化
- 开发/本地试用（镜像模式）：  
  `IMAGE_TAG=latest docker compose -f docker-compose.develop.yml --env-file .env up -d`
- 生产部署（镜像模式）：  
  `IMAGE_TAG=latest docker compose -f docker-compose-deploy.yml --env-file .env up -d`

生产建议在 CI 先执行 `alembic upgrade head`，并结合外部 Redis、监控与日志。

## 📂 目录速览
- `backend/`：FastAPI 后端（入口 `main.py`，业务在 `app/`）。
- `frontend/`：Next.js 管理与监控 UI。
- `docs/`：设计与 API 文档（接口变更时同步更新 `docs/api/`）。
- `scripts/`：脚本工具（模型检查、批量任务、密钥生成示例等）。
- `tests/`：pytest 测试套件（含异步用例）。
- `docker-compose.develop.yml`：开发/本地试用编排（后端镜像 + PostgreSQL/Redis + 可选前端）。
- `docker-compose-deploy.yml`：生产部署编排（仅后端镜像 + PostgreSQL/Redis）。
- `docker-compose.images.yml`：纯镜像后端编排（不含前端，可用于快速试跑）。

## 📚 文档与规范
- API 文档：`docs/api/`
- 后端设计：`docs/backend/`
- 前端设计：`docs/fronted/`
- Bridge / MCP：`docs/bridge/design.md` + `specs/004-mcp-bridge/quickstart.md` + `docs/api/bridge.md`
- UI 规范：`ui-prompt.md`
- 前端文案与 i18n：`frontend/lib/i18n/`
- 设计/截图资源：`docs/images/`

## 🔌 Bridge（MCP）使用说明（快速上手）

Bridge 用于在浏览器无法直连本地 MCP 的前提下，通过“反向 WSS 隧道 + 本地 Agent”让 Web 侧安全调用用户机器/内网的 MCP 工具。

### 0) 一键安装 Bridge CLI（推荐）
macOS/Linux：
```bash
curl -fsSL https://raw.githubusercontent.com/MarshallEriksen-Neura/AI-Higress-Gateway/master/scripts/install-bridge.sh | bash
```
Windows（PowerShell）：
```powershell
irm https://raw.githubusercontent.com/MarshallEriksen-Neura/AI-Higress-Gateway/master/scripts/install-bridge.ps1 | iex
```

### 1) 启动云端 Tunnel Gateway（Go）
```bash
cd bridge
go run ./cmd/bridge gateway serve --listen :8088 --agent-token-secret "$SECRET_KEY"
```

### 2) 配置后端（FastAPI -> Gateway）
推荐在后端 `.env` 设置：
- `BRIDGE_GATEWAY_URL=http://127.0.0.1:8088`
- `BRIDGE_GATEWAY_INTERNAL_TOKEN`（可选；如果你设置了 Gateway 的 `--internal-token`，两边必须一致）
- `SECRET_KEY`（用于签发 Bridge Agent 的 AUTH token；与 Gateway 的 `--agent-token-secret` 保持一致）

### 3) 网页生成用户侧配置文件（不上传密钥）
在管理台打开 `/dashboard/bridge` → `配置` Tab：
- 点击“生成 Token”（写入 `server.token`）
- 下载 `config.yaml`

### 4) 用户机器/服务器运行 Agent
```bash
bridge agent start
```
配置文件发现顺序：
- 若显式传 `--config <file>`，优先使用该路径
- 否则从当前目录向上查找 `<仓库根>/.ai-bridge/config.yaml`（找到 `.git` 即停止）
- 再否则回退到 `~/.ai-bridge/config.yaml`

可选：将网页下载的配置写入默认路径：
```bash
bridge config apply --file ./config.yaml
bridge config validate
```

远程 MCP Server（可选）：`mcp_servers` 除了本地 `command`（stdio）外，也支持远程 `type: streamable|sse|auto` + `url` + 可选 `headers`。
然后回到 Chat 会话选择 `agent_id`，后端会自动拉取工具列表并注入模型（tool-calling）。

### 5) 其他 MCP 客户端（Claude Desktop/Cursor）直连（stdio）
如果你想让本地的 Claude Desktop/Cursor 直接用这个聚合后的 MCP 工具（不走云端隧道）：
```bash
bridge agent serve-mcp --config ~/.ai-bridge/config.yaml
```

### 6) 构建与发布（Windows/macOS/Linux）
- 本地打包：`make build-bridge-dist`（产物在 `dist/bridge/*`）
- 自动发布到 GitHub Release：推送 `bridge-v*` 标签（例如 `bridge-v0.1.0`，见 `.github/workflows/bridge-release.yml`）

## 🤝 贡献指南
- 遵循 PEP 8、类型注解；函数/变量 snake_case，类 PascalCase。
- 新增接口/缓存/上下文逻辑需补充测试。
- 涉及 API 行为、鉴权或错误码的改动必须同步更新 `docs/api/`。
- 提交信息保持简洁，如 `添加模型缓存错误处理`。

## 📜 许可证
MIT
