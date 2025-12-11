# 前端认证架构图

## 系统架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端应用 (Next.js)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   UI 组件     │      │  Zustand     │      │   Axios      │  │
│  │              │◄────►│   Store      │◄────►│   Client     │  │
│  │ - AuthDialog │      │              │      │              │  │
│  │ - UserMenu   │      │ - user       │      │ - 拦截器     │  │
│  │ - withAuth   │      │ - login()    │      │ - 自动刷新   │  │
│  └──────────────┘      │ - logout()   │      └──────────────┘  │
│                        │ - checkAuth()│              │          │
│                        └──────────────┘              │          │
│                               │                      │          │
│  ┌────────────────────────────┼──────────────────────┘          │
│  │                            │                                 │
│  │  ┌─────────────────────────▼──────────────────────┐         │
│  │  │          Token Manager                          │         │
│  │  │  ┌──────────────┐      ┌──────────────┐       │         │
│  │  │  │ localStorage │      │   Cookies    │       │         │
│  │  │  │              │      │              │       │         │
│  │  │  │ access_token │      │refresh_token │       │         │
│  │  │  │   (1小时)    │      │   (7天)      │       │         │
│  │  │  └──────────────┘      └──────────────┘       │         │
│  │  └─────────────────────────────────────────────────┘         │
│  │                                                               │
└──┼───────────────────────────────────────────────────────────────┘
   │
   │ HTTP/HTTPS
   │
   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      后端 API (FastAPI)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  POST /auth/register    - 用户注册                               │
│  POST /auth/login       - 用户登录                               │
│  POST /auth/refresh     - 刷新令牌                               │
│  GET  /auth/me          - 获取当前用户                           │
│  POST /auth/logout      - 用户登出                               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 认证流程详解

### 1. 用户注册流程

```
用户 → AuthDialog → Zustand Store → Axios → API
                                              │
                                              ▼
                                         创建用户
                                              │
                                              ▼
                                         自动登录
                                              │
                                              ▼
                                    返回 access_token
                                    返回 refresh_token
                                              │
                                              ▼
                                    存储到 localStorage
                                    存储到 Cookies
                                              │
                                              ▼
                                    跳转到 Dashboard
```

### 2. 用户登录流程

```
┌──────┐
│ 用户 │
└──┬───┘
   │ 1. 输入用户名/密码
   ▼
┌────────────┐
│ AuthDialog │
└──┬─────────┘
   │ 2. 表单验证
   ▼
┌──────────────┐
│ Zustand Store│
│  login()     │
└──┬───────────┘
   │ 3. 调用 API
   ▼
┌──────────────┐
│ Axios Client │
└──┬───────────┘
   │ 4. POST /auth/login
   ▼
┌──────────────┐
│  Backend API │
└──┬───────────┘
   │ 5. 验证凭据
   │ 6. 生成 tokens
   ▼
┌──────────────────────────┐
│ Response:                │
│ - access_token (1小时)   │
│ - refresh_token (7天)    │
│ - token_type: "bearer"   │
│ - expires_in: 3600       │
└──┬───────────────────────┘
   │ 7. 返回响应
   ▼
┌──────────────┐
│ Token Manager│
└──┬───────────┘
   │ 8. 存储 tokens
   │    - localStorage: access_token
   │    - Cookies: refresh_token
   ▼
┌──────────────┐
│ Axios Client │
└──┬───────────┘
   │ 9. GET /auth/me
   ▼
┌──────────────┐
│  Backend API │
└──┬───────────┘
   │ 10. 返回用户信息
   ▼
┌──────────────┐
│ Zustand Store│
│  setUser()   │
└──┬───────────┘
   │ 11. 更新状态
   │     - user: UserInfo
   │     - isAuthenticated: true
   ▼
┌──────────────┐
│   Router     │
│ push('/dashboard')
└──────────────┘
```

### 3. Token 自动刷新流程

