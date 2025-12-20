# Token 存储迁移指南

## 🎯 迁移目标

将 `access_token` 从 **localStorage/sessionStorage** 迁移到 **Cookie**，以支持服务端预取（SSR）。

## 📋 变更说明

### 之前（旧方案）
```
access_token → localStorage/sessionStorage
refresh_token → HttpOnly Cookie（后端设置）
```

**问题**：
- ❌ 服务端无法读取 localStorage/sessionStorage
- ❌ SSR 预取失败（401 错误）
- ❌ 首屏加载有闪烁

### 现在（新方案）
```
access_token → Cookie（非 HttpOnly）+ localStorage/sessionStorage（fallback）
refresh_token → HttpOnly Cookie（后端设置）
```

**优势**：
- ✅ 服务端可以读取 Cookie
- ✅ SSR 预取成功
- ✅ 首屏无闪烁
- ✅ 向后兼容（保留 localStorage fallback）

## 🔧 前端改动

### 1. Token Manager 更新

`frontend/lib/auth/token-manager.ts` 已更新：

```typescript
// 设置 token 时，同时写入 Cookie 和 localStorage
tokenManager.setAccessToken(token, { remember: true });

// 读取 token 时，优先从 Cookie 读取
const token = tokenManager.getAccessToken();
```

**Cookie 配置**：
- `expires`: remember ? 7天 : session
- `secure`: production 环境启用
- `sameSite`: 'strict'
- `httpOnly`: false（允许客户端 JS 读取）

### 2. 客户端请求（无需改动）

现有的 axios/fetch 请求代码**无需改动**，因为：
- `tokenManager.getAccessToken()` 会自动从 Cookie 读取
- 请求拦截器继续从 tokenManager 获取 token
- 向后兼容 localStorage 中的旧 token

### 3. 服务端预取（已支持）

`serverFetch` 现在可以从 Cookie 读取 token：

```typescript
// frontend/lib/swr/server-fetch.ts
const cookieStore = await cookies();
const token = cookieStore.get('access_token')?.value;
```

## 🔐 安全性说明

### Cookie 安全配置

```typescript
Cookies.set('access_token', token, {
  secure: true,        // HTTPS only (生产环境)
  sameSite: 'strict',  // 防止 CSRF
  path: '/',           // 全站可用
  httpOnly: false,     // 允许 JS 读取（SSR 需要）
});
```

### 为什么不用 HttpOnly？

**HttpOnly Cookie 的限制**：
- ✅ 更安全（防止 XSS 窃取）
- ❌ 客户端 JS 无法读取
- ❌ 无法在 Authorization Header 中使用
- ❌ 需要后端支持从 Cookie 读取 token

**我们的方案**：
- access_token 在 Cookie（非 HttpOnly）
  - 服务端可读（SSR）
  - 客户端可读（axios）
  - 放在 Authorization Header（标准做法）
- refresh_token 在 HttpOnly Cookie
  - 更安全（长期有效）
  - 只在刷新时使用

### XSS 防护

虽然 access_token 不是 HttpOnly，但我们有其他防护：
1. **短期有效**：access_token 通常 15-30 分钟过期
2. **CSP 策略**：Content Security Policy 防止脚本注入
3. **输入验证**：所有用户输入都经过验证和转义
4. **HTTPS Only**：生产环境强制 HTTPS

## 🚀 部署步骤

### 1. 前端部署

```bash
# 1. 更新代码
git pull origin main

# 2. 安装依赖（如果有新增）
npm install

# 3. 构建
npm run build

# 4. 部署
npm run start
```

### 2. 用户迁移（自动）

**首次登录后自动迁移**：
1. 用户登录成功
2. `tokenManager.setAccessToken()` 同时写入 Cookie 和 localStorage
3. 下次访问时，优先从 Cookie 读取
4. localStorage 中的旧 token 作为 fallback

**无需手动操作**：
- 已登录用户：下次刷新页面时自动迁移
- 新用户：直接使用新方案

### 3. 验证迁移

