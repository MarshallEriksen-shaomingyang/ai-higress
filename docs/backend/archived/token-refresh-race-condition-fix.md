# Token 刷新竞态条件修复总结

## 问题描述

在高频刷新场景下，出现"重复刷新时有些 API 认证成功、有些失败"的问题。

## 根本原因分析

### 1. Token 存储策略不当（主要原因）
- **问题**：Access token 同时存储在 localStorage 和 Cookie 中
- **影响**：两个存储位置可能出现短暂不同步，导致不同请求使用不同版本的 token
- **违反最佳实践**：标准做法应该是 access_token 仅存 localStorage，refresh_token 仅存 HttpOnly Cookie

### 2. Token 刷新的竞态条件
- **问题**：多个并发请求同时遇到 401 错误时
  - 第一个请求开始刷新 token
  - 其他请求被加入队列，但可能在刷新完成前就使用旧 token 发出
- **影响**：部分请求使用旧 token 失败

### 3. 后端立即撤销旧 Token
- **问题**：刷新 token 后立即撤销旧 token
- **影响**：前端可能还有使用旧 token 的飞行中请求（in-flight requests），这些请求到达后端时会因 token 已被撤销而返回 401

## 修复方案

### 1. 修正 Token 存储策略 ✅

**文件**：`frontend/lib/auth/token-manager.ts`

**修改内容**：
- Access Token 仅存储在 localStorage（移除 Cookie 存储）
- Refresh Token 保持仅存储在 Cookie（已正确）

```typescript
// 修改前：同时存储在 localStorage 和 Cookie
setAccessToken: (token: string) => {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
  Cookies.set(ACCESS_TOKEN_KEY, token, { ... }); // ❌ 不应该存储在 Cookie
}

// 修改后：仅存储在 localStorage
setAccessToken: (token: string) => {
  localStorage.setItem(ACCESS_TOKEN_KEY, token); // ✅ 仅 localStorage
}
```

**优势**：
- 避免双重存储的同步问题
- 符合业界最佳实践
- 提高性能（减少一次 Cookie 操作）

### 2. 优化前端 Token 刷新逻辑 ✅

**文件**：`frontend/http/client.ts`

**修改内容**：
- 使用共享的 Promise（`refreshTokenPromise`）确保只刷新一次
- 所有等待的请求都使用同一个刷新 Promise
- 避免重复刷新和竞态条件

```typescript
// 修改前：可能重复刷新
if (isRefreshing) {
  // 加入队列，但可能在刷新完成前就发出请求
  return new Promise((resolve, reject) => {
    failedQueue.push({ resolve, reject });
  }).then(token => { ... });
}

// 修改后：共享刷新 Promise
if (isRefreshing && refreshTokenPromise) {
  // 等待正在进行的刷新完成
  return refreshTokenPromise.then(token => {
    originalRequest.headers.Authorization = `Bearer ${token}`;
    return instance(originalRequest);
  });
}

// 创建共享的刷新 Promise
refreshTokenPromise = refreshAccessToken()
  .then(newToken => {
    processQueue(null, newToken);
    return newToken;
  })
  .finally(() => {
    isRefreshing = false;
    refreshTokenPromise = null;
  });
```

**优势**：
- 确保只刷新一次
- 所有等待的请求都使用新 token
- 避免竞态条件

### 3. 后端添加 Token 宽限期 ✅

**文件**：
- `backend/app/services/token_redis_service.py`
- `backend/app/api/auth_routes.py`

**修改内容**：

#### 3.1 TokenRedisService 添加宽限期支持

```python
async def revoke_token(
    self, jti: str, reason: str = "user_logout", grace_period_seconds: int = 0
) -> bool:
    """
    撤销单个 token
    
    Args:
        grace_period_seconds: 宽限期（秒），在此期间 token 仍然有效
    """
    if grace_period_seconds > 0:
        # 计算实际撤销时间
        revoke_at = now + timedelta(seconds=grace_period_seconds)
        # 存储黑名单条目，但在验证时会检查 revoked_at 时间
        ...
```

#### 3.2 修改黑名单检查逻辑

```python
async def is_token_blacklisted(self, jti: str) -> bool:
    """检查 token 是否在黑名单中"""
    data = await redis_get_json(self.redis, blacklist_key)
    
    if data is None:
        return False
    
    # 检查是否在宽限期内
    entry = TokenBlacklistEntry.model_validate(data)
    now = datetime.now(timezone.utc)
    
    # 如果撤销时间还未到，token 仍然有效
    if entry.revoked_at > now:
        return False
    
    return True
```

#### 3.3 在 Token 刷新时使用宽限期

```python
# auth_routes.py
# 撤销旧的 refresh token，添加 30 秒宽限期
await token_service.revoke_token(jti, reason="token_rotated", grace_period_seconds=30)
```

**优势**：
- 允许飞行中的请求在 30 秒内完成
- 避免因立即撤销导致的 401 错误
- 提高用户体验

## 测试建议

### 1. 单元测试
```bash
# 测试 token 刷新逻辑
pytest backend/tests/test_auth_routes.py -k refresh

# 测试 token 宽限期
pytest backend/tests/test_token_redis_service.py -k grace_period
```

### 2. 集成测试
- 模拟高并发场景：同时发送 10+ 个需要认证的请求
- 验证所有请求都能成功（不会出现部分失败）
- 测试 token 刷新时的行为

### 3. 手动测试
1. 打开浏览器开发者工具的 Network 面板
2. 快速刷新页面多次（或快速点击多个需要认证的功能）
3. 观察所有 API 请求是否都成功
4. 检查 localStorage 中的 access_token 是否正确更新

## 预期效果

修复后应该能够：
1. ✅ 消除 token 存储不一致问题
2. ✅ 避免重复刷新 token
3. ✅ 允许飞行中的请求完成
4. ✅ 提高高并发场景下的认证成功率
5. ✅ 改善用户体验（减少"会话已过期"的错误提示）

## 相关文件

### 前端
- `frontend/lib/auth/token-manager.ts` - Token 存储管理
- `frontend/http/client.ts` - HTTP 客户端和拦截器

### 后端
- `backend/app/services/token_redis_service.py` - Token Redis 服务
- `backend/app/api/auth_routes.py` - 认证路由

## 注意事项

1. **宽限期时间**：当前设置为 30 秒，可根据实际网络延迟调整
2. **安全性**：宽限期不会降低安全性，因为：
   - 旧 token 只能在短时间内使用
   - 仍然会被标记为已撤销
   - 检测到重用攻击时会立即撤销整个 token 家族
3. **向后兼容**：`grace_period_seconds` 参数默认为 0，保持原有行为

## 后续优化建议

1. 添加 token 刷新的指数退避策略
2. 监控 token 刷新的成功率和延迟
3. 考虑添加 token 预刷新机制（在过期前主动刷新）
4. 优化 Redis 存储结构以提高查询性能

---

**修复日期**：2025-12-05  
**修复人员**：AI Assistant  
**影响范围**：前端认证流程、后端 Token 管理