```
┌──────────────┐
│  用户操作    │
│ (访问页面)   │
└──┬───────────┘
   │ 1. 发起 API 请求
   ▼
┌──────────────┐
│ Axios Client │
│ 请求拦截器   │
└──┬───────────┘
   │ 2. 添加 Authorization 头
   │    Bearer {access_token}
   ▼
┌──────────────┐
│  Backend API │
└──┬───────────┘
   │ 3. 验证 token
   │
   ├─ Token 有效 ──────────────┐
   │                            │
   │                            ▼
   │                     ┌──────────────┐
   │                     │ 返回数据     │
   │                     └──────────────┘
   │
   └─ Token 过期 (401) ────────┐
                                │
                                ▼
                         ┌──────────────┐
                         │ Axios Client │
                         │ 响应拦截器   │
                         └──┬───────────┘
                            │ 4. 检测 401
                            │
                            ├─ 正在刷新? ──► 加入队列等待
                            │
                            └─ 未刷新 ────┐
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │ 设置刷新标志 │
                                   │isRefreshing=true
                                   └──┬───────────┘
                                      │ 5. 获取 refresh_token
                                      ▼
                                   ┌──────────────┐
                                   │ Token Manager│
                                   └──┬───────────┘
                                      │ 6. 从 Cookies 读取
                                      ▼
                                   ┌──────────────┐
                                   │ POST /auth/  │
                                   │    refresh   │
                                   └──┬───────────┘
                                      │
                                      ├─ 刷新成功 ──┐
                                      │             │
                                      │             ▼
                                      │      ┌──────────────┐
                                      │      │ 更新 tokens  │
                                      │      │ 处理队列请求 │
                                      │      │ 重试原请求   │
                                      │      └──────────────┘
                                      │
                                      └─ 刷新失败 ──┐
                                                    │
                                                    ▼
                                             ┌──────────────┐
                                             │ 清除 tokens  │
                                             │ 跳转登录页   │
                                             └──────────────┘
```

### 4. 受保护路由访问流程

```
┌──────────────┐
│  用户访问    │
│ /dashboard   │
└──┬───────────┘
   │
   ▼
┌──────────────┐
│  withAuth    │
│     HOC      │
└──┬───────────┘
   │ 1. 检查认证状态
   ▼
┌──────────────┐
│ Zustand Store│
│  checkAuth() │
└──┬───────────┘
   │ 2. 获取 access_token
   ▼
┌──────────────┐
│ Token Manager│
└──┬───────────┘
   │
   ├─ Token 存在 ──────────┐
   │                        │
   │                        ▼
   │                 ┌──────────────┐
   │                 │ GET /auth/me │
   │                 └──┬───────────┘
   │                    │
   │                    ├─ 成功 ──► 渲染页面
   │                    │
   │                    └─ 失败 ──► 清除 token
   │                                跳转登录
   │
   └─ Token 不存在 ────┐
                       │
                       ▼
                ┌──────────────┐
                │ 跳转登录页   │
                └──────────────┘
```

### 5. 用户登出流程

```
┌──────────────┐
│  用户点击    │
│   登出按钮   │
└──┬───────────┘
   │
   ▼
┌──────────────┐
│  UserMenu    │
└──┬───────────┘
   │ 1. 调用 logout()
   ▼
┌──────────────┐
│ Zustand Store│
│  logout()    │
└──┬───────────┘
   │ 2. 调用 API
   ▼
┌──────────────┐
│ Axios Client │
└──┬───────────┘
   │ 3. POST /auth/logout
   ▼
┌──────────────┐
│  Backend API │
└──┬───────────┘
   │ 4. 清理服务端会话
   │    (可选)
   ▼
┌──────────────┐
│ Token Manager│
└──┬───────────┘
   │ 5. 清除所有 tokens
   │    - localStorage.clear()
   │    - Cookies.remove()
   ▼
┌──────────────┐
│ Zustand Store│
└──┬───────────┘
   │ 6. 重置状态
   │    - user: null
   │    - isAuthenticated: false
   ▼
┌──────────────┐
│   Router     │
│ push('/login')
└──────────────┘
```

## 数据存储策略

### Access Token (localStorage)

```
┌─────────────────────────────────────┐
│         localStorage                │
├─────────────────────────────────────┤
│ Key: "access_token"                 │
│ Value: "eyJhbGciOiJIUzI1NiIs..."   │
│ 有效期: 1小时                        │
│ 用途: API 请求认证                   │
│ 安全性: 可被 JavaScript 访问         │
└─────────────────────────────────────┘
```

### Refresh Token (Cookies)

```
┌─────────────────────────────────────┐
│           Cookies                   │
├─────────────────────────────────────┤
│ Name: "refresh_token"               │
│ Value: "eyJhbGciOiJIUzI1NiIs..."   │
│ Expires: 7天                        │
│ HttpOnly: false (前端设置)          │
│ Secure: true (生产环境)             │
│ SameSite: Strict                    │
│ Path: /                             │
│ 用途: 刷新 access_token             │
└─────────────────────────────────────┘
```

### User Info (Zustand Store - 内存)

```
┌─────────────────────────────────────┐
│       Zustand Store (内存)          │
├─────────────────────────────────────┤
│ user: {                             │
│   id: "uuid",                       │
│   username: "string",               │
│   email: "string",                  │
│   display_name: "string | null",    │
│   avatar: "string | null",          │
│   is_superuser: boolean,            │
│   role_codes: ["default_user"]      │
│ }                                   │
│ isAuthenticated: boolean            │
│ isLoading: boolean                  │
└─────────────────────────────────────┘
```

## 安全机制

### 1. XSS 防护

