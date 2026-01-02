# 用户权限管理页面设计文档

## 概述

本文档描述了 AI Higress 系统中用户权限管理页面的详细设计方案。该页面允许超级管理员为指定用户授予、更新和撤销细粒度权限，支持配额类权限和功能类权限的管理。

## 页面信息

**页面路径**: `/system/users/[userId]/permissions`

**访问权限**: 仅超级管理员（`is_superuser: true`）

**优先级**: ⭐⭐ 中等

**父页面**: `/system/users` (用户管理页面)

## 功能需求

### 核心功能

1. **查看用户权限列表**
   - 显示指定用户的所有权限记录
   - 展示权限类型、值、过期时间、备注等信息
   - 支持权限状态标识（已过期/有效）

2. **授予新权限**
   - 通过对话框授予新权限
   - 支持选择权限类型
   - 可配置权限值（针对配额类权限）
   - 可设置过期时间
   - 可添加备注说明

3. **更新权限配置**
   - 修改权限值
   - 调整过期时间
   - 更新备注信息

4. **撤销权限**
   - 删除指定权限记录
   - 需要二次确认

5. **权限类型说明**
   - 显示各权限类型的用途和说明
   - 帮助管理员理解权限含义

## 数据模型

### UserPermission（用户权限）

```typescript
interface UserPermission {
  id: string;                      // UUID
  user_id: string;                 // 用户ID
  permission_type: string;         // 权限类型（最多32字符）
  permission_value: string | null; // 权限值（最多100字符，配额类权限使用）
  expires_at: string | null;       // 过期时间（ISO 8601格式）
  notes: string | null;            // 备注说明
  created_at: string;              // 创建时间
  updated_at: string;              // 更新时间
}
```

### 权限类型说明

根据后端模型注释，常见权限类型包括：

- `create_private_provider` - 创建私有提供商权限
- `submit_shared_provider` - 提交共享提供商权限
- `unlimited_providers` - 无限制提供商数量
- `private_provider_limit` - 私有提供商数量限制（配额类，需要 permission_value）

## API 接口

### 1. 获取用户权限列表

```
GET /admin/users/{user_id}/permissions
```

**响应**: `UserPermission[]`

### 2. 授予/更新用户权限

```
POST /admin/users/{user_id}/permissions
```

**请求体**:
```typescript
{
  permission_type: string;         // 必填，最多32字符
  permission_value?: string;       // 可选，最多100字符
  expires_at?: string;             // 可选，ISO 8601格式
  notes?: string;                  // 可选，最多2000字符
}
```

**响应**: `UserPermission`

**说明**: 如果该用户已存在相同 `permission_type` 的权限，则更新；否则创建新记录。

### 3. 撤销用户权限

```
DELETE /admin/users/{user_id}/permissions/{permission_id}
```

**响应**: `204 No Content`

## UI 设计

### 页面布局

