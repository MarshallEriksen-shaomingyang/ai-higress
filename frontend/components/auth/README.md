# 认证组件

## PermissionGuard

权限检查组件，用于保护需要特定权限的页面或组件。

### 功能特性

- ✅ 检查用户是否具有所需权限
- ✅ 显示友好的 403 错误页面
- ✅ 支持国际化（中英文）
- ✅ 提供返回和回到首页的操作按钮
- ✅ 加载状态处理

### 使用方法

#### 基本用法

```tsx
import { PermissionGuard } from "@/components/auth/permission-guard";

export default function AdminPage() {
  return (
    <PermissionGuard requiredPermission="superuser">
      <div>
        <h1>管理员页面</h1>
        <p>只有管理员可以看到这个内容</p>
      </div>
    </PermissionGuard>
  );
}
```

#### 在系统页面中使用

```tsx
// frontend/app/dashboard/system/page.tsx
import { PermissionGuard } from "@/components/auth/permission-guard";
import { SystemDashboardClient } from "./_components/system-dashboard-client";

export default function SystemDashboardPage() {
  return (
    <PermissionGuard requiredPermission="superuser">
      <SystemDashboardClient />
    </PermissionGuard>
  );
}
```

### Props

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `children` | `ReactNode` | 是 | 需要权限保护的子组件 |
| `requiredPermission` | `"superuser"` | 是 | 所需的权限类型 |

### 权限类型

目前支持的权限类型：

- `superuser`: 管理员权限（检查 `user.is_superuser === true`）

### 错误页面

当用户没有所需权限时，会显示 403 错误页面，包含：

- 🛡️ 警告图标
- 📝 错误标题和描述
- 🔑 所需权限信息
- 🔙 返回上一页按钮
- 🏠 返回首页按钮

### 国际化

组件使用以下 i18n keys：

- `error.403.heading`: 错误标题
- `error.403.description`: 错误描述
- `error.403.required_permission`: "所需权限"标签
- `error.403.permission_superuser`: "管理员（超级用户）"
- `error.403.contact_admin`: 联系管理员提示
- `error.403.btn_back`: "返回上一页"按钮
- `error.403.btn_home`: "返回首页"按钮
- `common.loading`: 加载中文案

### 工作原理

1. **加载状态**: 在用户信息加载时显示加载提示
2. **权限检查**: 从 `useAuthStore` 获取用户信息，检查 `is_superuser` 字段
3. **权限不足**: 显示 403 错误页面，提供返回操作
4. **权限充足**: 渲染子组件

### 注意事项

- 组件必须在客户端使用（已标记 `"use client"`）
- 依赖 `useAuthStore` 获取用户信息
- 需要配合后端 API 的权限检查使用（三层防护）
- 确保在使用前已经初始化了认证状态（通常在根布局中完成）

### 相关组件

- `AuthDialog`: 登录/注册对话框
- `OAuthButtons`: OAuth 登录按钮
