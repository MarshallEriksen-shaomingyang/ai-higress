# 前端认证功能实施清单

本文档提供了实施前端认证功能的详细步骤清单，包括需要创建/修改的文件和具体代码示例。

## 📋 实施清单

### ✅ 阶段 1: 准备工作

#### 1.1 安装依赖包

```bash
cd frontend
bun add js-cookie
bun add -D @types/js-cookie
```

**验证**: 检查 `package.json` 中是否包含 `js-cookie` 和 `@types/js-cookie`

---

### ✅ 阶段 2: 核心功能实现

#### 2.1 创建 Token 管理工具

**文件**: `frontend/lib/auth/token-manager.ts`

```typescript
import Cookies from 'js-cookie';

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

export const tokenManager = {
  // Access Token (localStorage)
  setAccessToken: (token: string) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(ACCESS_TOKEN_KEY, token);
    }
  },

  getAccessToken: (): string | null => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(ACCESS_TOKEN_KEY);
    }
    return null;
  },

  clearAccessToken: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
    }
  },

  // Refresh Token (Cookie)
  setRefreshToken: (token: string) => {
    Cookies.set(REFRESH_TOKEN_KEY, token, {
      expires: 7, // 7天
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

  // 清除所有 token
  clearAll: () => {
    tokenManager.clearAccessToken();
    tokenManager.clearRefreshToken();
  },
};
```

**验证**: 创建文件并确保导入正常

---

#### 2.2 创建 Zustand Auth Store

**文件**: `frontend/lib/stores/auth-store.ts`

```typescript
import { create } from 'zustand';
import { authService, type UserInfo, type LoginRequest, type RegisterRequest } from '@/http/auth';
import { tokenManager } from '@/lib/auth/token-manager';
import { toast } from 'sonner';

interface AuthState {
  user: UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  // Actions
  setUser: (user: UserInfo | null) => void;
  setLoading: (loading: boolean) => void;
  login: (credentials: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<UserInfo>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  setUser: (user) => {
    set({ 
      user, 
      isAuthenticated: !!user,
      isLoading: false 
    });
  },

  setLoading: (loading) => {
    set({ isLoading: loading });
  },

  login: async (credentials) => {
    try {
      set({ isLoading: true });
      
      // 调用登录 API
      const response = await authService.login(credentials);
      
      // 存储 tokens
      tokenManager.setAccessToken(response.access_token);
      tokenManager.setRefreshToken(response.refresh_token);
      
      // 获取用户信息
      const user = await authService.getCurrentUser();
      
      // 更新状态
      set({ 
        user, 
        isAuthenticated: true,
        isLoading: false 
      });
      
      toast.success('登录成功');
    } catch (error: any) {
      set({ isLoading: false });
      const message = error.response?.data?.detail || '登录失败';
      toast.error(message);
      throw error;
    }
  },

  register: async (data) => {
    try {
      set({ isLoading: true });
      
      // 调用注册 API
      const user = await authService.register(data);
      
      // 注册成功后自动登录
      await get().login({
        username: data.username,
        password: data.password,
      });
      
      toast.success('注册成功');
      return user;
    } catch (error: any) {
      set({ isLoading: false });
      const message = error.response?.data?.detail || '注册失败';
      toast.error(message);
      throw error;
    }
  },

  logout: async () => {
    try {
      // 调用登出 API
      await authService.logout();
    } catch (error) {
      console.error('Logout API error:', error);
    } finally {
      // 无论 API 是否成功，都清除本地状态
      tokenManager.clearAll();
      set({ 
        user: null, 
        isAuthenticated: false,
        isLoading: false 
      });
      toast.success('已退出登录');
    }
  },

  checkAuth: async () => {
    const accessToken = tokenManager.getAccessToken();
    
    if (!accessToken) {
      set({ 
        user: null, 
        isAuthenticated: false,
        isLoading: false 
      });
      return;
    }

    try {
      // 验证 token 并获取用户信息
      const user = await authService.getCurrentUser();
      set({ 
        user, 
        isAuthenticated: true,
        isLoading: false 
      });
    } catch (error) {
      // Token 无效，清除
      tokenManager.clearAll();
      set({ 
        user: null, 
        isAuthenticated: false,
        isLoading: false 
      });
    }
  },
}));
```

**验证**: 
- 创建文件
- 确保所有导入正确
- 测试 store 的创建

---

#### 2.3 更新 Axios Client（添加自动刷新机制）

**文件**: `frontend/http/client.ts`

需要完全重写此文件以支持自动刷新：