```
┌─────────────────────────────────────────────────────────────┐
│ ← 返回用户列表                                               │
│                                                              │
│ 用户权限管理                                                 │
│ 管理 [用户名] 的细粒度权限配置                               │
│                                                              │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ 用户信息卡片                                         │    │
│ │ 👤 [显示名称]                                        │    │
│ │ 📧 [邮箱]                                            │    │
│ │ 🏷️  [角色标签...]                                    │    │
│ └─────────────────────────────────────────────────────┘    │
│                                                              │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ 权限列表                              [+ 授予权限]   │    │
│ │ ─────────────────────────────────────────────────── │    │
│ │ 权限类型 │ 权限值 │ 过期时间 │ 备注 │ 状态 │ 操作  │    │
│ │ ─────────────────────────────────────────────────── │    │
│ │ create_  │   -    │ 2025-12  │ 测试 │ 有效 │ 编辑  │    │
│ │ private_ │        │ -31      │ 用户 │      │ 删除  │    │
│ │ provider │        │          │      │      │       │    │
│ │ ─────────────────────────────────────────────────── │    │
│ │ private_ │  10    │ 永久     │ VIP  │ 有效 │ 编辑  │    │
│ │ provider │        │          │ 用户 │      │ 删除  │    │
│ │ _limit   │        │          │      │      │       │    │
│ └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 组件设计

#### 1. 用户信息卡片

**位置**: 页面顶部

**内容**:
- 用户头像/图标
- 显示名称
- 邮箱地址
- 角色标签（彩色徽章）
- 账户状态（Active/Inactive）

**样式**: 
- 使用 `Card` 组件
- 极简设计，细边框
- 信息横向排列，充分利用空间

#### 2. 权限列表表格

**位置**: 主内容区

**列定义**:

| 列名 | 宽度 | 说明 |
|------|------|------|
| 权限类型 | 25% | 显示 permission_type，使用等宽字体 |
| 权限值 | 15% | 显示 permission_value，无值显示 "-" |
| 过期时间 | 20% | 格式化显示，永久显示"永久" |
| 备注 | 25% | 显示 notes，过长截断 |
| 状态 | 10% | 徽章显示（有效/已过期） |
| 操作 | 5% | 编辑、删除按钮 |

**特性**:
- 使用 `Table` 组件
- 空状态提示："该用户暂无特殊权限"
- 过期权限用灰色显示
- 悬停行高亮

#### 3. 授予权限对话框

**触发**: 点击"授予权限"按钮

**表单字段**:

1. **权限类型** (必填)
   - 组件: `Select` 下拉选择器
   - 选项: 预定义权限类型列表
   - 每个选项显示类型名称和说明

2. **权限值** (可选)
   - 组件: `Input` 文本输入框
   - 仅当选择配额类权限时显示
   - 占位符: "例如: 10"
   - 验证: 数字或字符串，最多100字符

3. **过期时间** (可选)
   - 组件: `DateTimePicker` 或 `Select`
   - 选项: 
     - 永久（默认）
     - 1个月后
     - 3个月后
     - 6个月后
     - 1年后
     - 自定义日期
   - 显示相对时间提示

4. **备注** (可选)
   - 组件: `Textarea` 多行文本框
   - 占位符: "添加备注说明..."
   - 最多2000字符

**按钮**:
- 取消（次要按钮）
- 授予（主要按钮）

**验证**:
- 权限类型必填
- 如果该权限类型已存在，提示将更新现有权限
- 过期时间必须晚于当前时间

#### 4. 编辑权限对话框

**触发**: 点击表格中的"编辑"按钮

**表单字段**:
- 权限类型（只读，灰色背景）
- 权限值（可编辑）
- 过期时间（可编辑）
- 备注（可编辑）

**按钮**:
- 取消
- 保存

#### 5. 删除确认对话框

**触发**: 点击表格中的"删除"按钮

**内容**:
```
确认撤销权限？

您即将撤销用户 [用户名] 的以下权限：
权限类型: [permission_type]
权限值: [permission_value]

此操作不可恢复。
```

**按钮**:
- 取消（次要按钮）
- 确认撤销（危险按钮，红色）

### 权限类型配置

在前端定义权限类型元数据：

```typescript
interface PermissionTypeMetadata {
  type: string;
  name: string;
  description: string;
  requiresValue: boolean;
  valueLabel?: string;
  valuePlaceholder?: string;
  category: 'feature' | 'quota';
}

const PERMISSION_TYPES: PermissionTypeMetadata[] = [
  {
    type: 'create_private_provider',
    name: '创建私有提供商',
    description: '允许用户创建私有提供商',
    requiresValue: false,
    category: 'feature',
  },
  {
    type: 'submit_shared_provider',
    name: '提交共享提供商',
    description: '允许用户提交共享提供商到公共池',
    requiresValue: false,
    category: 'feature',
  },
  {
    type: 'unlimited_providers',
    name: '无限制提供商',
    description: '不限制用户可创建的提供商数量',
    requiresValue: false,
    category: 'quota',
  },
  {
    type: 'private_provider_limit',
    name: '私有提供商限制',
    description: '设置用户可创建的私有提供商数量上限',
    requiresValue: true,
    valueLabel: '数量上限',
    valuePlaceholder: '例如: 10',
    category: 'quota',
  },
];
```

## 技术实现

### 文件结构

```
frontend/
├── app/
│   └── system/
│       └── users/
│           └── [userId]/
│               └── permissions/
│                   ├── page.tsx                    # 主页面（服务端组件）
│                   └── components/
│                       ├── user-info-card.tsx      # 用户信息卡片
│                       ├── permissions-table.tsx   # 权限列表表格（客户端）
│                       ├── grant-permission-dialog.tsx  # 授予权限对话框
│                       ├── edit-permission-dialog.tsx   # 编辑权限对话框
│                       └── revoke-permission-dialog.tsx # 撤销权限对话框
├── http/
│   └── admin.ts                                    # 添加权限管理API
├── lib/
│   ├── api-types.ts                                # 添加权限类型定义
│   ├── swr/
│   │   └── use-user-permissions.ts                 # SWR Hook
│   └── i18n/
│       └── permissions.ts                          # 国际化文案
└── lib/
    └── constants/
        └── permission-types.ts                     # 权限类型元数据
