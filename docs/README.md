# 📚 AI Higress 项目文档

欢迎来到 AI Higress 项目文档中心！本文档提供了项目的完整技术文档和开发指南。

---

## 🗂️ 文档导航

### 📖 API 文档
**位置**: [`docs/api/`](./api/)

完整的 API 接口文档，包括请求参数、响应格式和认证方式。

- [API 完整文档](./api/API_Documentation.md) - 所有 API 接口的详细说明

---

### 🔧 后端文档
**位置**: [`docs/backend/`](./backend/)

后端架构设计、核心功能设计和实现文档。

#### 核心设计文档
- [会话上下文设计](./backend/session-context-design.md) - 会话管理核心架构
- [密钥管理](./backend/key-management.md) - API 密钥和厂商密钥管理
- [安全加固](./backend/security-hardening.md) - 系统安全设计
- [指标优化](./backend/metrics_optimization.md) - 性能指标优化方案

#### 已完成项目归档
- [归档文档](./backend/archived/) - 已完成的实现计划和任务总结

---

### 🎨 前端文档
**位置**: [`docs/frontend/`](./frontend/)

前端采用 **"新中式数字水墨 (Digital Ink)"** 设计哲学，追求呼吸感、秩序感与琉璃质感的统一。

#### 核心设计与视觉
- [设计规范 v2.0 (ui-prompt)](../ui-prompt.md) - 全局设计灵魂与 AI 提示词
- [Chat UI 设计规范](./frontend/chat-ui-design.md) - 对话流视觉美学
- [SEO 与响应式设计](./frontend/seo-and-responsive.md) - SEO 和响应式设计
- [PWA 桌面安装计划](./frontend/pwa-desktop-installation-plan.md) - PWA 功能规划

#### 功能模块文档
**位置**: [`docs/frontend/features/`](./frontend/features/)

按功能模块组织的设计文档：

- **认证模块** ([`auth/`](./frontend/features/auth/))
  - [架构设计](./frontend/features/auth/architecture.md)
  - [中间件方案](./frontend/features/auth/middleware-approach.md)
  - [测试指南](./frontend/features/auth/testing-guide.md)

- **路由模块** ([`routing/`](./frontend/features/routing/))
  - [架构设计](./frontend/features/routing/architecture.md)

- **提供商模块** ([`providers/`](./frontend/features/providers/))
  - [密钥管理设计](./frontend/features/providers/keys-management-design.md)

- **权限模块** ([`permissions/`](./frontend/features/permissions/))
  - [管理设计](./frontend/features/permissions/management-design.md)

- **通知模块** ([`notifications/`](./frontend/features/notifications/))
  - [系统设计](./frontend/features/notifications/system-design.md)

- **积分模块** ([`credits/`](./frontend/features/credits/))
  - [页面设计](./frontend/features/credits/page-design.md)

- **管理员模块** ([`admin/`](./frontend/features/admin/))
  - [权限管理](./frontend/features/admin/permission-management.md)

- **系统模块** ([`system/`](./frontend/features/system/))
  - [上游代理管理](./frontend/features/system/upstream-proxy-management.md)

- [工作流自动化](./frontend/features/workflow-automation.md) - 工作流功能设计

#### OAuth 集成文档
- [OAuth 集成指南](./frontend/oauth-integration.md) - OAuth 完整指南
- [OAuth 快速开始](./frontend/oauth-quick-start.md) - 快速接入指南
- [Linuxdo OAuth 集成](./frontend/oauth-linuxdo-integration.md) - Linuxdo 平台集成

#### 聊天与图像功能
- [聊天图像生成集成](./frontend/chat-image-generation-integration.md) - 图像生成功能
- [聊天助手历史评估集成](./frontend/chat-assistants-history-eval-integration.md) - 助手系统集成
- [CLI 配置集成](./frontend/cli-config-integration.md) - CLI 配置管理

#### UI 组件文档
- [Neon Card 使用指南](./frontend/neon-card-usage.md) - Neon 卡片组件
- [Theme Card 使用指南](./frontend/theme-card-usage.md) - 主题卡片组件
- [图像主机配置](./frontend/image-hostname-config.md) - 图像配置

#### 已完成项目归档
- [归档文档](./frontend/archived/) - 已完成的实现计划和任务总结

---

## 📋 文档分类说明

### 🟢 核心设计文档
这些文档描述了系统的核心架构和设计决策，是理解项目的关键参考：
- API 文档
- 架构设计文档
- 核心功能设计文档

### 🟡 功能模块文档
按功能模块组织的设计文档，描述了各个功能的实现方案：
- 认证、路由、提供商、权限等模块
- 每个模块包含架构设计、实现方案、测试指南等

### 🔵 已完成项目归档
已完成的实现计划、任务总结和迁移文档：
- 保留历史记录，便于回溯
- 不在主目录显示，避免混淆

---

## 🔍 快速查找

### 我想了解...

#### API 接口
→ [API 完整文档](./api/API_Documentation.md)

#### 后端架构
→ [会话上下文设计](./backend/session-context-design.md)  
→ [密钥管理](./backend/key-management.md)  
→ [安全加固](./backend/security-hardening.md)

#### 前端架构
→ [认证架构](./frontend/features/auth/architecture.md)
→ [路由架构](./frontend/features/routing/architecture.md)

#### 特定功能实现
→ 查看 [`frontend/features/`](./frontend/features/) 对应模块

#### 已完成的项目
→ [`backend/archived/`](./backend/archived/)
→ [`frontend/archived/`](./frontend/archived/)

---

## 📝 文档维护指南

### 新增文档时
1. **API 文档**: 更新 `docs/api/API_Documentation.md`
2. **后端设计**: 添加到 `docs/backend/`
3. **前端功能**: 添加到 `docs/frontend/features/<模块>/`
4. **已完成项目**: 移动到对应的 `archived/` 目录

### 文档命名规范
- 使用小写字母和连字符：`feature-name-design.md`
- 设计文档：`*-design.md` 或 `architecture.md`
- 实现计划：`*-plan.md` 或 `*-implementation.md`
- 任务总结：`*-summary.md`

### 保持文档同步
- API 变更时，立即更新 API 文档
- 架构调整时，更新对应的设计文档
- 功能完成后，将实现文档移到 `archived/`

---

## 📊 文档统计

| 类型 | 数量 | 说明 |
|------|------|------|
| API 文档 | 12 | 完整的 API 参考 |
| 后端核心文档 | 8 | 架构和核心功能设计 |
| 前端核心文档 | 17 | 系统级设计和规划 |
| 功能模块文档 | 10 | 按功能组织的设计文档 |
| 已归档文档 | 22 | 已完成的项目文档 |
| 开发文档 | 2 | 环境配置和开发指南 |

---

## 🤝 贡献指南

如果你想为文档做出贡献：

1. 确保文档清晰、准确、最新
2. 遵循现有的文档结构和命名规范
3. 添加必要的示例和图表
4. 更新相关的导航链接

---

## 📞 获取帮助

- 查看 [API 文档](./api/API_Documentation.md) 了解接口详情
- 查看 [功能模块文档](./frontend/features/) 了解实现方案
- 查看 [归档文档](./backend/archived/) 了解历史项目

---

**最后更新**: 2026-01-02
**维护者**: AI Higress Team
