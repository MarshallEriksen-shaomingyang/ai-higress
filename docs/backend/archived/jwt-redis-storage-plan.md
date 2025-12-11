# JWT Token Redis 存储实现计划

## 1. 项目概述

### 1.1 目标
实现基于 Redis 的 JWT token 存储和管理系统，提供以下功能：
- Token 持久化存储和验证
- Token 黑名单机制（支持主动撤销）
- Refresh Token 轮换和家族追踪
- 用户会话管理（查看和撤销活跃会话）
- 安全增强（防止 token 重放攻击）

### 1.2 当前状态分析
- ✅ 已有基础 JWT 认证实现（无状态）
- ✅ 已有 Redis 基础设施和服务层
- ✅ Access Token 过期时间：30 分钟
- ✅ Refresh Token 过期时间：7 天
- ❌ Token 未存储到 Redis
- ❌ 无法主动撤销 token
- ❌ 登出功能仅为占位符
- ❌ 无会话管理功能

### 1.3 技术栈
- Python 3.12 + FastAPI
- Redis (异步客户端 redis.asyncio)
- JWT (python-jose)
- 现有服务：`redis_client.py`, `redis_service.py`

---

## 2. Redis 数据模型设计

### 2.1 键命名规范

遵循现有项目的键命名模式（参考 `redis_service.py`）：

```python
# Token 存储键模板
ACCESS_TOKEN_KEY = "auth:access_token:{token_id}"
REFRESH_TOKEN_KEY = "auth:refresh_token:{token_id}"

# 用户会话索引键
USER_SESSIONS_KEY = "auth:user:{user_id}:sessions"

# Token 黑名单键
TOKEN_BLACKLIST_KEY = "auth:blacklist:{token_jti}"

# Refresh Token 家族键（用于检测 token 重用）
REFRESH_TOKEN_FAMILY_KEY = "auth:refresh_family:{family_id}"
```

### 2.2 数据结构

#### 2.2.1 Access Token 存储
```json
{
  "token_id": "uuid",
  "user_id": "uuid",
  "token_type": "access",
  "jti": "jwt_id",
  "issued_at": 1234567890,
  "expires_at": 1234569690,
  "device_info": {
    "user_agent": "Mozilla/5.0...",
    "ip_address": "192.168.1.1"
  }
}
```
- **TTL**: 30 分钟（与 JWT 过期时间一致）

#### 2.2.2 Refresh Token 存储
```json
{
  "token_id": "uuid",
  "user_id": "uuid",
  "token_type": "refresh",
  "jti": "jwt_id",
  "family_id": "uuid",
  "issued_at": 1234567890,
  "expires_at": 1234567890,
  "parent_jti": "previous_jwt_id",
  "device_info": {
    "user_agent": "Mozilla/5.0...",
    "ip_address": "192.168.1.1"
  },
  "revoked": false
}
```
- **TTL**: 7 天（与 JWT 过期时间一致）
- **family_id**: 用于追踪 token 轮换链
- **parent_jti**: 指向上一个 refresh token（用于检测重放）

#### 2.2.3 用户会话索引
```json
{
  "user_id": "uuid",
  "sessions": [
    {
      "session_id": "uuid",
      "refresh_token_jti": "jwt_id",
      "created_at": 1234567890,
      "last_used_at": 1234567890,
      "device_info": {}
    }
  ]
}
```
- **TTL**: 7 天（随最长的 refresh token 过期）

#### 2.2.4 Token 黑名单
```json
{
  "jti": "jwt_id",
  "user_id": "uuid",
  "revoked_at": 1234567890,
  "reason": "user_logout"
}
```
- **TTL**: 根据原 token 的剩余有效期设置

---

## 3. 核心功能设计

### 3.1 Token 生命周期管理流程

1. **用户登录** → 生成 Access + Refresh Token
2. **存储到 Redis** → 记录 token 信息和设备信息
3. **返回 Token 给客户端**
4. **客户端使用 Access Token** → 每次请求携带
5. **验证 Token** → 检查签名、过期时间、Redis 状态、黑名单
6. **Token 过期** → 使用 Refresh Token 获取新 token
7. **Token 轮换** → 生成新 token 对，撤销旧 refresh token
8. **用户登出** → 将 token 加入黑名单

### 3.2 Token 验证流程

#### 3.2.1 Access Token 验证
1. 验证 JWT 签名和过期时间
2. 提取 JTI（JWT ID）
3. 检查 Redis 中是否存在该 token
4. 检查是否在黑名单中
5. 验证用户状态（is_active）
6. 返回用户信息

#### 3.2.2 Refresh Token 验证
1. 验证 JWT 签名和过期时间
2. 检查 Redis 中的 token 记录
3. 检查是否已被撤销
4. 检查 token 家族完整性（防止重放）
5. 如果检测到重用，撤销整个家族
6. 生成新的 token 对并轮换

### 3.3 Token 撤销机制