```

### 核心代码示例

#### 1. API 类型定义 (frontend/lib/api-types.ts)

```typescript
// 添加到现有文件
export interface UserPermission {
  id: string;
  user_id: string;
  permission_type: string;
  permission_value: string | null;
  expires_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface GrantPermissionRequest {
  permission_type: string;
  permission_value?: string;
  expires_at?: string;
  notes?: string;
}
```

#### 2. HTTP 服务 (frontend/http/admin.ts)

```typescript
// 添加到现有 adminService
export const adminService = {
  // ... 现有方法

  // 获取用户权限
  getUserPermissions: async (userId: string): Promise<UserPermission[]> => {
    const response = await httpClient.get(`/admin/users/${userId}/permissions`);
    return response.data;
  },

  // 授予/更新权限
  grantUserPermission: async (
    userId: string,
    data: GrantPermissionRequest
  ): Promise<UserPermission> => {
    const response = await httpClient.post(
      `/admin/users/${userId}/permissions`,
      data
    );
    return response.data;
  },

  // 撤销权限
  revokeUserPermission: async (
    userId: string,
    permissionId: string
  ): Promise<void> => {
    await httpClient.delete(
      `/admin/users/${userId}/permissions/${permissionId}`
    );
  },
};
```

#### 3. SWR Hook (frontend/lib/swr/use-user-permissions.ts)

```typescript
import useSWR from 'swr';
import { adminService } from '@/http/admin';
import { UserPermission } from '@/lib/api-types';

export function useUserPermissions(userId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<UserPermission[]>(
    userId ? `/admin/users/${userId}/permissions` : null,
    () => (userId ? adminService.getUserPermissions(userId) : null),
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
    }
  );

  return {
    permissions: data,
    isLoading,
    isError: error,
    mutate,
  };
}
```

#### 4. 国际化 (frontend/lib/i18n/permissions.ts)

```typescript
import type { Language } from "../i18n-context";

export const permissionsTranslations: Record<Language, Record<string, string>> = {
  en: {
    "permissions.title": "User Permissions",
    "permissions.subtitle": "Manage fine-grained permissions for this user",
    "permissions.back_to_users": "Back to Users",
    "permissions.grant_permission": "Grant Permission",
    "permissions.no_permissions": "This user has no special permissions",
    
    "permissions.table_type": "Permission Type",
    "permissions.table_value": "Value",
    "permissions.table_expires": "Expires At",
    "permissions.table_notes": "Notes",
    "permissions.table_status": "Status",
    "permissions.table_actions": "Actions",
    
    "permissions.status_active": "Active",
    "permissions.status_expired": "Expired",
    "permissions.never_expires": "Never",
    
    "permissions.grant_dialog_title": "Grant Permission",
    "permissions.grant_dialog_desc": "Grant a new permission to this user",
    "permissions.edit_dialog_title": "Edit Permission",
    "permissions.edit_dialog_desc": "Update permission configuration",
    
    "permissions.label_type": "Permission Type",
    "permissions.label_value": "Permission Value",
    "permissions.label_expires": "Expires At",
    "permissions.label_notes": "Notes",
    
    "permissions.placeholder_select_type": "Select permission type",
    "permissions.placeholder_value": "e.g., 10",
    "permissions.placeholder_notes": "Add notes...",
    
    "permissions.expires_never": "Never",
    "permissions.expires_1month": "1 Month",
    "permissions.expires_3months": "3 Months",
    "permissions.expires_6months": "6 Months",
    "permissions.expires_1year": "1 Year",
    "permissions.expires_custom": "Custom Date",
    
    "permissions.revoke_confirm_title": "Revoke Permission?",
    "permissions.revoke_confirm_desc": "You are about to revoke the following permission from user {user}:",
    "permissions.revoke_warning": "This action cannot be undone.",
    "permissions.btn_revoke": "Revoke",
    
    "permissions.success_granted": "Permission granted successfully",
    "permissions.success_updated": "Permission updated successfully",
    "permissions.success_revoked": "Permission revoked successfully",
    "permissions.error_grant": "Failed to grant permission",
    "permissions.error_update": "Failed to update permission",
    "permissions.error_revoke": "Failed to revoke permission",
  },
  zh: {
    "permissions.title": "用户权限管理",
    "permissions.subtitle": "管理该用户的细粒度权限配置",
    "permissions.back_to_users": "返回用户列表",
    "permissions.grant_permission": "授予权限",
    "permissions.no_permissions": "该用户暂无特殊权限",
    
    "permissions.table_type": "权限类型",
    "permissions.table_value": "权限值",
    "permissions.table_expires": "过期时间",
    "permissions.table_notes": "备注",
    "permissions.table_status": "状态",
    "permissions.table_actions": "操作",
    
    "permissions.status_active": "有效",
    "permissions.status_expired": "已过期",
    "permissions.never_expires": "永久",
    
    "permissions.grant_dialog_title": "授予权限",
    "permissions.grant_dialog_desc": "为该用户授予新权限",
    "permissions.edit_dialog_title": "编辑权限",
    "permissions.edit_dialog_desc": "更新权限配置",
    
    "permissions.label_type": "权限类型",
    "permissions.label_value": "权限值",
    "permissions.label_expires": "过期时间",
    "permissions.label_notes": "备注",
    
    "permissions.placeholder_select_type": "选择权限类型",
    "permissions.placeholder_value": "例如: 10",
    "permissions.placeholder_notes": "添加备注说明...",
    
    "permissions.expires_never": "永久",
    "permissions.expires_1month": "1个月后",
    "permissions.expires_3months": "3个月后",
    "permissions.expires_6months": "6个月后",
    "permissions.expires_1year": "1年后",
    "permissions.expires_custom": "自定义日期",
    
    "permissions.revoke_confirm_title": "确认撤销权限？",
    "permissions.revoke_confirm_desc": "您即将撤销用户 {user} 的以下权限：",
    "permissions.revoke_warning": "此操作不可恢复。",
    "permissions.btn_revoke": "确认撤销",
    
    "permissions.success_granted": "权限授予成功",
    "permissions.success_updated": "权限更新成功",
    "permissions.success_revoked": "权限撤销成功",
    "permissions.error_grant": "授予权限失败",
    "permissions.error_update": "更新权限失败",
    "permissions.error_revoke": "撤销权限失败",
  },
};
```

#### 5. 权限类型常量 (frontend/lib/constants/permission-types.ts)

```typescript
export interface PermissionTypeMetadata {
  type: string;
  nameKey: string;
  descriptionKey: string;
  requiresValue: boolean;
  valueLabel?: string;
  valuePlaceholder?: string;
  category: 'feature' | 'quota';
}