```typescript
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { tokenManager } from '@/lib/auth/token-manager';

// 错误提示函数
const showError = (msg: string) => {
  if (typeof window !== 'undefined') {
    import('sonner').then(({ toast }) => {
      toast.error(msg);
    }).catch(() => {
      console.error(msg);
    });
  }
};

// 环境变量
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// 刷新 token 的状态管理
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: any) => void;
  reject: (reason?: any) => void;
}> = [];

// 处理队列中的请求
const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  
  failedQueue = [];
};

// 刷新 token 的函数
const refreshAccessToken = async (): Promise<string> => {
  const refreshToken = tokenManager.getRefreshToken();
  
  if (!refreshToken) {
    throw new Error('No refresh token available');
  }

  try {
    const response = await axios.post(`${BASE_URL}/auth/refresh`, {
      refresh_token: refreshToken,
    });

    const { access_token, refresh_token: new_refresh_token } = response.data;
    
    // 更新 tokens
    tokenManager.setAccessToken(access_token);
    tokenManager.setRefreshToken(new_refresh_token);
    
    return access_token;
  } catch (error) {
    // 刷新失败，清除所有 token
    tokenManager.clearAll();
    throw error;
  }
};

// 创建axios实例
const createHttpClient = (): AxiosInstance => {
  const instance = axios.create({
    baseURL: BASE_URL,
    timeout: 10000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // 请求拦截器
  instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      // 从 tokenManager 获取 token
      const token = tokenManager.getAccessToken();
      const apiKey = typeof window !== 'undefined' 
        ? localStorage.getItem('api_key') 
        : null;

      // 添加认证信息
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      } else if (apiKey) {
        config.headers['X-API-Key'] = apiKey;
      }

      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // 响应拦截器
  instance.interceptors.response.use(
    (response: AxiosResponse) => {
      return response;
    },
    async (error: AxiosError) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

      // 统一错误处理
      if (error.response) {
        const status = error.response.status;
        const errorData = error.response.data as { detail?: string };

        // 401 错误 - 尝试刷新 token
        if (status === 401 && !originalRequest._retry) {
          if (isRefreshing) {
            // 如果正在刷新，将请求加入队列
            return new Promise((resolve, reject) => {
              failedQueue.push({ resolve, reject });
            }).then(token => {
              if (originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${token}`;
              }
              return instance(originalRequest);
            }).catch(err => {
              return Promise.reject(err);
            });
          }

          originalRequest._retry = true;
          isRefreshing = true;

          try {
            const newToken = await refreshAccessToken();
            processQueue(null, newToken);
            
            // 更新原请求的 token 并重试
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
            }
            return instance(originalRequest);
          } catch (refreshError) {
            processQueue(refreshError, null);
            
            // 刷新失败，跳转到登录页
            if (typeof window !== 'undefined') {
              window.location.href = '/login';
            }
            showError('会话已过期，请重新登录');
            return Promise.reject(refreshError);
          } finally {
            isRefreshing = false;
          }
        }

        // 其他错误处理
        switch (status) {
          case 403:
            showError('无权限访问该资源');
            break;
          case 404:
            showError('请求的资源不存在');
            break;
          case 429:
            showError('请求过于频繁，请稍后再试');
            break;
          case 500:
            showError('服务器内部错误');
            break;
          case 503:
            showError('服务暂时不可用');
            break;
          default:
            if (status !== 401) {
              showError(errorData?.detail || '请求失败');
            }
        }
      } else if (error.request) {
        showError('网络连接失败，请检查网络设置');
      } else {
        showError('请求配置错误');
      }

      return Promise.reject(error);
    }
  );

  return instance;
};

// 创建并导出axios实例
export const httpClient = createHttpClient();

// 导出类型
export type { AxiosRequestConfig, AxiosResponse, AxiosError };

// 导出默认实例
export default httpClient;
```

**验证**: 
- 替换现有文件
- 确保所有导入正确
- 测试基本的 API 调用

---

#### 2.4 更新 AuthDialog 组件

**文件**: `frontend/components/auth/auth-dialog.tsx`

```typescript
"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { BrushBorder } from "@/components/ink/brush-border";
import { InkButton } from "@/components/ink/ink-button";
import { FormInput } from "@/components/forms/form-input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useI18n } from "@/lib/i18n-context";
import { useAuthStore } from "@/lib/stores/auth-store";
import { toast } from "sonner";

type AuthMode = "login" | "register";

// 登录表单验证
const loginSchema = z.object({
  username: z.string().min(3, "用户名至少3个字符").max(50, "用户名最多50个字符"),
  password: z.string().min(6, "密码至少6个字符").max(128, "密码最多128个字符"),
});