#### 3.3.1 单个 Token 撤销
- 将 token JTI 加入黑名单
- 从用户会话列表中移除
- 设置适当的 TTL

#### 3.3.2 用户所有 Token 撤销
- 获取用户所有会话
- 批量撤销所有 access 和 refresh token
- 清空用户会话索引

#### 3.3.3 Token 家族撤销（检测到重放攻击）
- 撤销同一家族的所有 token
- 记录安全事件
- 可选：通知用户

---

## 4. 实现细节

### 4.1 新增文件结构

```
backend/app/
├── services/
│   ├── jwt_auth_service.py          # 现有文件，需要修改
│   └── token_redis_service.py       # 新增：Token Redis 服务
├── schemas/
│   └── token.py                     # 新增：Token 相关 Schema
├── api/
│   ├── auth_routes.py               # 现有文件，需要修改
│   └── v1/
│       └── session_routes.py        # 新增：会话管理路由
└── jwt_auth.py                      # 现有文件，需要修改
```

### 4.2 核心服务实现

#### 4.2.1 `token_redis_service.py` - 主要方法

```python
class TokenRedisService:
    """Token Redis 存储服务"""
    
    async def store_access_token(...)
        # 存储 access token 到 Redis
    
    async def store_refresh_token(...)
        # 存储 refresh token 到 Redis
    
    async def verify_access_token(...)
        # 验证 access token 是否有效
    
    async def verify_refresh_token(...)
        # 验证 refresh token 是否有效
    
    async def revoke_token(...)
        # 撤销单个 token
    
    async def revoke_user_tokens(...)
        # 撤销用户所有 token
    
    async def revoke_token_family(...)
        # 撤销 token 家族（检测到重放攻击）
    
    async def get_user_sessions(...)
        # 获取用户所有活跃会话
    
    async def is_token_blacklisted(...)
        # 检查 token 是否在黑名单中
```

#### 4.2.2 修改 `jwt_auth_service.py` - 新增功能

```python
def create_access_token_with_jti(data, expires_delta=None):
    """创建带 JTI 的 access token，返回 (token, jti)"""
    
def create_refresh_token_with_jti(data, family_id=None):
    """创建带 JTI 的 refresh token，返回 (token, jti, family_id)"""
    
def extract_jti_from_token(token):
    """从 token 中提取 JTI"""
```

### 4.3 API 路由修改

#### 4.3.1 修改 `auth_routes.py` - 主要端点

```python
@router.post("/login")
async def login(...):
    """
    用户登录并获取JWT令牌
    - 生成带 JTI 的 token
    - 存储到 Redis
    - 记录设备信息
    """

@router.post("/logout")
async def logout(...):
    """
    用户登出
    - 提取当前 token 的 JTI
    - 将 token 加入黑名单
    - 从用户会话中移除
    """

@router.post("/logout-all")
async def logout_all(...):
    """
    登出所有设备
    - 撤销用户所有 token
    - 清空所有会话
    """

@router.post("/refresh")
async def refresh_token(...):
    """
    使用刷新令牌获取新的访问令牌
    - 验证 refresh token
    - 检测 token 重用
    - 生成新 token 对并轮换
    - 更新 Redis 存储
    """
```

#### 4.3.2 新增 `session_routes.py` - 会话管理

```python
@router.get("/sessions")
async def list_sessions(...):
    """获取当前用户所有活跃会话"""

@router.delete("/sessions/{session_id}")
async def revoke_session(...):
    """撤销指定会话"""
```

### 4.4 中间件修改

#### 4.4.1 修改 `jwt_auth.py` - 集成 Redis 验证

```python
async def require_jwt_token(
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis)  # 新增 Redis 依赖
) -> AuthenticatedUser:
    """
    验证JWT访问令牌并返回已认证的用户
    - 验证 JWT 签名
    - 检查 Redis 中的 token 状态
    - 检查黑名单
    - 验证用户状态
    """
```

---

## 5. Schema 定义

### 5.1 `schemas/token.py` - 数据模型

```python
class DeviceInfo(BaseModel):
    """设备信息"""
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

class TokenRecord(BaseModel):
    """Token 记录"""
    token_id: str
    user_id: str
    token_type: str
    jti: str
    issued_at: datetime
    expires_at: datetime
    device_info: Optional[DeviceInfo] = None
    family_id: Optional[str] = None
    parent_jti: Optional[str] = None
    revoked: bool = False

class TokenBlacklistEntry(BaseModel):
    """黑名单条目"""
    jti: str
    user_id: str
    revoked_at: datetime
    reason: str

class UserSession(BaseModel):
    """用户会话"""
    session_id: str
    refresh_token_jti: str
    created_at: datetime
    last_used_at: datetime
    device_info: Optional[DeviceInfo] = None

class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str
    created_at: datetime
    last_used_at: datetime
    device_info: Optional[DeviceInfo] = None
    is_current: bool
```

---

## 6. 测试计划