export const PERMISSION_TYPES: PermissionTypeMetadata[] = [
  {
    type: 'create_private_provider',
    nameKey: 'permissions.type_create_private_provider',
    descriptionKey: 'permissions.type_create_private_provider_desc',
    requiresValue: false,
    category: 'feature',
  },
  {
    type: 'submit_shared_provider',
    nameKey: 'permissions.type_submit_shared_provider',
    descriptionKey: 'permissions.type_submit_shared_provider_desc',
    requiresValue: false,
    category: 'feature',
  },
  {
    type: 'unlimited_providers',
    nameKey: 'permissions.type_unlimited_providers',
    descriptionKey: 'permissions.type_unlimited_providers_desc',
    requiresValue: false,
    category: 'quota',
  },
  {
    type: 'private_provider_limit',
    nameKey: 'permissions.type_private_provider_limit',
    descriptionKey: 'permissions.type_private_provider_limit_desc',
    requiresValue: true,
    valueLabel: 'permissions.label_limit_value',
    valuePlaceholder: 'permissions.placeholder_limit_value',
    category: 'quota',
  },
];
```

## 集成方式

### 方案 1: 独立页面（推荐）

**路由**: `/system/users/[userId]/permissions`

**入口**: 在用户列表表格中添加"权限"操作按钮

```tsx
// 在 /system/users/page.tsx 中
<Button 
  variant="ghost" 
  size="sm" 
  onClick={() => router.push(`/system/users/${user.id}/permissions`)}
>
  <Key className="w-4 h-4" />
