<div align="center">
  <a href="https://ai.ethereals.space">
    <img src="docs/images/logo.svg" alt="Logo" width="500" height="200">
  </a>
  <h3 align="center">AI-HIGRESS-GATEWAY</h3>

  <p align="center">
    Enterprise-grade Intelligent AI Gateway for Companies, Teams, and Individuals
    <br />
    <a href="https://ai.ethereals.space">View Demo</a>
    ·
    <a href="https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/issues">Report Bug</a>
    ·
    <a href="https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/pulls">Request Feature</a>
  </p>

  <p align="center">
    <img src="https://img.shields.io/pypi/pyversions/fastapi?style=flat-square&logo=python" alt="python">
    <img src="https://img.shields.io/badge/Next.js-14.0-black?style=flat-square&logo=next.js" alt="Next.js">
    <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
    <img src="https://img.shields.io/github/stars/MarshallEriksen-Neura/AI-Higress-Gateway?style=social" alt="Stars">
  </p>

  <p align="center">
    <a href="README.md">English</a> · <a href="README.zh.md">中文</a>
  </p>
</div>

## 📖 Table of Contents

- [✨ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [🖥️ Demo](#️-demo)
- [🛠️ Tech Stack](#️-tech-stack)
- [🚀 Quick Start](#-quick-start)
- [🚧 Project Status](#-project-status)
- [📚 Documentation](#-documentation)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## ✨ Features

We are committed to building a high-performance, highly available AI gateway service that supports multiple provider configurations, intelligent degradation, and load balancing across multiple API keys.

### 🎯 Core Features

- 🔀 **Intelligent Routing & Load Balancing**
  - Multi-dimensional routing strategies (latency-first/cost-first/reliability-first/balanced mode)
  - Real-time Provider health monitoring with automatic failover
  - Failure cooldown mechanism to avoid repeated calls to problematic nodes
  - Multiple API Key polling with QPS rate limiting
  - Dynamic routing by model with physical-to-logical model mapping

- 🏢 **Private Provider Support**
  - Users can create private AI providers with custom API endpoints
  - Support for HTTP, official SDKs (OpenAI/Claude/Google/VertexAI), and Claude CLI modes
  - Private sharing mechanism with authorized user access
  - Real-time probe monitoring to detect upstream availability
  - Submit shared Providers to public pool (requires admin approval)

- 💬 **Enterprise-grade Session Management**
  - JWT Token + Redis session storage
  - Multi-device login management with remote logout support
  - Token rotation mechanism to prevent replay attacks
  - Device fingerprinting and anomaly detection
  - Complete session audit logs

- 🧩 **Cloud MCP & Agent Workflow**
  - Support for Model Context Protocol to easily extend Agent capabilities
  - Agent workflow orchestration (🚧 In Development)
  - Cloud tool library management
  - Multi-modal dialogue support (text/image/audio)

- 🔍 **Intelligent Model Management**
  - Automatic discovery of Provider-supported model lists
  - Model alias mapping to unify logical model names
  - Fine-grained model enable/disable per Provider
  - Capability tag override (chat/vision/function_calling/image_generation, etc.)
  - Static model configuration for scenarios without `/models` endpoint

### 🚀 Additional Highlights

- 🤖 **Multi-model Support**: Seamlessly integrate OpenAI, DeepSeek, Claude, Google Gemini, Vertex AI, and other mainstream models
- ⚡ **High-performance Architecture**: Built on FastAPI + Celery async tasks, supporting high-concurrency request forwarding
- 💳 **Credit Management System**: Flexible quota control, auto top-up, consumption statistics, and reports
- 📊 **Real-time Monitoring**: Provider-level metrics, time series data, request log tracking
- 🔐 **Enterprise Security**: RBAC permission system, API key management, encrypted storage
- 🎨 **Modern UI**: Immersive management interface built with Next.js 14 + shadcn/ui
- 🖼️ **Image Generation**: Support for OpenAI, Gemini, Imagen, and other text-to-image models
- 🌐 **Proxy Pool Management**: Upstream proxy health checks, failure cooldown, dynamic switching

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User/Application Layer                │
│    Web UI (Next.js)  │  API Clients  │  CLI Tools          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway (FastAPI)                   │
│  ┌──────────────┬──────────────┬──────────────┬───────────┐│
│  │ Auth/AuthZ   │ Routing      │ Rate Limit   │ Monitoring││
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
      │ (Cache)  │  │ (Storage)│  │ (Tasks)  │
      └──────────┘  └──────────┘  └──────────┘
```

### Core Components

- **API Gateway**: Unified entry point for authentication, routing, rate limiting, etc.
- **Smart Router**: Intelligent routing engine selecting optimal Provider based on multi-dimensional metrics
- **Provider Manager**: Manages multiple AI provider configurations and health status
- **Credit System**: Credit management to control user quota consumption
- **Monitoring**: Real-time monitoring of Provider performance metrics
- **Session Manager**: JWT session management with multi-device login control

## 🖥️ Demo

### Dashboard

<table>
<tr>
<td width="50%">
<img src="docs/images/dashboard.png" alt="Default Theme Dashboard" />
<p align="center"><em>Default Theme</em></p>
</td>
<td width="50%">
<img src="docs/images/dark_dashboard.png" alt="Dark Theme Dashboard" />
<p align="center"><em>Dark Theme</em></p>
</td>
</tr>
</table>

<p align="center">
<img src="docs/images/christmas_dashboard.png" alt="Christmas Theme Dashboard" width="80%" />
<br/><em>Christmas Theme</em>
</p>

### Provider Management

<table>
<tr>
<td width="50%">
<img src="docs/images/provider-list.png" alt="Provider List" />
<p align="center"><em>Default Theme</em></p>
</td>
<td width="50%">
<img src="docs/images/dark_provider_list.png" alt="Dark Theme Provider List" />
<p align="center"><em>Dark Theme</em></p>
</td>
</tr>
</table>

<p align="center">
<img src="docs/images/christmas_provider_list.png" alt="Christmas Theme Provider List" width="80%" />
<br/><em>Christmas Theme</em>
</p>

### Chat Interface

<p align="center">
<img src="docs/images/chat.png" alt="Chat Interface" width="80%" />
<br/><em>AI Conversation Interface</em>
</p>

## 🛠️ Tech Stack

### Backend
* **Framework**: FastAPI (Python 3.10+)
* **Async Tasks**: Celery + Redis
* **Database**: PostgreSQL + SQLAlchemy
* **Cache/Session**: Redis
* **Authentication**: JWT + Passlib
* **API Clients**: HTTPX, OpenAI SDK, Anthropic SDK, Google SDK

### Frontend
* **Framework**: Next.js 14 (App Router)
* **UI Components**: shadcn/ui + Radix UI
* **Styling**: TailwindCSS
* **State Management**: React Hooks
* **HTTP Client**: Axios

### Infrastructure
* **Containerization**: Docker + Docker Compose
* **Reverse Proxy**: Nginx (optional)
* **Object Storage**: Aliyun OSS / S3-compatible storage (optional)
* **Monitoring**: Built-in metrics collection + time series data

## 🚀 Quick Start

### Prerequisites

* Python 3.10+
* Node.js 18+
* Docker (optional)

### Installation Steps

1. Clone the repository
   ```bash
   git clone https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway.git
   cd AI-Higress-Gateway
   cp .env.example .env
   docker compose -f docker-compose.images.yml up -d
   ```

2. Frontend Setup
   ```bash
   cd frontend
   cp .env.example .env
   bun install
   bun dev
   ```

3. Cloud MCP Configuration
   ```bash
   git clone https://github.com/MarshallEriksen-Neura/mcp-higress-gateway.git
   cd mcp-higress-gateway
   cp .env.example .env
   docker compose up -d
   ```

## 🚧 Project Status

> **⚡ This project is under active development!** We are continuously adding new features, optimizing performance, and fixing issues. Stay tuned for the latest updates!

**Recent Updates**:
- ✅ Completed intelligent routing and load balancing system
- ✅ Implemented private Provider support with probe monitoring
- ✅ Enhanced session management and security mechanisms
- ✅ Implemented automatic model discovery and disable functionality
- 🚧 Agent workflow orchestration in development
- 🚧 Cloud MCP tool library in development

## 📚 Documentation

This README provides a quick overview. For more detailed feature descriptions, API documentation, and configuration guides, please refer to:

- 📖 [Complete Documentation](./docs/README.zh.md)
- 🌐 [API Documentation](./docs/api/API_Documentation.md)
- 🏗️ [Architecture Design](./docs/backend/)
- 🎨 [Frontend Documentation](./docs/fronted/)

## 🤝 Contributing

Contributions are welcome! We welcome all forms of contributions:

- 🐛 [Report Bugs](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/issues)
- 💡 [Feature Requests](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/issues)
- 📝 Improve documentation
- 🔧 Submit code fixes or new features

## 💬 Community & Support

- 📖 [Documentation](./docs)
- 🐛 [Issue Tracker](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway/issues)
- 🌟 [Star the Project](https://github.com/MarshallEriksen-Neura/AI-Higress-Gateway)

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=MarshallEriksen-Neura/AI-Higress-Gateway&type=Date)](https://star-history.com/#MarshallEriksen-Neura/AI-Higress-Gateway&Date)

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details

---

<div align="center">
  <strong>Made with ❤️ by MarshallEriksen-Neura Team</strong>
  <br/>
  <sub>If this project helps you, please give us a ⭐️</sub>
</div>