// 注册表单验证
const registerSchema = z.object({
  username: z.string().min(3, "用户名至少3个字符").max(50, "用户名最多50个字符"),
  email: z.string().email("请输入有效的邮箱地址"),
  password: z.string().min(6, "密码至少6个字符").max(128, "密码最多128个字符"),
  confirmPassword: z.string(),
  display_name: z.string().optional(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "两次输入的密码不一致",
  path: ["confirmPassword"],
});

type LoginFormData = z.infer<typeof loginSchema>;
type RegisterFormData = z.infer<typeof registerSchema>;

export function AuthDialog() {
  const { t } = useI18n();
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("login");
  const { login, register: registerUser, isLoading } = useAuthStore();

  const isLogin = mode === "login";

  // 登录表单
  const loginForm = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: "",
      password: "",
    },
  });

  // 注册表单
  const registerForm = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      username: "",
      email: "",
      password: "",
      confirmPassword: "",
      display_name: "",
    },
  });

  // 处理登录
  const handleLogin = async (data: LoginFormData) => {
    try {
      await login(data);
      router.push('/dashboard/overview');
    } catch (error) {
      // 错误已在 store 中处理
      console.error('Login error:', error);
    }
  };

  // 处理注册
  const handleRegister = async (data: RegisterFormData) => {
    try {
      const { confirmPassword, ...registerData } = data;
      await registerUser(registerData);
      router.push('/dashboard/overview');
    } catch (error) {
      // 错误已在 store 中处理
      console.error('Register error:', error);
    }
  };

  return (
    <Dialog defaultOpen>
      <DialogContent className="max-w-md w-full">
        <DialogHeader className="text-center">
          <DialogTitle className="text-2xl font-serif font-bold">
            {t("app.title")}
          </DialogTitle>
          <DialogDescription>
            {isLogin ? t("auth.login.subtitle") : t("auth.register.subtitle")}
          </DialogDescription>
        </DialogHeader>

        <BrushBorder className="mt-4">
          {isLogin ? (
            <form onSubmit={loginForm.handleSubmit(handleLogin)} className="space-y-6">
              <FormInput
                label={t("auth.email_label")}
                type="text"
                placeholder={t("auth.email_placeholder")}
                {...loginForm.register("username")}
                error={loginForm.formState.errors.username?.message}
              />

              <FormInput
                label={t("auth.password_label")}
                type="password"
                placeholder={t("auth.password_placeholder")}
                {...loginForm.register("password")}
                error={loginForm.formState.errors.password?.message}
              />

              <InkButton 
                className="w-full" 
                type="submit"
                disabled={isLoading}
              >
                {isLoading ? "登录中..." : t("auth.login_button")}
              </InkButton>
            </form>
          ) : (
            <form onSubmit={registerForm.handleSubmit(handleRegister)} className="space-y-6">
              <FormInput
                label={t("auth.name_label")}
                type="text"
                placeholder={t("auth.name_placeholder")}
                {...registerForm.register("display_name")}
                error={registerForm.formState.errors.display_name?.message}
              />

              <FormInput
                label="用户名"
                type="text"
                placeholder="请输入用户名"
                {...registerForm.register("username")}
                error={registerForm.formState.errors.username?.message}
              />

              <FormInput
                label={t("auth.email_label")}
                type="email"
                placeholder={t("auth.email_placeholder")}
                {...registerForm.register("email")}
                error={registerForm.formState.errors.email?.message}
              />

              <FormInput
                label={t("auth.password_label")}
                type="password"
                placeholder={t("auth.password_placeholder")}
                {...registerForm.register("password")}
                error={registerForm.formState.errors.password?.message}
              />

              <FormInput
                label={t("auth.confirm_password_label")}
                type="password"
                placeholder={t("auth.confirm_password_placeholder")}
                {...registerForm.register("confirmPassword")}
                error={registerForm.formState.errors.confirmPassword?.message}
              />

              <InkButton 
                className="w-full" 
                type="submit"
                disabled={isLoading}
              >
                {isLoading ? "注册中..." : t("auth.register_button")}
              </InkButton>
            </form>
          )}
        </BrushBorder>

        <div className="mt-4 text-center text-sm">
          {isLogin ? (
            <p className="text-muted-foreground">
              {t("auth.no_account")}{" "}
              <button
                type="button"
                onClick={() => setMode("register")}
                className="text-primary hover:underline font-medium"
              >
                {t("auth.signup_link")}
              </button>
            </p>
          ) : (
            <p className="text-muted-foreground">
              {t("auth.have_account")}{" "}
              <button
                type="button"
                onClick={() => setMode("login")}
                className="text-primary hover:underline font-medium"
              >
                {t("auth.signin_link")}
              </button>
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

**验证**: 
- 替换现有文件
- 测试表单验证
- 测试登录/注册切换

---

#### 2.5 创建受保护路由 HOC

**文件**: `frontend/lib/auth/with-auth.tsx`

```typescript
"use client";

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/stores/auth-store';

export function withAuth<P extends object>(
  Component: React.ComponentType<P>
) {
  return function AuthenticatedComponent(props: P) {
    const { isAuthenticated, isLoading, checkAuth } = useAuthStore();
    const router = useRouter();

    useEffect(() => {
      checkAuth();
    }, [checkAuth]);

    useEffect(() => {
      if (!isLoading && !isAuthenticated) {
        router.push('/login');
      }
    }, [isAuthenticated, isLoading, router]);

    // 加载中显示骨架屏
    if (isLoading) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        </div>
      );
    }

    // 未认证不渲染
    if (!isAuthenticated) {
      return null;
    }

    return <Component {...props} />;
  };
}
```

**验证**: 创建文件并测试导入

---

#### 2.6 创建用户菜单组件

**文件**: `frontend/components/layout/user-menu.tsx`

```typescript
"use client";

import React from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/stores/auth-store';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { User, Settings, LogOut } from 'lucide-react';

export function UserMenu() {
  const router = useRouter();
  const { user, logout } = useAuthStore();

  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative h-10 w-10 rounded-full">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
            {user.display_name?.[0] || user.username[0].toUpperCase()}
          </div>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="end" forceMount>
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium leading-none">
              {user.display_name || user.username}
            </p>
            <p className="text-xs leading-none text-muted-foreground">
              {user.email}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => router.push('/profile')}>
          <User className="mr-2 h-4 w-4" />
          <span>个人资料</span>
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => router.push('/profile')}>
          <Settings className="mr-2 h-4 w-4" />
          <span>设置</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleLogout}>
          <LogOut className="mr-2 h-4 w-4" />
          <span>退出登录</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

**验证**: 创建文件并测试组件渲染

---

#### 2.7 更新顶部导航栏

**文件**: `frontend/components/layout/top-nav.tsx`

在现有文件中添加用户菜单：

```typescript
// 在文件顶部添加导入
import { useAuthStore } from '@/lib/stores/auth-store';
import { UserMenu } from './user-menu';
import { Button } from '@/components/ui/button';
import { useRouter } from 'next/navigation';

// 在组件内部添加
export function TopNav() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuthStore();

  return (
    <header className="...">
      {/* 现有内容 */}
      
      {/* 在右侧添加用户菜单或登录按钮 */}
      <div className="flex items-center gap-4">
        {!isLoading && (
          isAuthenticated ? (
            <UserMenu />
          ) : (
            <Button onClick={() => router.push('/login')}>
              登录
            </Button>
          )
        )}
      </div>
    </header>
  );
}
```

**验证**: 更新文件并测试显示

---

#### 2.8 更新 FormInput 组件支持错误显示

**文件**: `frontend/components/forms/form-input.tsx`

确保组件支持 `error` 属性：

```typescript
import React from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface FormInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export const FormInput = React.forwardRef<HTMLInputElement, FormInputProps>(
  ({ label, error, ...props }, ref) => {
    return (
      <div className="space-y-2">
        <Label htmlFor={props.id}>{label}</Label>
        <Input ref={ref} {...props} className={error ? 'border-red-500' : ''} />
        {error && (
          <p className="text-sm text-red-500">{error}</p>
        )}
      </div>
    );
  }
);

FormInput.displayName = 'FormInput';
```

**验证**: 更新文件并测试错误显示

---

### ✅ 阶段 3: 应用保护

#### 3.1 保护 Dashboard 页面

**文件**: `frontend/app/dashboard/layout.tsx`

```typescript
"use client";

import { withAuth } from '@/lib/auth/with-auth';

function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="dashboard-layout">
      {/* 现有布局代码 */}
      {children}
    </div>
  );
}