</Button>
```

**优点**:
- 页面结构清晰，不影响用户管理页面
- 可以展示更多信息和操作
- URL 可分享和书签

### 方案 2: 标签页集成

在用户详情页中添加"权限"标签页

**优点**:
- 信息集中，切换方便
- 减少页面跳转

**缺点**:
- 需要先实现用户详情页
- 页面复杂度增加

**建议**: 采用方案1（独立页面），更符合当前项目结构。

## 设计原则遵循

### 1. 极简主义
- 使用最少的元素实现功能
- 表格采用细线边框
- 按钮仅在需要时显示
- 充足的留白空间

### 2. 东方美学（墨水风格）
- 主色调：深灰、纯白、浅灰
- 状态徽章使用深蓝和暗红点缀
- 细线边框，轻微阴影
- 简洁的图标和文字

### 3. 用户体验
- 清晰的视觉层级
- 一致的交互模式（参考角色管理页面）
- 即时反馈（toast 通知）
- 二次确认（删除操作）
- 表单验证和错误提示

### 4. 响应式设计
- 表格在小屏幕上可水平滚动
- 对话框在移动设备上全屏显示
- 按钮和输入框适配触摸操作

## 安全考虑

1. **权限验证**: 所有操作需要超级管理员权限（JWT 认证）
2. **唯一性约束**: 同一用户的同一权限类型只能有一条记录
3. **过期时间验证**: 必须晚于当前时间
4. **输入验证**: 
   - permission_type 最多32字符
   - permission_value 最多100字符
   - notes 最多2000字符
5. **级联删除**: 删除用户时自动删除其权限记录（后端已实现）

## 使用流程

### 授予权限流程

1. 访问 `/system/users` 页面
2. 在用户列表中找到目标用户
3. 点击"权限"图标按钮
4. 进入权限管理页面
5. 点击"授予权限"按钮
6. 在对话框中选择权限类型
7. 如果是配额类权限，填写权限值
8. 可选：设置过期时间
9. 可选：添加备注说明
10. 点击"授予"按钮
11. 系统显示成功提示，权限列表自动刷新

### 编辑权限流程

1. 在权限列表中找到要编辑的权限
2. 点击"编辑"按钮
3. 在对话框中修改权限值、过期时间或备注
4. 点击"保存"按钮
5. 系统显示成功提示，权限列表自动刷新

### 撤销权限流程

1. 在权限列表中找到要撤销的权限
2. 点击"删除"按钮
3. 在确认对话框中查看权限详情
4. 点击"确认撤销"按钮
5. 系统显示成功提示，权限从列表中移除

## 测试建议

### 单元测试
- 测试 API 服务方法
- 测试 SWR Hook 的数据获取和更新
- 测试权限类型元数据配置

### 集成测试
- 测试完整的授予权限流程
- 测试编辑权限流程
- 测试撤销权限流程
- 测试权限过期状态显示

### UI 测试
- 测试对话框交互
- 测试表单验证
- 测试空状态显示
- 测试错误处理

### 权限测试
- 验证非超级管理员无法访问
- 验证权限唯一性约束
- 验证过期时间验证

### 边界测试
- 测试空权限列表
- 测试大量权限记录
- 测试长文本备注
- 测试网络错误处理

## 未来改进

1. **批量操作**: 支持批量授予或撤销权限
2. **权限模板**: 提供常用权限组合模板
3. **权限历史**: 记录权限变更历史
4. **权限搜索**: 在权限列表中添加搜索功能
5. **权限分组**: 按类别分组显示权限
6. **权限继承**: 显示从角色继承的权限
7. **权限冲突检测**: 检测并提示权限冲突
8. **权限使用统计**: 显示权限使用情况

## 依赖项

### 新增 npm 包
无需新增，使用现有依赖：
- `@radix-ui/react-dialog` - 对话框组件（已有）
- `@radix-ui/react-select` - 下拉选择器（已有）
- `lucide-react` - 图标库（已有）
- `sonner` - Toast 通知（已有）
- `swr` - 数据获取（已有）

### shadcn/ui 组件
使用现有组件，无需额外安装：
- `Card`, `CardContent`, `CardHeader`, `CardTitle`, `CardDescription`
- `Button`
- `Input`, `Textarea`
- `Select`, `SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem`
- `Table`, `TableHeader`, `TableBody`, `TableRow`, `TableHead`, `TableCell`
- `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription`, `DialogFooter`
- `Badge`

## 导航集成

在用户管理页面 (`/system/users`) 的表格操作列中添加权限管理按钮：

```tsx
<Button 
  variant="ghost" 
  size="sm" 
  onClick={() => router.push(`/system/users/${user.id}/permissions`)}
  title="管理权限"
>
  <Key className="w-4 h-4" />
</Button>
```

图标顺序建议：
1. 角色管理（Shield 图标）
2. 权限管理（Key 图标）- **新增**
3. 编辑（Edit 图标）
4. 删除（Trash2 图标）

## 相关文档

- [用户管理页面](./admin-permission-management.md)
- [角色管理页面](./admin-permission-management.md)
- [后端 API 文档](../backend/API_Documentation.md)
- [前端设计文档](../../frontend/docs/frontend-design.md)
- [UI 设计规范](../../ui-prompt.md)

---

**文档版本**: 1.0  
**创建日期**: 2025-12-05  
**最后更新**: 2025-12-05  
**作者**: AI Architect