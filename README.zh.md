<div align="center">
  <a href="https://ai.ethereals.space">
    <img src="docs/images/logo.svg" alt="Logo" width="500" height="200">
  </a>
  <h3 align="center">AI-HIGRESS-GATEWAY</h3>

  <p align="center">
    为公司，团体，个人打造的企业级智能AI网关
    <br />
    <a href="https://ai.ethereals.space">查看 Demo</a>
    ·
    <a href="https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/issues">报告 Bug</a>
    ·
    <a href="https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/pulls">提交 Feature</a>
  </p>
  
  <p align="center">
    <img src="https://img.shields.io/pypi/pyversions/fastapi
?style=flat-square&logo=python" alt="python">
    <img src="https://img.shields.io/badge/Next.js-14.0-black?style=flat-square&logo=next.js" alt="Next.js">
    <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
    <img src="https://img.shields.io/github/stars/MarshallEriksen-Neura/AI-Higress-Gateway?style=social" alt="Stars">
  </p>
</div>

## 📖 目录

- [✨ 特性 (Features)](#-特性-features)
- [🏗️ 架构设计 (Architecture)](#️-架构设计-architecture)
- [🖥️ 演示 (Demo)](#️-演示-demo)
- [🛠️ 技术栈 (Tech Stack)](#️-技术栈-tech-stack)
- [🚀 快速开始 (Getting Started)](#-快速开始-getting-started)
- [📚 主要功能 (Key Features)](#-主要功能-key-features)
- [🔧 配置说明 (Configuration)](#-配置说明-configuration)
- [📊 监控与运维 (Monitoring)](#-监控与运维-monitoring)
- [🗺️ 路线图 (Roadmap)](#️-路线图-roadmap)
- [📄 许可证 (License)](#-许可证-license)

---

## ✨ 特性 (Features)

我们致力于打造高性能，高可用的AI网关服务，支持多provider配置，智能降级， 多api key 的负载均衡

### 🎯 核心特性

- 🔀 **智能路由与负载均衡**
  - 多维度路由策略（延迟优先/成本优先/可靠性优先/均衡模式）
  - 实时监控Provider健康状态，自动故障切换
  - 失败冷却机制，避免重复调用问题节点
  - 多API Key轮询，QPS限流保护
  - 按模型动态路由，支持物理模型到逻辑模型映射

- 🏢 **私有Provider支持**
  - 用户可自建私有AI提供商，支持自定义API端点
  - 支持HTTP、官方SDK（OpenAI/Claude/Google/VertexAI）、Claude CLI模式
  - 私密分享机制，可授权特定用户访问
  - 实时探针监控，自动检测上游可用性
  - 提交共享Provider到公共池（需管理员审核）

- 💬 **企业级会话管理**
  - JWT Token + Redis 会话存储
  - 多设备登录管理，支持远程登出
  - Token轮换机制，防止重用攻击
  - 设备指纹识别，异常登录检测
  - 完整的会话审计日志

- 🧩 **云端MCP与Agent工作流**
  - 支持Model Context Protocol，轻松扩展Agent能力
  - Agent工作流编排（🚧 开发中）
  - 云端工具库管理
  - 多模态对话支持（文本/图像/音频）

- 🔍 **智能模型管理**
  - 自动发现Provider支持的模型列表
  - 模型别名映射，统一逻辑模型名称
  - 按Provider细粒度禁用/启用模型
  - 能力标记覆盖（chat/vision/function_calling/image_generation等）
  - 静态模型配置，应对无`/models`端点的场景

### 🚀 其他亮点

- 🤖 **多模型支持**：无缝接入 OpenAI, DeepSeek, Claude, Google Gemini, Vertex AI 等主流模型
- ⚡ **高性能架构**：基于FastAPI + Celery异步任务，支持高并发请求转发
- 💳 **积分管理系统**：灵活的额度控制、自动充值、消费统计与报表
- 📊 **实时监控**：Provider级别指标、时间序列数据、请求日志追踪
- 🔐 **企业级安全**：RBAC权限体系、API密钥管理、加密存储
- 🎨 **现代化 UI**：使用 Next.js 14 + shadcn/ui 打造的沉浸式管理界面
- 🖼️ **图像生成**：支持OpenAI、Gemini、Imagen等多种文生图模型
- 🌐 **代理池管理**：上游代理自动测活、失败冷却、动态切换

## 🏗️ 架构设计 (Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                        用户/应用层                            │
│    Web UI (Next.js)  │  API Clients  │  CLI Tools          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway (FastAPI)                   │
│  ┌──────────────┬──────────────┬──────────────┬───────────┐│
│  │ 认证/鉴权     │ 路由决策      │ 限流/熔断     │ 监控追踪  ││
│  └──────────────┴──────────────┴──────────────┴───────────┘│
└─────────────────────────┬───────────────────────────────────┘
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ OpenAI   │  │ Claude   │  │ Gemini   │
      │ Provider │  │ Provider │  │ Provider │
      └──────────┘  └──────────┘  └──────────┘
            │             │             │
            └─────────────┴─────────────┘
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ Redis    │  │PostgreSQL│  │ Celery   │
      │ (缓存/会话)│  │ (数据持久化)│  │ (异步任务) │
      └──────────┘  └──────────┘  └──────────┘
```

### 核心组件

- **API Gateway**: 统一入口，处理认证、路由、限流等
- **Smart Router**: 智能路由引擎，基于多维度指标选择最优Provider
- **Provider Manager**: 管理多个AI提供商配置和健康状态
- **Credit System**: 积分管理，控制用户额度消费
- **Monitoring**: 实时监控各Provider性能指标
- **Session Manager**: JWT会话管理，多设备登录控制

## 🖥️ 演示 (Demo)

### 仪表盘 (Dashboard)

<table>
<tr>
<td width="50%">
<img src="docs/images/dashboard.png" alt="默认主题仪表盘" />
<p align="center"><em>默认主题</em></p>
</td>
<td width="50%">
<img src="docs/images/dark_dashboard.png" alt="暗色主题仪表盘" />
<p align="center"><em>暗色主题</em></p>
</td>
</tr>
</table>

<p align="center">
<img src="docs/images/christmas_dashboard.png" alt="圣诞主题仪表盘" width="80%" />
<br/><em>圣诞主题</em>
</p>

### Provider管理 (Provider Management)

<table>
<tr>
<td width="50%">
<img src="docs/images/provider-list.png" alt="Provider列表" />
<p align="center"><em>默认主题</em></p>
</td>
<td width="50%">
<img src="docs/images/dark_provider_list.png" alt="暗色主题Provider列表" />
<p align="center"><em>暗色主题</em></p>
</td>
</tr>
</table>

<p align="center">
<img src="docs/images/christmas_provider_list.png" alt="圣诞主题Provider列表" width="80%" />
<br/><em>圣诞主题</em>
</p>

### 聊天界面 (Chat Interface)

<p align="center">
<img src="docs/images/chat.png" alt="聊天界面" width="80%" />
<br/><em>AI对话界面</em>
</p>

## 🛠️ 技术栈 (Tech Stack)

### 后端 (Backend)
* **框架**: FastAPI (Python 3.10+)
* **异步任务**: Celery + Redis
* **数据库**: PostgreSQL + SQLAlchemy
* **缓存/会话**: Redis
* **认证**: JWT + Passlib
* **API客户端**: HTTPX, OpenAI SDK, Anthropic SDK, Google SDK

### 前端 (Frontend)
* **框架**: Next.js 14 (App Router)
* **UI组件**: shadcn/ui + Radix UI
* **样式**: TailwindCSS
* **状态管理**: React Hooks
* **HTTP客户端**: Axios

### 基础设施 (Infrastructure)
* **容器化**: Docker + Docker Compose
* **反向代理**: Nginx (可选)
* **对象存储**: 阿里云OSS / S3兼容存储 (可选)
* **监控**: 内置指标收集 + 时序数据

## 🚀 快速开始 (Getting Started)

### 前置要求

* Python 3.10+
* Node.js 18+
* Docker (可选)

### 安装步骤

1. 克隆仓库
   ```bash
   git clone https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway.git
   cp .env env
   docker compose up -f docker-compose.images.yml -d
2. 前端
   ```bash
   cd fronted
   cp .env env
   bun dev
   ```
3. 云端mcp配置
   ```bash
   git clone https://github.com/MarshallEriksen-Neura/mcp-higress-gateway.git
   cp .env env
   docker compose up -d
   ```
## 🚧 项目状态 (Project Status)

> **⚡ 本项目正处于积极开发中！** 我们持续添加新功能、优化性能并修复问题。欢迎关注项目获取最新进展！

**最近更新**:
- ✅ 完成智能路由与负载均衡系统
- ✅ 实现私有Provider支持与探针监控
- ✅ 完善会话管理与安全机制
- ✅ 实现模型自动发现与禁用功能
- 🚧 Agent工作流编排开发中
- 🚧 云端MCP工具库开发中

## 📚 完整文档

本 README 提供快速概览。更详细的功能说明、API 文档和配置指南，请查看：

- 📖 [完整中文文档](./docs/README.zh.md)
- 🌐 [API 文档](./docs/api/API_Documentation.md)
- 🏗️ [架构设计](./docs/backend/)
- 🎨 [前端文档](./docs/fronted/)

## 🤝 贡献 (Contributing)

欢迎贡献！我们欢迎任何形式的贡献：

- 🐛 [报告Bug](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/issues)
- 💡 [功能建议](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/issues)
- 📝 改进文档
- 🔧 提交代码修复或新功能

## 💬 社区与支持

- 📖 [完整文档](./docs)
- 🐛 [问题跟踪](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/issues)
- 🌟 [Star项目](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway)

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=MarshallEriksen-Neura/AI-Higress-Gateway&type=Date)](https://star-history.com/#MarshallEriksen-Neura/AI-Higress-Gateway&Date)

## 📄 许可证 (License)

MIT License - 详见 [LICENSE](LICENSE) 文件

---

<div align="center">
  <strong>Made with ❤️ by MarshallEriksen-Neura Team</strong>
  <br/>
  <sub>如果这个项目对您有帮助，请给我们一个 ⭐️</sub>
</div>