export default withAuth(DashboardLayout);
```

**验证**: 更新文件并测试未登录时的重定向

---

#### 3.2 保护 Profile 页面

**文件**: `frontend/app/profile/layout.tsx`

```typescript
"use client";

import { withAuth } from '@/lib/auth/with-auth';

function ProfileLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="profile-layout">
      {children}
    </div>
  );
}

export default withAuth(ProfileLayout);
```

**验证**: 更新文件并测试

---

#### 3.3 保护 System 页面

**文件**: `frontend/app/system/layout.tsx`

```typescript
"use client";

import { withAuth } from '@/lib/auth/with-auth';

function SystemLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="system-layout">
      {children}
    </div>
  );
}

export default withAuth(SystemLayout);
```

**验证**: 更新文件并测试

---

### ✅ 阶段 4: 根布局集成

#### 4.1 更新根布局检查认证状态

**文件**: `frontend/app/layout.tsx`

```typescript
"use client";

import { useEffect } from 'react';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Toaster } from 'sonner';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const checkAuth = useAuthStore((state) => state.checkAuth);

  useEffect(() => {
    // 应用启动时检查认证状态
    checkAuth();
  }, [checkAuth]);

  return (
    <html lang="zh-CN">
      <body>
        {children}
        <Toaster position="top-right" />
      </body>
    </html>
  );
}
```

**验证**: 更新文件并测试页面刷新时的认证状态保持

---

## 📝 测试清单

### 手动测试

- [ ] **注册流程**
  - [ ] 填写有效信息注册成功
  - [ ] 用户名已存在时显示错误
  - [ ] 邮箱已存在时显示错误
  - [ ] 密码不一致时显示错误
  - [ ] 注册成功后自动登录并跳转

- [ ] **登录流程**
  - [ ] 使用用户名登录成功
  - [ ] 使用邮箱登录成功
  - [ ] 错误的密码显示错误
  - [ ] 不存在的用户显示错误
  - [ ] 登录成功后跳转到 dashboard

- [ ] **Token 刷新**
  - [ ] Access token 过期后自动刷新
  - [ ] 刷新失败后跳转登录页
  - [ ] 多个并发请求只触发一次刷新

- [ ] **登出流程**
  - [ ] 点击登出清除所有认证信息
  - [ ] 登出后跳转到登录页
  - [ ] 登出后无法访问受保护页面

- [ ] **受保护路由**
  - [ ] 未登录访问 dashboard 重定向到登录页
  - [ ] 未登录访问 profile 重定向到登录页
  - [ ] 未登录访问 system 重定向到登录页
  - [ ] 登录后可以正常访问所有页面

- [ ] **页面刷新**
  - [ ] 刷新页面后认证状态保持
  - [ ] Token 有效时不需要重新登录
  - [ ] Token 无效时自动跳转登录页

- [ ] **用户菜单**
  - [ ] 显示用户名和邮箱
  - [ ] 点击个人资料跳转正确
  - [ ] 点击设置跳转正确
  - [ ] 点击登出执行登出操作

---

## 🔍 调试技巧

### 1. 检查 Token 存储

```javascript
// 在浏览器控制台执行
console.log('Access Token:', localStorage.getItem('access_token'));
console.log('Refresh Token:', document.cookie);
```

### 2. 监控 Zustand Store

```javascript
// 在组件中添加
useEffect(() => {
  const unsubscribe = useAuthStore.subscribe(
    (state) => console.log('Auth State:', state)
  );
  return unsubscribe;
}, []);
```

### 3. 监控 Axios 请求

在 `client.ts` 中添加日志：

```typescript
instance.interceptors.request.use(
  (config) => {
    console.log('Request:', config.method, config.url);
    return config;
  }
);

