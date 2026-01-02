# 使用 Next.js Middleware 保护路由

## 概述

相比于 HOC（Higher-Order Component）方式，使用 Next.js Middleware 保护路由有以下优势：

1. **服务端执行**: 在请求到达页面之前就进行认证检查
2. **性能更好**: 避免客户端闪烁（未认证用户看到页面后再重定向）
3. **更简洁**: 不需要在每个页面组件中包装 HOC
4. **统一管理**: 所有路由保护逻辑集中在一个文件中

## 实施方案

### 1. 创建 Middleware 文件

**文件**: `frontend/middleware.ts`

```typescript
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const protectedRoutes = [
  '/dashboard',
  '/profile',
  '/system',
];

const publicRoutes = [
  '/login',
  '/register',
  '/',
];

function isProtectedRoute(pathname: string): boolean {
  return protectedRoutes.some(route => pathname.startsWith(route));
}

function isPublicRoute(pathname: string): boolean {
  return publicRoutes.some(route => pathname === route || pathname.startsWith(route));
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  const accessToken = request.cookies.get('access_token')?.value;
  const refreshToken = request.cookies.get('refresh_token')?.value;
  
  if (isProtectedRoute(pathname)) {
    if (!accessToken && !refreshToken) {
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('redirect', pathname);
      return NextResponse.redirect(loginUrl);
    }
    
    return NextResponse.next();
  }
  
  if (pathname === '/login' && accessToken) {
    return NextResponse.redirect(new URL('/dashboard/overview', request.url));
  }
  
  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico|.*\\..*|public).*)',
  ],
};
```

### 2. 更新 Token Manager（支持 Cookie）

**文件**: `frontend/lib/auth/token-manager.ts`

```typescript
import Cookies from 'js-cookie';

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

export const tokenManager = {
  setAccessToken: (token: string) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(ACCESS_TOKEN_KEY, token);
      
      Cookies.set(ACCESS_TOKEN_KEY, token, {
        expires: 1/24,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'strict',
        path: '/',
      });
    }
  },

  getAccessToken: (): string | null => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem(ACCESS_TOKEN_KEY);
      if (token) return token;
      
      return Cookies.get(ACCESS_TOKEN_KEY) || null;
    }
    return null;
  },

  clearAccessToken: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      Cookies.remove(ACCESS_TOKEN_KEY);
    }
  },

  setRefreshToken: (token: string) => {
    Cookies.set(REFRESH_TOKEN_KEY, token, {
      expires: 7,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      path: '/',
    });
  },

  getRefreshToken: (): string | undefined => {
    return Cookies.get(REFRESH_TOKEN_KEY);
  },

  clearRefreshToken: () => {
    Cookies.remove(REFRESH_TOKEN_KEY);
  },

  clearAll: () => {
    tokenManager.clearAccessToken();
    tokenManager.clearRefreshToken();
  },
};
```

### 3. 简化页面组件

现在页面组件不需要任何认证相关的包装：

**文件**: `frontend/app/dashboard/layout.tsx`

```typescript
export default function DashboardLayout({ 
  children 
}: { 
  children: React.ReactNode 
}) {
  return (
    <div className="dashboard-layout">
      {children}
    </div>
  );
}
```

### 4. 处理登录后重定向

**文件**: `frontend/components/auth/auth-dialog.tsx`

在登录组件中添加 redirect 参数支持：

```typescript
"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/lib/stores/auth-store";

export function AuthDialog() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get('redirect') || '/dashboard/overview';
  const { login, register: registerUser } = useAuthStore();

  const handleLogin = async (data: LoginFormData) => {
    try {
      await login(data);
      router.push(redirectTo);
    } catch (error) {
      console.error('Login error:', error);
    }
  };

  const handleRegister = async (data: RegisterFormData) => {
    try {
      const { confirmPassword, ...registerData } = data;
      await registerUser(registerData);
      router.push(redirectTo);
    } catch (error) {
      console.error('Register error:', error);
    }
  };
}
```

## 架构对比

### 使用 HOC 方式（旧）

```
用户访问 /dashboard
    ↓
Next.js 渲染页面
    ↓
withAuth HOC 执行
    ↓
检查认证状态（客户端）
    ↓
未认证 → 重定向到 /login（客户端）
    ↓
用户看到页面闪烁 ❌
```

### 使用 Middleware 方式（新）

```
用户访问 /dashboard
    ↓
Middleware 执行（服务端）
    ↓
检查 Cookie 中的 token
    ↓
未认证 → 重定向到 /login（服务端）
    ↓
用户直接看到登录页 ✅
```

## 优势总结

### 1. 性能优势
- ✅ 服务端重定向，无客户端闪烁
- ✅ 减少不必要的页面渲染
- ✅ 更快的响应速度

### 2. 代码简洁性
- ✅ 不需要在每个页面包装 HOC
- ✅ 路由保护逻辑集中管理
- ✅ 更少的样板代码

### 3. 安全性
- ✅ 服务端验证，更难绕过
- ✅ Token 存储在 Cookie 中，middleware 可访问
- ✅ 统一的认证检查点

### 4. 用户体验
- ✅ 无页面闪烁
- ✅ 支持登录后重定向到原页面
- ✅ 更流畅的导航体验

## 注意事项

### 1. Cookie 大小限制
- Cookie 有 4KB 大小限制
- JWT token 通常在 1-2KB，不会超限
- 如果 token 过大，考虑使用 session

### 2. 服务端渲染
- Middleware 运行在服务端
- 无法访问 localStorage
- 必须使用 Cookie 存储 token

### 3. Token 同步
- 客户端和服务端都需要访问 token
- 同时存储在 localStorage（客户端）和 Cookie（服务端）
- 确保两者保持同步

### 4. 开发环境
- 本地开发时 Cookie 可能不工作（HTTP）
- 需要配置 `secure: false` 在开发环境
- 生产环境必须使用 HTTPS

## 迁移步骤

如果已经使用了 HOC 方式，迁移到 Middleware：

1. ✅ 创建 `middleware.ts` 文件
2. ✅ 更新 `token-manager.ts`，支持 Cookie 存储
3. ✅ 移除所有页面的 `withAuth` 包装
4. ✅ 删除 `with-auth.tsx` 文件
5. ✅ 更新登录组件，支持 redirect 参数
6. ✅ 测试所有受保护路由

## 测试清单

- [ ] 未登录访问 `/dashboard` 重定向到 `/login?redirect=/dashboard`
- [ ] 登录成功后跳转到 redirect 参数指定的页面
- [ ] 已登录访问 `/login` 重定向到 `/dashboard/overview`
- [ ] 刷新页面后认证状态保持
- [ ] Token 过期后自动刷新
- [ ] 登出后清除所有 Cookie 和 localStorage
- [ ] 多标签页同步登录状态

## 相关文档

- [Next.js Middleware 官方文档](https://nextjs.org/docs/app/building-your-application/routing/middleware)
- [前端认证集成方案](./frontend-auth-integration-plan.md)
- [前端认证实施清单](./frontend-auth-implementation-checklist.md)

---

**最后更新**: 2025-12-04
**推荐使用**: ✅ Middleware 方式（更现代、更高效）