**检查 Cookie**：
```javascript
// 浏览器控制台
document.cookie.includes('access_token')
// 应该返回 true
```

**检查 SSR 预取**：
```bash
# 查看服务端日志
# 应该看到成功的预取请求，而不是 401 错误
```

## 🔄 回滚方案

如果需要回滚到旧方案：

1. **恢复 token-manager.ts**：
```bash
git revert <commit-hash>
```

2. **清除用户 Cookie**：
```javascript
// 在浏览器控制台执行
document.cookie = 'access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
```

3. **用户重新登录**：
- Token 会重新存储到 localStorage
- 服务端预取会失败（返回 null）
- 客户端会重新请求（正常工作）

## 📊 监控指标

### 成功指标

1. **SSR 预取成功率**：
   - 监控服务端日志中的 401 错误
   - 目标：< 5%（仅未登录用户）

2. **首屏加载时间**：
   - 监控 FCP/LCP 指标
   - 目标：减少 20-30%

3. **用户体验**：
   - 监控页面闪烁投诉
   - 目标：0 投诉

### 问题排查

**问题 1：Cookie 未设置**
```javascript
// 检查
console.log(document.cookie);

// 原因可能是：
// 1. 登录接口未调用 tokenManager.setAccessToken
// 2. Cookie 被浏览器阻止（第三方 Cookie 设置）
// 3. Domain/Path 配置错误
```

**问题 2：服务端读取不到 Cookie**
```typescript
// 检查 Next.js 服务端日志
const cookieStore = await cookies();
console.log('Cookies:', cookieStore.getAll());

// 原因可能是：
// 1. Cookie 的 Path 不匹配
// 2. Cookie 的 Domain 不匹配
// 3. Cookie 已过期
```

**问题 3：客户端请求失败**
```javascript
// 检查 tokenManager
const token = tokenManager.getAccessToken();
console.log('Token:', token);

// 原因可能是：
// 1. Cookie 和 localStorage 都没有 token
// 2. Token 已过期
// 3. Token 格式错误
```

## 📝 后续优化

### 1. 后端支持从 Cookie 读取（可选）

如果后端也支持从 Cookie 读取 token，可以进一步简化：

```python
# Python/FastAPI 示例
def get_current_user(
    authorization: str = Header(None),
    access_token: str = Cookie(None)
):
    # 优先从 Header 读取
    token = None
    if authorization and authorization.startswith('Bearer '):
        token = authorization[7:]
    # Fallback 到 Cookie
    elif access_token:
        token = access_token
    
    if not token:
        raise HTTPException(401, "Not authenticated")
    
    return verify_token(token)
```

**优势**：
- 客户端可以不用手动添加 Authorization Header
- 浏览器自动携带 Cookie
- 更符合传统 Web 应用的做法

### 2. Token 刷新优化

考虑在服务端预取时自动刷新即将过期的 token：

```typescript
// server-fetch.ts
if (token && isTokenExpiringSoon(token)) {
  const newToken = await refreshToken();
  // 更新 Cookie
}
```

### 3. 多域名支持

如果前后端在不同域名，需要配置 CORS 和 Cookie Domain：

```typescript
Cookies.set('access_token', token, {
  domain: '.example.com', // 主域名
  // ...
});
```

## ❓ FAQ

**Q: 为什么不直接用 HttpOnly Cookie？**
A: HttpOnly Cookie 客户端 JS 无法读取，无法放到 Authorization Header 中。除非后端支持从 Cookie 读取 token。

**Q: Cookie 和 localStorage 哪个更安全？**
A: HttpOnly Cookie > 非 HttpOnly Cookie > localStorage。但我们的 access_token 是短期的，风险可控。

**Q: 会影响现有用户吗？**
A: 不会。新方案向后兼容，会自动从 localStorage 迁移到 Cookie。

**Q: 需要清除用户缓存吗？**
A: 不需要。用户下次登录时会自动迁移。

**Q: 如果用户禁用了 Cookie 怎么办？**
A: Fallback 到 localStorage，但服务端预取会失败（客户端仍然正常工作）。
