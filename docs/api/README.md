# 📖 API 文档

AI Higress 项目的完整 API 接口文档。

---

## 📚 文档列表

### [API 完整文档](./API_Documentation.md)
**文件**: `API_Documentation.md` (3276 行)

包含所有 API 接口的详细说明，包括：

#### 认证相关
- 用户注册、登录、登出
- Token 刷新和会话管理
- 定时开放注册管理

#### 用户管理
- 用户 CRUD 操作
- 用户权限管理
- 角色与权限（RBAC）

#### API 密钥管理
- 用户 API 密钥 CRUD
- 密钥权限控制
- 提供商访问限制

#### 积分与额度
- 积分查询和充值
- 积分消耗统计
- 自动充值配置

#### 提供商管理
- 提供商 CRUD 操作
- 模型列表查询
- 健康状态检查
- 厂商密钥管理

#### 路由管理
- 路由决策

#### 通知系统
- 通知 CRUD 操作
- 通知状态管理

#### 系统管理
- 系统配置
- 健康检查

### [用户概览指标](./metrics-user-overview.md)
**说明**: `/metrics/user-overview/*` 系列接口、缓存策略与前端映射

### [Dashboard v2 指标接口](./metrics-dashboard-v2.md)
**说明**: `/metrics/*`（用户页 + 系统页）指标接口、Token 估算口径与缓存策略

### [LinuxDo OAuth 接入](./linuxdo-oauth.md)
**说明**: LinuxDo Connect OAuth 登录流程、配置及回调接口

### [Workflows（工作流自动化）](./workflows.md)
**说明**: `/v1/workflows` 与 `/v1/workflow-runs/*`（Spec 模版、执行实例、SSE 事件流）

### [Admin Memory（系统记忆审核/发布）](./admin-memory.md)
**说明**: `/v1/admin/memories/*`（候选列表、审核发布、手动创建；Create/Approve 需显式 `project_id` 作为 embedding 调用上下文）

---

## 🔍 快速查找

### 按功能查找

| 功能 | 章节 | 说明 |
|------|------|------|
| 用户注册登录 | 认证 | POST /auth/register, /auth/login |
| Token 管理 | 认证 | POST /auth/refresh, /auth/logout |
| 会话管理 | 会话管理 | GET /v1/sessions |
| 用户信息 | 用户管理 | GET /users/me |
| API 密钥 | API密钥管理 | GET/POST/PUT/DELETE /users/{user_id}/api-keys |
| 积分查询 | 积分与额度 | GET /v1/credits/me |
| 积分消耗统计 | 积分与额度 | GET /v1/credits/me/consumption/* |
| 积分兑换 | 积分与额度 | POST /v1/credits/me/grant-token |
| 提供商列表 | 提供商管理 | GET /providers |
| 路由决策 | 路由管理 | POST /routing/decide |

### 按角色查找

#### 普通用户
- 认证相关接口
- 用户信息管理
- API 密钥管理
- 积分查询
- 积分兑换
- 提供商查询

#### 管理员
- 所有普通用户接口
- 用户管理（CRUD）
- 权限管理
- 积分充值
- 积分入账/兑换 token 签发
- 提供商管理
- 厂商密钥管理

---

## 📝 使用说明

### 认证方式

大部分接口需要 JWT 认证：

```http
Authorization: Bearer <access_token>
```

### 错误响应格式

```json
{
  "detail": "错误信息"
}
```

或

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "错误信息",
    "details": {}
  }
}
```

### 常见状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 204 | 删除成功（无内容） |
| 400 | 请求参数错误 |
| 401 | 未认证或 Token 无效 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 422 | 验证错误 |
| 500 | 服务器错误 |

---

## 🔄 文档更新

### 更新原则
- API 变更时，立即更新文档
- 保持文档与代码同步
- 添加必要的示例和说明

### 更新流程
1. 修改 `API_Documentation.md`
2. 更新相关章节
3. 添加变更说明
4. 提交 PR

---

## 📞 相关资源

- [后端设计文档](../backend/) - 后端架构和实现
- [前端文档](../fronted/) - 前端集成指南
- [主文档导航](../README.md) - 返回文档首页

---

**最后更新**: 2025-12-11  
**维护者**: AI Higress Team