### 6.1 单元测试

#### 6.1.1 `test_token_redis_service.py`
- 测试 token 存储
- 测试 token 验证
- 测试 token 撤销
- 测试黑名单检查
- 测试用户会话管理
- 测试 token 家族撤销

#### 6.1.2 `test_jwt_auth_with_redis.py`
- 测试登录流程（含 Redis 存储）
- 测试登出流程（含黑名单）
- 测试 token 验证（含 Redis 检查）
- 测试 refresh token 轮换
- 测试 token 重用检测

### 6.2 集成测试

#### 6.2.1 `test_auth_flow_integration.py`
- 完整登录-使用-登出流程
- Token 刷新流程
- 多设备登录场景
- Token 重放攻击防护
- 会话管理功能

### 6.3 性能测试
- Redis 读写性能
- 并发 token 验证
- 大量会话管理

---

## 7. 安全考虑

### 7.1 Token 安全
- 使用 JTI 防止 token 重放
- Refresh token 家族追踪防止重用
- Token 黑名单机制
- 设备指纹记录

### 7.2 Redis 安全
- 敏感数据不存储明文 token
- 适当的 TTL 设置
- Redis 连接加密（生产环境）

### 7.3 API 安全
- 速率限制（防止暴力破解）
- 日志记录（安全事件）
- 异常设备检测

---

## 8. 性能优化

### 8.1 Redis 优化
- 使用 Pipeline 批量操作
- 合理设置 TTL 避免内存泄漏
- 使用 Redis 集群（高可用）

### 8.2 缓存策略
- Token 验证结果短期缓存（可选）
- 用户会话列表缓存

### 8.3 监控指标
- Token 生成/验证速率
- Redis 命中率
- 黑名单大小
- 活跃会话数

---

## 9. 部署和迁移

### 9.1 向后兼容
- 保持现有 JWT 验证逻辑作为降级方案
- 渐进式启用 Redis 验证
- 配置开关控制功能启用

### 9.2 数据迁移
- 无需迁移（新功能）
- 现有用户下次登录时自动启用

### 9.3 配置项
```python
# settings.py 新增配置
ENABLE_TOKEN_REDIS_STORAGE: bool = True
ENABLE_TOKEN_ROTATION: bool = True
ENABLE_DEVICE_TRACKING: bool = True
MAX_SESSIONS_PER_USER: int = 5
```

---

## 10. 文档更新

### 10.1 API 文档
- 更新 `/auth/login` 说明
- 更新 `/auth/logout` 说明
- 新增 `/auth/logout-all` 文档
- 新增 `/auth/refresh` 详细说明
- 新增 `/v1/sessions` 端点文档

### 10.2 开发文档
- Token 生命周期说明
- Redis 键结构文档
- 安全最佳实践
- 故障排查指南

---

## 11. 实施时间表

### Phase 1: 基础设施（2-3天）
- 设计 Redis 数据模型
- 实现 `token_redis_service.py`
- 添加 Schema 定义
- 单元测试

### Phase 2: 核心功能（3-4天）
- 修改登录/登出逻辑
- 实现 token 验证中间件
- 实现 refresh token 轮换
- 集成测试

### Phase 3: 高级功能（2-3天）
- 会话管理 API
- Token 家族追踪
- 设备信息记录
- 安全事件日志

### Phase 4: 优化和文档（1-2天）
- 性能优化
- 更新 API 文档
- 编写使用指南
- 代码审查

**总计：8-12 天**

---

## 12. 风险和挑战

### 12.1 技术风险
- Redis 单点故障 → 使用 Redis 集群
- 性能瓶颈 → 优化查询和缓存
- 数据一致性 → 使用事务和锁

### 12.2 业务风险
- 用户体验影响 → 保持向后兼容
- 现有集成破坏 → 充分测试
- 安全漏洞 → 安全审计

---

## 13. 成功标准

### 13.1 功能完整性
- 所有 token 存储到 Redis
- Token 可以被主动撤销
- Refresh token 安全轮换
- 用户可以管理会话

### 13.2 性能指标
- Token 验证延迟 < 50ms
- Redis 命中率 > 95%
- 支持 1000+ 并发验证

### 13.3 安全指标
- 无 token 重放攻击
- 检测并阻止异常行为
- 完整的审计日志

---

## 附录

### A. 相关文件清单
- `backend/app/services/jwt_auth_service.py`
- `backend/app/services/token_redis_service.py` (新增)
- `backend/app/schemas/token.py` (新增)
- `backend/app/api/auth_routes.py`
- `backend/app/api/v1/session_routes.py` (新增)
- `backend/app/jwt_auth.py`
- `backend/app/redis_client.py`
- `backend/app/storage/redis_service.py`

### B. 参考资料
- RFC 7519 - JSON Web Token (JWT)
- OWASP JWT Security Cheat Sheet
- Redis Best Practices
- 项目现有文档：`docs/backend/session-context-design.md`