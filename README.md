# APIProxy - AI Gateway

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

APIProxy 是一个基于 FastAPI 构建的高性能 AI 代理网关。它为上游 AI 服务提供了一个统一、兼容 OpenAI 标准的接口，并内置了模型缓存、会话管理和格式转换等功能，旨在简化客户端集成、提升性能和稳定性。

---

## ✨ 功能特性

- **🚀 OpenAI 兼容接口**: 提供标准的 `/v1/chat/completions` 和 `/models` 端点，无缝对接现有生态。
- **🔄 格式自动转换**: 智能检测并转换不同厂商的 API 请求格式（例如，将 Gemini 风格的输入自动转为 OpenAI 的 `messages` 格式）。
- **⚡️ 模型列表缓存**: 将上游模型列表缓存在 Redis 中，减少不必要的 API 请求，加快响应速度。
- **🗣️ 会话上下文管理**: 通过 `X-Session-Id` 请求头，自动记录和管理对话历史。
- **🔌 流式 & 非流式支持**: 自动检测客户端需求，同时支持流式（SSE）和非流式响应。
- **🛠️ 灵活配置**: 所有关键参数（如上游地址、API 密钥、Redis 地址等）均可通过环境变量配置。
- **🐳 Docker 一键部署**: 提供 `docker-compose.yml`，一键启动网关服务和所需的 Redis 数据库。
- **📝 请求日志**: 内置中间件，详细记录请求和响应信息，便于调试和监控。

## 🛠️ 技术栈

- **后端框架**: [FastAPI](https://fastapi.tiangolo.com/)
- **ASGI 服务器**: [Uvicorn](https://www.uvicorn.org/)
- **HTTP 客户端**: [HTTPX](https://www.python-httpx.org/)
- **数据缓存/会话存储**: [Redis](https://redis.io/)
- **配置管理**: [Pydantic Settings](https://docs.pydantic.dev/latest/usage/settings/)
- **依赖管理**: [uv](https://github.com/astral-sh/uv) / pip

## 🚀 快速开始

我们强烈推荐使用 Docker 进行部署，因为它提供了最简单、最一致的运行环境。

### 先决条件

- [Docker](https://www.docker.com/products/docker-desktop/) 和 [Docker Compose](https://docs.docker.com/compose/install/)
- Git

### 1. Docker 部署 (推荐)

1.  **克隆项目仓库**
    ```bash
    git clone <your-repository-url>
    cd APIProxy
    ```

2.  **创建并配置 `.env` 文件**
    从模板文件复制一份配置，并填入你的上游 API 信息。
    ```bash
    cp .env.example .env
    ```
    编辑 `.env` 文件:
    ```dotenv
    A4F_BASE_URL=REDACTED_API_URL  # 你的上游 API 地址
    A4F_API_KEY=your_upstream_api_key   # 你的上游 API 密钥
    REDIS_URL=redis://redis:6379/0      # Docker 环境下的 Redis 地址，通常无需修改
    ```

3.  **启动服务**
    使用 Docker Compose 在后台启动所有服务：
    ```bash
    docker-compose up -d
    ```
    服务将在 `http://localhost:8000` 上可用。

4.  **查看日志 (可选)**
    ```bash
    docker-compose logs -f api
    ```

5.  **停止服务**
    ```bash
    docker-compose down
    ```

### 2. 本地开发环境

1.  **克隆项目并安装依赖**
    确保你已安装 Python 3.12+。
    ```bash
    git clone <your-repository-url>
    cd APIProxy
    python -m venv .venv
    source .venv/bin/activate
    pip install .
    ```

2.  **配置 `.env` 文件**
    与 Docker 步骤类似，创建 `.env` 文件，但需要将 `REDIS_URL` 指向本地运行的 Redis 实例。
    ```bash
    cp .env.example .env
    ```
    编辑 `.env` 文件:
    ```dotenv
    A4F_BASE_URL=REDACTED_API_URL
    A4F_API_KEY=your_upstream_api_key
    REDIS_URL=redis://localhost:6379/0 # 指向本地 Redis
    ```
    确保你已经在本地启动了 Redis 服务。

3.  **启动服务**
    项目已配置好脚本，可以直接运行：
    ```bash
    apiproxy
    ```
    或者使用 Uvicorn (支持热重载):
    ```bash
    uvicorn main:app --reload
    ```
    服务将在 `http://localhost:8000` 上可用。

## ⚙️ 配置

应用通过环境变量进行配置，启动时会从 `.env` 文件加载。

| 环境变量          | 描述                                     | 默认值                                    |
| ----------------- | ---------------------------------------- | ----------------------------------------- |
| `A4F_BASE_URL`    | 上游 AI 服务的基地址。                   | `需在 .env 文件中设置`                      |
| `A4F_API_KEY`     | 用于访问上游服务的 API 密钥。            | `需在 .env 文件中设置`                    |
| `REDIS_URL`       | Redis 连接字符串。                       | `redis://redis:6379/0`                    |
| `MODELS_CACHE_TTL`| 模型列表缓存的过期时间（秒）。             | `300`                                     |
| `MASK_AS_BROWSER` | 是否将发往上游的请求伪装成浏览器。         | `True`                                    |

## API 端点

- `GET /health`: 健康检查端点。
- `GET /models`: 获取兼容 OpenAI 格式的模型列表（需要认证）。
- `POST /v1/chat/completions`: 代理聊天补全请求（需要认证）。
- `GET /context/{session_id}`: 获取指定会话的上下文历史（需要认证）。

## ✅ 运行测试

项目使用 `pytest` 进行测试。

```bash
pytest
```

## 🤝 贡献

欢迎提交问题和合并请求！

## 📄 许可证

本项目采用 MIT 许可证。详情请见 `LICENSE` 文件。