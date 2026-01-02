# 管理员权限管理页面设计文档

## 概述

本文档描述了为 AI Higress 系统设计的管理员权限管理界面。该系统采用基于角色的访问控制（RBAC）模型，允许超级管理员管理系统角色、权限以及用户的角色分配。

## 页面设计

### 1. 角色管理页面 (`/system/roles`)

**功能特性：**
- 查看所有系统角色列表
- 创建新角色（角色名称、角色编码、描述）
- 编辑现有角色（仅能修改名称和描述，编码不可变）
- 删除角色
- 为角色分配权限（通过权限选择对话框）

**设计元素：**
- 简洁的卡片式表格布局
- 操作按钮：权限管理（锁图标）、编辑、删除
- 对话框式的权限选择界面，采用勾选框网格布局
- 遵循"东方水墨"风格的极简设计

**API 集成：**
```typescript
- GET /admin/permissions - 获取所有权限定义
- GET /admin/roles - 获取所有角色
- POST /admin/roles - 创建角色
- PUT /admin/roles/{role_id} - 更新角色
- DELETE /admin/roles/{role_id} - 删除角色
- GET /admin/roles/{role_id}/permissions - 查询角色权限
- PUT /admin/roles/{role_id}/permissions - 设置角色权限
```

### 2. 用户管理页面 (`/system/users`)

**功能特性：**
- 查看所有用户列表
- 创建新用户（用户名、邮箱、显示名称、密码）
- 查看用户的角色标签
- 为用户分配/移除角色（通过角色选择对话框）
- 查看用户状态（Active/Inactive）

**设计元素：**
- 用户信息表格，包含姓名、邮箱、角色标签、状态
- 角色以彩色标签形式展示
- 操作按钮：角色管理（盾牌图标）、编辑、删除
- 对话框式的角色选择界面，采用勾选框网格布局

**API 集成：**
```typescript
- GET /admin/users - 获取所有用户
- POST /users - 创建用户
- GET /admin/users/{user_id}/roles - 获取用户角色
- PUT /admin/users/{user_id}/roles - 设置用户角色
```

## 技术实现

### 前端技术栈
- **框架**：Next.js 16 (React 19)
- **UI 组件**：Shadcn UI + Radix UI
- **样式**：Tailwind CSS 4
- **状态管理**：React Hooks (useState, useEffect)
- **HTTP 客户端**：Axios
- **图标**：Lucide React

### 核心文件

#### 1. HTTP 服务层
```
/frontend/http/admin.ts - RBAC 管理 API 服务
```

主要接口：
- `adminService.getPermissions()` - 获取权限列表
- `adminService.getRoles()` - 获取角色列表
- `adminService.createRole()` - 创建角色
- `adminService.updateRole()` - 更新角色
- `adminService.deleteRole()` - 删除角色
- `adminService.getRolePermissions()` - 获取角色权限
- `adminService.setRolePermissions()` - 设置角色权限
- `adminService.getUserRoles()` - 获取用户角色
- `adminService.setUserRoles()` - 设置用户角色
- `adminService.getAllUsers()` - 获取所有用户

#### 2. 页面组件
```
/frontend/app/system/roles/page.tsx - 角色管理页面
/frontend/app/system/users/page.tsx - 用户管理页面
```

#### 3. UI 组件
```
/frontend/components/ui/checkbox.tsx - 复选框组件（新增）
```

#### 4. 国际化
```
/frontend/lib/i18n-context.tsx - 添加了角色和用户管理的中英文翻译
```

翻译键：
- `roles.*` - 角色管理相关
- `users.*` - 用户管理相关

### 数据模型

#### Permission（权限）
```typescript
{
  id: string;
  code: string;
  description: string;
  created_at: string;
  updated_at: string;
}
```

#### Role（角色）
```typescript
{
  id: string;
  code: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}
```

#### UserInfo（用户信息）
```typescript
{
  id: string;
  username: string;
  email: string;
  display_name: string | null;
  avatar: string | null;
  is_active: boolean;
  is_superuser: boolean;
  role_codes?: string[];
  created_at: string;
  updated_at: string;
}
```

## 设计原则

### 1. 极简主义
- 使用最少的元素实现最大功能
- 避免过度装饰和复杂动效
- 留白充足，让界面"呼吸"

### 2. 东方美学（水墨风格）
- 主色调：深灰、纯白、浅灰
- 强调色：深蓝（用于状态标签）
- 细线边框，轻微阴影
- 简洁的图标和文字

### 3. 用户体验
- 清晰的视觉层级
- 一致的交互模式
- 即时反馈（通过 toast 通知）
- 二次确认（删除操作）

### 4. 响应式设计
- 权限/角色选择对话框采用网格布局
- 在小屏幕上自动调整为单列
- 表格在移动设备上可水平滚动

## 安全考虑

1. **权限验证**：所有 RBAC 操作需要超级管理员权限（JWT 认证）
2. **角色编码不可变**：角色编码作为稳定标识符，创建后不允许修改
3. **级联删除**：删除角色时会同时移除该角色的权限绑定和用户角色绑定
4. **全量覆盖语义**：
   - 设置角色权限时，采用全量覆盖（而非增量添加）
   - 设置用户角色时，采用全量覆盖（而非增量添加）

## 使用流程

### 创建角色并分配权限
1. 访问 `/system/roles` 页面
2. 点击"添加角色"按钮
3. 填写角色名称、编码、描述
4. 点击"创建"保存角色
5. 在角色列表中点击"锁"图标
6. 在权限对话框中勾选需要的权限
7. 点击"保存权限"

### 为用户分配角色
1. 访问 `/system/users` 页面
2. 在用户列表中找到目标用户
3. 点击用户行的"盾牌"图标
4. 在角色对话框中勾选需要的角色
5. 点击"保存"完成分配

## 未来改进

1. **批量操作**：支持批量分配角色/权限
2. **角色模板**：提供常用角色模板（如系统管理员、运维人员、查看者等）
3. **权限继承**：支持角色继承机制
4. **审计日志**：记录所有权限变更操作
5. **权限分组**：将权限按功能模块分组显示
6. **搜索过滤**：在用户和角色列表中添加搜索功能
7. **权限描述**：为每个权限提供更详细的说明

## 测试建议

1. **单元测试**：测试 API 服务方法
2. **集成测试**：测试完整的 RBAC 流程
3. **UI 测试**：测试对话框交互和表单验证
4.  **权限测试**：验证非超级管理员无法访问这些页面
5. **边界测试**：测试空数据、大量数据的情况

## 依赖项

新增的 npm 包：
- `@radix-ui/react-checkbox` - 复选框组件

## 导航集成

左侧边栏导航中已添加：
- **角色权限** (`/system/roles`) - 位于管理(Admin)分组下
- **用户管理** (`/system/users`) - 位于管理(Admin)分组下