instance.interceptors.response.use(
  (response) => {
    console.log('Response:', response.status, response.config.url);
    return response;
  }
);
```

---

## 🚀 部署注意事项

### 环境变量

确保设置以下环境变量：

```bash
# .env.local
NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com
```

### 生产环境配置

1. **Cookie 安全性**: 确保 `secure: true` 在生产环境启用
2. **HTTPS**: 生产环境必须使用 HTTPS
3. **CORS**: 后端需要正确配置 CORS 允许前端域名

---

## 📚 相关文档

- [前端认证集成方案](./frontend-auth-integration-plan.md)
- [API 文档](./API_Documentation.md)
- [Zustand 文档](https://github.com/pmndrs/zustand)
- [React Hook Form](https://react-hook-form.com/)

---

## ✅ 完成标准

所有以下条件都满足时，认证功能实施完成：

1. ✅ 所有文件已创建/更新
2. ✅ 依赖包已安装
3. ✅ 所有手动测试通过
4. ✅ 没有 TypeScript 错误
5. ✅ 没有 ESLint 警告
6. ✅ 用户体验流畅，无明显延迟
7. ✅ 错误提示清晰友好
8. ✅ 代码已提交到版本控制

---

**最后更新**: 2025-12-04
**维护者**: AI Higress Team