```
┌─────────────────────────────────────┐
│  Refresh Token 存储在 Cookie        │
│  (虽然不是 httpOnly，但相对安全)    │
├─────────────────────────────────────┤
│  Access Token 短期有效 (1小时)      │
│  即使被窃取，影响有限                │
├─────────────────────────────────────┤
│  所有用户输入都经过验证和转义        │
│  使用 Zod schema 验证                │
└─────────────────────────────────────┘
```

### 2. CSRF 防护

```
┌─────────────────────────────────────┐
│  使用 Bearer Token 认证             │
│  不依赖 Cookie 进行身份验证          │
├─────────────────────────────────────┤
│  Cookie 设置 SameSite=Strict        │
│  防止跨站请求                        │
└─────────────────────────────────────┘
```

### 3. Token 过期策略

```
Access Token (短期)
├─ 有效期: 1小时
├─ 用途: 日常 API 请求
└─ 过期处理: 自动刷新

Refresh Token (长期)
├─ 有效期: 7天
├─ 用途: 获取新的 access_token
└─ 过期处理: 重新登录
```

## 组件依赖关系

```
┌─────────────────────────────────────────────────────────┐
│                    App Layout                           │
│  ┌───────────────────────────────────────────────────┐ │
│  │  useEffect(() => checkAuth())                     │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Top Navigation                        │
│  ┌───────────────────────────────────────────────────┐ │
│  │  isAuthenticated ? <UserMenu /> : <LoginButton /> │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
┌──────────────────┐           ┌──────────────────┐
│    UserMenu      │           │   LoginButton    │
│  ┌────────────┐  │           │  ┌────────────┐  │
│  │ - Profile  │  │           │  │ onClick    │  │
│  │ - Settings │  │           │  │ → /login   │  │
│  │ - Logout   │  │           │  └────────────┘  │
│  └────────────┘  │           └──────────────────┘
└──────────────────┘
          │
          ▼
┌──────────────────┐
│  logout()        │
│  ┌────────────┐  │
│  │ Clear      │  │
│  │ Tokens     │  │
│  │ → /login   │  │
│  └────────────┘  │
└──────────────────┘
```

## 文件结构

```
frontend/
├── lib/
│   ├── auth/
│   │   ├── token-manager.ts      # Token 管理工具
│   │   └── with-auth.tsx          # 受保护路由 HOC
│   └── stores/
│       └── auth-store.ts          # Zustand 认证状态
├── http/
│   ├── client.ts                  # Axios 客户端 (含自动刷新)
│   └── auth.ts                    # 认证 API 服务
├── components/
│   ├── auth/
│   │   └── auth-dialog.tsx        # 登录/注册对话框
│   ├── layout/
│   │   ├── top-nav.tsx            # 顶部导航 (含用户菜单)
│   │   └── user-menu.tsx          # 用户下拉菜单
│   └── forms/
│       └── form-input.tsx         # 表单输入组件
└── app/
    ├── layout.tsx                 # 根布局 (检查认证)
    ├── (auth)/
    │   └── login/
    │       └── page.tsx           # 登录页面
    ├── dashboard/
    │   └── layout.tsx             # Dashboard 布局 (受保护)
    ├── profile/
    │   └── layout.tsx             # Profile 布局 (受保护)
    └── system/
        └── layout.tsx             # System 布局 (受保护)
```

## 关键技术点

### 1. 防止并发刷新

```typescript
let isRefreshing = false;
let failedQueue: Array<{resolve, reject}> = [];

// 当检测到 401 时
if (isRefreshing) {
  // 将请求加入队列
  return new Promise((resolve, reject) => {
    failedQueue.push({resolve, reject});
  });
}

// 刷新完成后处理队列
processQueue(null, newToken);
```

### 2. 状态持久化

```typescript
// 页面加载时检查认证状态
useEffect(() => {
  checkAuth();
}, []);

// checkAuth 实现
const checkAuth = async () => {
  const token = tokenManager.getAccessToken();
  if (token) {
    try {
      const user = await authService.getCurrentUser();
      setUser(user);
    } catch {
      tokenManager.clearAll();
    }
  }
};
```

### 3. 表单验证

```typescript
// 使用 Zod + React Hook Form
const schema = z.object({
  username: z.string().min(3).max(50),
  password: z.string().min(6).max(128),
});

const form = useForm({
  resolver: zodResolver(schema),
});
```

## 总结

这个认证架构提供了：

✅ **安全性**: Token 分离存储，自动刷新机制
✅ **用户体验**: 无感刷新，持久化登录状态
✅ **可维护性**: 清晰的职责分离，模块化设计
✅ **可扩展性**: 易于添加新的认证方式（OAuth等）
✅ **错误处理**: 完善的错误提示和恢复机制

---

**相关文档**:
- [前端认证集成方案](./frontend-auth-integration-plan.md)
- [前端认证实施清单](./frontend-auth-implementation-checklist.md)
- [API 文档](./API_Documentation.md)