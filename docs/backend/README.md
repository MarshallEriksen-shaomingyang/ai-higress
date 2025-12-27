# 🔧 后端文档

AI Higress 后端架构设计、核心功能设计和实现文档。

---

## 📚 核心设计文档

### [文生图：OSS 短链 + Celery 异步化 + 会话历史融合](./image-generation-async-and-history.md)
**重要性**: ⭐⭐⭐⭐

文生图后端能力与后续演进方案，包括：
- `/v1/images/generations`（OpenAI 兼容）两条上游 lane
- OSS 私有桶 + 网关签名短链（`/media/images/...`）
- 复用 `chat_run` 的 Celery 异步执行与 RunEvent 事件流
- 与会话历史（`chat_messages`/`chat_runs`）融合的最小改动策略

**适用场景**: 接入文生图、做异步化/队列化、让生图进入聊天历史

---

### [会话上下文设计](./session-context-design.md)
**重要性**: ⭐⭐⭐⭐⭐

会话管理的核心架构设计，包括：
- 会话上下文存储
- 粘性路由实现
- 会话生命周期管理
- Redis 数据结构设计

**适用场景**: 理解会话管理机制、实现会话相关功能

---

### [密钥管理](./key-management.md)
**重要性**: ⭐⭐⭐⭐

API 密钥和厂商密钥的管理设计，包括：
- 用户 API 密钥管理
- 厂商 API 密钥管理
- 密钥权限控制
- 密钥轮换策略

**适用场景**: 实现密钥相关功能、理解权限控制

---

### [安全加固](./security-hardening.md)
**重要性**: ⭐⭐⭐⭐

系统安全设计和加固方案，包括：
- JWT Token 安全
- Redis 安全
- API 安全
- 数据加密

**适用场景**: 安全审计、安全功能实现

---

### [指标优化](./metrics_optimization.md)
**重要性**: ⭐⭐⭐

性能指标优化方案，包括：
- 指标收集优化
- 数据聚合策略
- 缓存策略
- 查询优化

**适用场景**: 性能优化、监控系统实现

---

## 🗂️ 已完成项目归档

**位置**: [`archived/`](./archived/)

包含已完成的实现计划、任务总结和 bug 修复文档：

### JWT Token Redis 存储
- [实现计划](./archived/jwt-redis-storage-plan.md)
- [实施总结](./archived/jwt-redis-storage-implementation-summary.md)

### Token 刷新优化
- [竞态条件修复](./archived/token-refresh-race-condition-fix.md)

### 指标系统
- [精度聚合计划](./archived/metrics_precision_aggregation_plan.md)

### 其他
- [Claude 降级方案](./archived/claude_fallback_plan.md)

---

## 🏗️ 技术栈

### 核心框架
- **Python 3.12**
- **FastAPI** - Web 框架
- **SQLAlchemy** - ORM
- **Alembic** - 数据库迁移

### 数据存储
- **PostgreSQL** - 主数据库
- **Redis** - 缓存和会话存储

### 异步任务
- **Celery** - 异步任务队列
- **Redis** - 消息代理

### 认证与安全
- **JWT** - Token 认证
- **python-jose** - JWT 实现
- **passlib** - 密码哈希

---

## 📖 开发指南

### 项目结构

```
backend/
├── app/
│   ├── api/              # API 路由
│   ├── models/           # 数据模型
│   ├── schemas/          # Pydantic 模型
│   ├── services/         # 业务逻辑
│   ├── storage/          # 存储层（Redis）
│   ├── tasks/            # Celery 任务
│   └── utils/            # 工具函数
├── alembic/              # 数据库迁移
├── tests/                # 测试
└── main.py               # 入口文件
```

### 代码规范

- **命名**: `snake_case` 函数/变量，`PascalCase` 类
- **类型提示**: 所有函数都应有类型提示
- **文档字符串**: 使用 Google 风格
- **异步**: 优先使用 async/await

### 测试规范

- 使用 `pytest` 和 `pytest-asyncio`
- 测试文件命名：`test_<feature>.py`
- 测试函数命名：`test_<case>()`
- 每个新功能都应有对应测试

---

## 🔍 快速查找

### 我想了解...

#### 会话管理
→ [会话上下文设计](./session-context-design.md)

#### 密钥管理
→ [密钥管理](./key-management.md)

#### 安全设计
→ [安全加固](./security-hardening.md)

#### 性能优化
→ [指标优化](./metrics_optimization.md)

#### 已完成的项目
→ [归档文档](./archived/)

---

## 📝 文档维护

### 新增设计文档
1. 在 `docs/backend/` 创建文档
2. 使用清晰的标题和章节
3. 添加必要的代码示例
4. 更新本 README

### 项目完成后
1. 将实现计划和总结移到 `archived/`
2. 保留核心设计文档
3. 更新相关链接

---

## 📞 相关资源

- [API 文档](../api/) - API 接口文档
- [前端文档](../fronted/) - 前端实现文档
- [主文档导航](../README.md) - 返回文档首页

---

**最后更新**: 2025-12-11  
**维护者**: AI Higress Team
