# OAuth 登录功能设置总结

## 已创建的文件

### 1. 前端核心文件

#### 回调页面
- **文件**: `frontend/app/(auth)/callback/page.tsx`
- **功能**: 处理 OAuth 提供商的回调，验证授权码，存储 token，跳转到目标页面
- **路由**: `/callback`

#### OAuth 重定向管理
- **文件**: `frontend/lib/auth/oauth-redirect.ts`
- **功能**: 管理 OAuth 登录流程中的重定向地址
- **API**:
  - `save(url?)`: 保存重定向地址
  - `get()`: 获取保存的地址
  - `clear()`: 清除保存的地址
  - `getAndClear(defaultUrl)`: 获取并清除

#### OAuth 登录按钮组件
- **文件**: `frontend/components/auth/oauth-buttons.tsx`
- **功能**: 可复用的 OAuth 登录按钮组件（Google、GitHub、Microsoft）
- **Props**:
  - `redirectUrl?`: 登录成功后的跳转地址
  - `showDivider?`: 是否显示分隔线

### 2. 国际化文案

#### 更新的文件
- **文件**: `frontend/lib/i18n/auth.ts`
- **新增文案**:
  - `auth.oauth_processing`: "正在处理 OAuth 登录..."
  - `auth.oauth_success`: "登录成功！"
  - `auth.oauth_failed`: "OAuth 登录失败"
  - `auth.oauth_redirecting`: "正在跳转到仪表盘..."
  - `auth.oauth_redirect_login`: "正在跳转到登录页..."
  - `auth.oauth_provider_error`: "OAuth 提供商返回错误"
  - `auth.oauth_missing_code`: "缺少授权码"
  - `auth.oauth_divider`: "或使用以下方式继续"
  - `auth.oauth_google`: "使用 Google 继续"
  - `auth.oauth_github`: "使用 GitHub 继续"
  - `auth.oauth_microsoft`: "使用 Microsoft 继续"

### 3. 文档

#### 集成指南
- **文件**: `docs/frontend/oauth-integration.md`
- **内容**:
  - OAuth 登录流程说明
  - 后端 API 要求
  - 重定向地址管理
  - 错误处理
  - 安全考虑
  - 配置示例
  - 常见问题

#### 集成示例
- **文件**: `docs/frontend/oauth-integration-example.md`
- **内容**:
  - 在登录对话框中集成 OAuth 按钮
  - 创建独立的 OAuth 登录页面
  - 在任意页面添加 OAuth 登录
  - 自定义 OAuth 按钮样式
  - 处理 OAuth 错误
  - 测试和调试技巧

## OAuth 登录流程

```
用户点击 OAuth 按钮
    ↓
保存重定向地址 (oauthRedirect.save)
    ↓
跳转到后端授权端点 (/api/auth/oauth/{provider}/authorize)
    ↓
后端重定向到 OAuth 提供商
    ↓
用户授权
    ↓
OAuth 提供商回调 (/callback?code=xxx&state=xxx)
    ↓
前端回调页面处理
    ↓
调用后端验证 API (/auth/oauth/callback)
    ↓
存储 access_token 和 refresh_token
    ↓
更新用户状态
    ↓
跳转到保存的重定向地址或 /dashboard
```

## 后端需要实现的 API

### 1. OAuth 授权端点

```
GET /api/auth/oauth/{provider}/authorize
```

**功能**:
- 生成 state 参数（防 CSRF）
- 构建 OAuth 授权 URL
- 设置回调地址为前端的 `/callback` 路由
- 重定向用户到 OAuth 提供商

**支持的 provider**:
- `google`
- `github`
- `microsoft`

### 2. OAuth 回调验证端点

```
POST /auth/oauth/callback
Content-Type: application/json

{
  "code": "authorization_code",
  "state": "state_value"
}
```

**响应**:
```json
{
  "access_token": "xxx",
  "refresh_token": "xxx",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "User Name",
    "is_active": true
  }
}
```

## 使用方法

### 方法 1：在现有登录对话框中添加

在 `frontend/components/auth/auth-dialog.tsx` 中导入并使用：

```tsx
import { OAuthButtons } from "@/components/auth/oauth-buttons";

// 在 DialogContent 中添加
<OAuthButtons redirectUrl={redirectTo} />
```

### 方法 2：创建独立的 OAuth 登录页面

```tsx
import { OAuthButtons } from "@/components/auth/oauth-buttons";

export default function OAuthLoginPage() {
  return (
    <div className="container">
      <OAuthButtons showDivider={false} />
    </div>
  );
}
```

### 方法 3：在任意位置添加单个按钮

```tsx
import { oauthRedirect } from "@/lib/auth/oauth-redirect";

function MyComponent() {
  const handleGoogleLogin = () => {
    oauthRedirect.save("/my-target-page");
    window.location.href = "/api/auth/oauth/google/authorize";
  };

  return <button onClick={handleGoogleLogin}>Google 登录</button>;
}
```

## 配置要求

### 前端环境变量

```env
# .env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### 后端环境变量

```env
# .env
OAUTH_CALLBACK_URL=http://localhost:3000/callback

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret

# GitHub OAuth
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret

# Microsoft OAuth
MICROSOFT_CLIENT_ID=your_client_id
MICROSOFT_CLIENT_SECRET=your_client_secret
```

### OAuth 提供商配置

在各 OAuth 提供商的开发者控制台中配置回调地址：

- **开发环境**: `http://localhost:3000/callback`
- **生产环境**: `https://yourdomain.com/callback`

## 安全注意事项

1. **State 参数**: 后端必须验证 state 参数，防止 CSRF 攻击
2. **HTTPS**: 生产环境必须使用 HTTPS
3. **Token 存储**: 
   - access_token 存储在 localStorage/sessionStorage
   - refresh_token 存储在 HttpOnly Cookie
4. **回调地址验证**: 后端应验证回调地址在白名单中
5. **Token 过期**: 实现 token 自动刷新机制

## 测试清单

- [ ] 点击 OAuth 按钮能正确跳转到授权页面
- [ ] 授权后能正确回调到 `/callback` 页面
- [ ] 回调页面能正确处理授权码
- [ ] Token 能正确存储
- [ ] 用户状态能正确更新
- [ ] 能正确跳转到目标页面
- [ ] 错误情况能正确处理和显示
- [ ] 取消授权能正确返回登录页
- [ ] 多个 OAuth 提供商都能正常工作
- [ ] 重定向地址保存和恢复正常

## 下一步

1. **实现后端 API**: 根据上述要求实现后端的 OAuth 授权和回调端点
2. **配置 OAuth 提供商**: 在各提供商的开发者控制台注册应用并获取凭证
3. **集成到登录页面**: 在现有登录对话框中添加 OAuth 按钮
4. **测试**: 完整测试 OAuth 登录流程
5. **更新 API 文档**: 在 `docs/api/` 中添加 OAuth API 文档

## 相关文档

- [OAuth 集成指南](./oauth-integration.md)
- [OAuth 集成示例](./oauth-integration-example.md)
- [认证错误处理](./auth-error-handling.md)
