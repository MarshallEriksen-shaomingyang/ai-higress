# 密钥管理文档

## 概述

本文档描述了AI Higress项目中密钥管理的架构和使用方法。重构后的密钥系统明确分离了不同类型的密钥，提供了更清晰的职责划分和更安全的管理方式。

## 密钥类型

### 1. 系统主密钥 (SYSTEM_MASTER_KEY)

**用途**：
- 派生其他密钥的根密钥
- 加密/解密敏感数据
- 生成哈希值

**管理方式**：
- 通过系统API生成：`POST /system/secret-key/generate`
- 存储在环境变量或安全配置中
- 轮换需要谨慎，会导致所有密码和API密钥失效

**示例**：
```bash
# 通过API生成（需要超级管理员JWT令牌）
curl -X POST "http://localhost:8000/system/secret-key/generate" \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"length": 64}'
```

### 2. 用户密码哈希 (USER_PASSWORD_HASH)

**用途**：
- 验证用户登录
- 存储在数据库中，不存储明文

**管理方式**：
- 用户注册时自动生成哈希
- 使用bcrypt算法，独立于系统主密钥
- 可通过用户API更新

**示例**：
```bash
# 用户注册
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@example.com", "password": "securepassword"}'
```

### 3. JWT访问令牌 (JWT_ACCESS_TOKEN)

**用途**：
- 用户登录后的会话管理
- 访问需要用户认证的API

**管理方式**：
- 登录时自动生成
- 有效期30分钟（可配置）
- 可通过刷新令牌获取新的访问令牌

**示例**：
```bash
# 用户登录获取JWT令牌
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "securepassword"}'

# 使用JWT令牌访问API
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer <jwt_token>"
```

### 4. API密钥 (API_KEY)

**用途**：
- 第三方应用访问服务API
- 区分用户身份和权限
- 可限制可访问的厂商提供商

**管理方式**：
- 通过JWT认证的API创建和管理
- 存储在数据库中，使用系统主密钥哈希
- 可设置过期时间和权限限制
- 具备 `is_active` / `disabled_reason` 状态字段，后台 Celery 任务会：
  - 定期扫描已过期密钥并标记为不可用；
  - 按时间窗口统计调用错误率，超过阈值会自动禁用（并同步清理 Redis 缓存）。

**示例**：
```bash
# 使用JWT令牌创建API密钥
curl -X POST "http://localhost:8000/users/{user_id}/api-keys" \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-app-key", "expiry": "MONTH"}'

# 使用API密钥访问服务
curl -X GET "http://localhost:8000/models" \
  -H "Authorization: Bearer <api_key>"
```

### 5. 厂商API密钥 (PROVIDER_API_KEY)

**用途**：
- 访问外部AI服务提供商（如OpenAI、Claude等）
- 管理多个厂商的多个密钥
- 负载均衡和故障转移

**管理方式**：
- 仅超级管理员可通过API管理
- 存储在数据库中，使用系统主密钥加密
- 可设置权重和QPS限制

**示例**：
```bash
# 创建厂商API密钥（需要超级管理员JWT令牌）
curl -X POST "http://localhost:8000/providers/{provider_id}/keys" \
  -H "Authorization: Bearer <superuser_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-...", "label": "primary-key", "weight": 1.0, "max_qps": 10}'
```

## API版本

### API密钥认证路由
- 路径：`/users/{user_id}/api-keys/*`
- 认证方式：API密钥
- 用途：客户端应用访问AI服务

### JWT认证路由
- 路径：`/auth/*`, `/users/*`, `/provider-keys/*`, `/system/*`
- 认证方式：JWT令牌
- 用途：用户管理、API密钥管理、厂商密钥管理、系统管理

### 系统API
- 路径：`/system/*`
- 认证方式：JWT令牌（需要超级管理员权限）
- 用途：系统初始化和密钥管理

### 认证API
- 路径：`/auth/*`
- 认证方式：无需认证或JWT令牌
- 用途：用户登录、注册、令牌刷新

## 使用流程

### 1. 系统初始化

```bash
# 1. 生成系统主密钥
curl -X POST "http://localhost:8000/system/secret-key/generate" \
  -H "Authorization: Bearer <initial_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"length": 64}'

# 2. 将生成的密钥添加到环境变量
export SECRET_KEY="your_generated_secret_key"

# 3. 初始化系统管理员
curl -X POST "http://localhost:8000/system/admin/init" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "email": "admin@example.com", "display_name": "System Administrator"}'

# 4. 使用返回的凭据登录获取JWT令牌
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "<returned_password>"}'
```

### 2. 普通用户使用流程

```bash
# 1. 用户注册
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@example.com", "password": "securepassword"}'

# 2. 用户登录获取JWT令牌
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "securepassword"}'

# 3. 使用JWT令牌创建API密钥
curl -X POST "http://localhost:8000/v2/users/{user_id}/api-keys" \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-app-key", "expiry": "MONTH"}'

# 4. 使用API密钥访问AI服务
curl -X GET "http://localhost:8000/models" \
  -H "Authorization: Bearer <api_key>"
```

## 安全最佳实践

1. **系统主密钥**：
   - 使用足够强度的随机密钥（至少64字符）
   - 存储在安全的位置，如环境变量或密钥管理服务
   - 定期轮换，但注意轮换会导致所有密码和API密钥失效

2. **用户密码**：
   - 强制使用强密码策略
   - 使用bcrypt哈希，加盐处理
   - 定期提醒用户更新密码

3. **API密钥**：
   - 为每个应用生成独立的API密钥
   - 设置适当的权限限制和过期时间
   - 监控API密钥的使用情况

4. **JWT令牌**：
   - 设置合理的过期时间
   - 使用HTTPS传输
   - 实现令牌黑名单机制以支持登出

5. **厂商API密钥**：
   - 定期轮换厂商密钥
   - 使用加密存储
   - 实现密钥健康检查和自动故障转移

## 故障排查

### 常见错误

1. **Invalid authentication token**
   - 检查令牌是否正确复制
   - 检查令牌是否已过期
   - 确认使用的是正确的令牌类型（JWT或API密钥）

2. **User account is disabled**
   - 联系管理员启用账户
   - 检查账户是否因违规被禁用

3. **权限不足**
   - 确认用户具有所需权限
   - 对于系统操作，确认是超级管理员

### 密钥恢复

如果丢失系统主密钥，需要：

1. 生成新的系统主密钥
2. 使用`/system/secret-key/rotate`端点轮换
3. 重新设置所有用户密码
4. 重新生成所有API密钥

## 开发指南

### 添加新的密钥类型

1. 在`app/services/key_management_service.py`中添加生成和管理逻辑
2. 在`docs/key-management.md`中更新文档
3. 添加相应的API端点和测试

### 自定义认证逻辑

1. 修改`app/jwt_auth.py`中的认证中间件
2. 更新`app/services/jwt_auth_service.py`中的令牌生成逻辑
3. 添加相应的测试

## 迁移指南

从旧版本迁移到新的密钥系统：

1. 备份现有数据库
2. 生成新的系统主密钥
3. 运行数据库迁移脚本
4. 通知所有用户更新密码和API密钥
5. 更新客户端应用使用新的认证方式

---

如有问题，请联系开发团队或查看项目Wiki获取更多信息。