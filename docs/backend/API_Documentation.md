# AI Higress API 文档

本文档详细介绍了 AI Higress 项目的所有 API 接口，包括请求参数、响应格式和认证方式，用于辅助前端开发。

## 目录

- [认证](#认证)
- [用户管理](#用户管理)
- [API密钥管理](#api密钥管理)
- [积分与额度](#积分与额度)
- [厂商密钥管理](#厂商密钥管理)
- [提供商管理](#提供商管理)
- [逻辑模型管理](#逻辑模型管理)
- [路由管理](#路由管理)
- [会话管理](#会话管理)
- [系统管理](#系统管理)

---

## 认证

### 1. 用户注册

**接口**: `POST /auth/register`

**描述**: 创建新用户账户。

该接口仅在管理员配置的“注册开放窗口”内可用：

- 管理员可以预设注册开放的开始/结束时间以及本轮允许的注册人数。
- `auto` 窗口会让新用户自动激活（`is_active=true`）；`manual` 窗口会保留注册信息但默认未激活，需要管理员后续审核。
- 超过结束时间或名额耗尽后，接口会返回 403 禁止访问。

**请求体**:
```json
{
  "email": "string (有效邮箱)",
  "password": "string (最少6字符)",
  "display_name": "string (可选)"
}
```

> 用户名会由后端基于邮箱前缀自动生成并保证唯一性。

**响应**:
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "display_name": "string | null",
  "avatar": "string | null",
  "is_active": true,
  "is_superuser": false,
  "role_codes": ["default_user"],
  "permission_flags": [
    {
      "key": "can_create_private_provider",
      "value": false
    },
    {
      "key": "can_submit_shared_provider",
      "value": false
    }
  ],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**错误响应**:
- 400: 用户名已存在
- 400: 邮箱已被使用
- 403: 当前未开放注册、注册时间已结束或名额耗尽

---

### 1.1 定时开放注册管理（管理员）

**接口**:

- `POST /admin/registration-windows/auto`：创建一个自动激活的注册窗口。
- `POST /admin/registration-windows/manual`：创建一个需要手动激活的注册窗口。
- `GET /admin/registration-windows/active`：查看当前正在生效的注册窗口（没有时返回 `null`）。

**请求体（创建窗口）**:
```json
{
  "start_time": "2024-06-01T10:00:00+08:00", // 必须包含时区
  "end_time": "2024-06-01T12:00:00+08:00",
  "max_registrations": 100
}
```

**响应示例（创建/查询）**:
```json
{
  "id": "uuid",
  "start_time": "2024-06-01T10:00:00+08:00",
  "end_time": "2024-06-01T12:00:00+08:00",
  "max_registrations": 100,
  "registered_count": 3,
  "auto_activate": true,
  "status": "active",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**说明**:
- `auto_activate=true` 表示注册完成即自动激活；`false` 表示需要管理员后续审核/激活。
- 创建时会自动安排 Celery 任务在开始/结束时间切换状态，服务端也会在请求时兜底检查时间窗口与名额。

---

### 2. 用户登录

**接口**: `POST /auth/login`

**描述**: 用户登录获取 JWT 令牌。登录成功后，系统会将 Token 信息存储到 Redis 中，包括设备信息（User-Agent、IP地址）用于会话管理和安全审计。

**请求头**:
- `User-Agent` (可选): 客户端标识，用于记录设备信息

**请求体**:
```json
{
  "username": "string", // 用户名或邮箱
  "password": "string"
}
```

**响应**:
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "expires_in": 1800 // 访问令牌过期时间(秒)，默认30分钟
}
```

**Token 存储说明**:
- Access Token 有效期：30 分钟
- Refresh Token 有效期：7 天
- Token 信息存储在 Redis 中，包含：
  - Token ID (JTI)
  - 用户 ID
  - 设备信息（User-Agent、IP地址）
  - Token 家族 ID（用于检测 Refresh Token 重用攻击）
  - 创建时间和过期时间

**错误响应**:
- 401: 用户名或密码错误
- 403: 账户已被禁用

---

### 3. 刷新令牌

**接口**: `POST /auth/refresh`

**描述**: 使用刷新令牌获取新的访问令牌。系统实现了 Token 轮换机制，每次刷新都会生成新的 Refresh Token 并撤销旧的 Refresh Token，防止 Token 重用攻击。

**请求头**:
- `User-Agent` (可选): 客户端标识，用于记录设备信息

**请求体**:
```json
{
  "refresh_token": "string"
}
```

**响应**:
```json
{
  "access_token": "string",
  "refresh_token": "string", // 新的 Refresh Token
  "token_type": "bearer",
  "expires_in": 1800 // 30分钟
}
```

**Token 轮换机制**:
- 每次刷新都会生成新的 Access Token 和 Refresh Token
- 旧的 Refresh Token 会被立即撤销并加入黑名单
- 新的 Refresh Token 继承相同的 Token 家族 ID
- 如果检测到已撤销的 Refresh Token 被重用，系统会撤销整个 Token 家族，防止安全攻击

**错误响应**:
- 401: 无效的刷新令牌
- 401: Token 已被撤销
- 401: Token 家族已被撤销（检测到重用攻击）

---

### 4. 获取当前用户信息

**接口**: `GET /auth/me`

**描述**: 获取当前认证用户的信息。

**认证**: JWT 令牌

**响应**:
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "display_name": "string | null",
  "avatar": "string | null",
  "is_superuser": true/false
}
```

---

### 5. 用户登出

**接口**: `POST /auth/logout`

**描述**: 用户登出，撤销当前 Access Token 和 Refresh Token。Token 会被加入黑名单，立即失效。

**认证**: JWT 令牌

**响应**:
```json
{
  "message": "已成功登出"
}
```

**Token 撤销说明**:
- 当前 Access Token 会被加入黑名单
- 关联的 Refresh Token 也会被撤销
- 撤销后的 Token 无法再用于任何 API 请求
- 黑名单记录会保留到 Token 原本的过期时间

**错误响应**:
- 401: Token 无效或已过期

---

### 6. 登出所有设备

**接口**: `POST /auth/logout-all`

**描述**: 撤销当前用户的所有 Token，强制所有设备登出。适用于账户安全事件（如密码泄露）或用户主动清理所有会话。

**认证**: JWT 令牌

**响应**:
```json
{
  "message": "已成功登出所有设备",
  "revoked_count": 5 // 撤销的 Token 数量
}
```

**撤销范围**:
- 撤销用户的所有 Access Token
- 撤销用户的所有 Refresh Token
- 清除用户的所有活跃会话记录
- 所有设备需要重新登录

**错误响应**:
- 401: Token 无效或已过期

---

## 会话管理

### 1. 获取用户会话列表

**接口**: `GET /v1/sessions`

**描述**: 获取当前用户的所有活跃会话列表，包括设备信息、登录时间、最后活跃时间等。

**认证**: JWT 令牌

**响应**:
```json
{
  "sessions": [
    {
      "token_id": "string",
      "device_info": {
        "user_agent": "Mozilla/5.0 ...",
        "ip_address": "192.168.1.100"
      },
      "created_at": "2025-12-04T10:30:00Z",
      "last_used_at": "2025-12-04T12:00:00Z",
      "expires_at": "2025-12-11T10:30:00Z",
      "is_current": true // 是否为当前会话
    }
  ],
  "total": 3
}
```

**字段说明**:
- `token_id`: Token 的唯一标识符
- `device_info`: 设备信息
  - `user_agent`: 浏览器/客户端标识
  - `ip_address`: 登录时的 IP 地址
- `created_at`: 会话创建时间（登录时间）
- `last_used_at`: 最后活跃时间
- `expires_at`: 会话过期时间
- `is_current`: 是否为当前请求使用的会话

**错误响应**:
- 401: Token 无效或已过期

---

### 2. 撤销指定会话

**接口**: `DELETE /v1/sessions/{token_id}`

**描述**: 撤销指定的会话，使该设备的 Token 失效。用户可以远程登出其他设备。

**认证**: JWT 令牌

**路径参数**:
- `token_id`: 要撤销的会话 Token ID

**成功响应**: 204 No Content

**错误响应**:
- 401: Token 无效或已过期
- 403: 无权撤销其他用户的会话
- 404: 会话不存在或已过期

---

### 3. 撤销所有其他会话

**接口**: `DELETE /v1/sessions/others`

**描述**: 撤销当前用户的所有其他会话，保留当前会话。适用于用户发现异常登录时快速清理其他设备。

**认证**: JWT 令牌

**响应**:
```json
{
  "message": "已成功撤销所有其他会话",
  "revoked_count": 4 // 撤销的会话数量
}
```

**错误响应**:
- 401: Token 无效或已过期

---

## 用户管理

### 1. 创建用户

**接口**: `POST /users`

**描述**: 创建新用户。

**认证**: JWT 令牌

**请求体**:
```json
{
  "username": "string (3-64字符, 字母数字._-)",
  "email": "string (有效邮箱)",
  "password": "string (8-128字符)",
  "display_name": "string (可选, 最大255字符)",
  "avatar": "string (可选, 最大512字符)"
}
```

**响应**:
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "display_name": "string | null",
  "avatar": "string | null",
  "is_active": true,
  "is_superuser": false,
  "role_codes": ["default_user"],
  "permission_flags": [
    {
      "key": "can_create_private_provider",
      "value": false
    },
    {
      "key": "can_submit_shared_provider",
      "value": false
    }
  ],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

### 2. 获取当前用户信息

**接口**: `GET /users/me`

**描述**: 获取当前认证用户的信息。

**认证**: JWT 令牌

**响应**:
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "display_name": "string | null",
  "avatar": "string | null",
  "is_active": true,
  "is_superuser": false,
  "role_codes": ["default_user"],
  "can_create_private_provider": false,
  "can_submit_shared_provider": false,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

### 3. 更新用户信息

**接口**: `PUT /users/{user_id}`

**描述**: 更新用户信息。

**认证**: JWT 令牌

**请求体**:
```json
{
  "email": "string (可选)",
  "password": "string (可选, 8-128字符)",
  "display_name": "string (可选, 最大255字符)",
  "avatar": "string (可选, 最大512字符)"
}
```

**响应**:
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "display_name": "string | null",
  "avatar": "string | null",
  "is_active": true,
  "is_superuser": false,
  "role_codes": ["default_user"],
  "permission_flags": [
    {
      "key": "can_create_private_provider",
      "value": false
    },
    {
      "key": "can_submit_shared_provider",
      "value": false
    }
  ],
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

### 4. 更新用户状态

**接口**: `PUT /users/{user_id}/status`

**描述**: 允许超级用户启用/禁用用户。禁用用户时，系统会立即撤销该用户在 Redis 中登记的所有 JWT Token（包括所有设备/会话），并清理其 API 密钥缓存，使禁用操作立刻生效。

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "is_active": true/false
}
```

**响应**:
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "display_name": "string | null",
  "avatar": "string | null",
  "is_active": true/false,
  "is_superuser": false,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

### 5. 管理员获取用户权限列表

**接口**: `GET /admin/users/{user_id}/permissions`

**描述**: 管理员查看指定用户的权限和配额配置，例如是否允许创建私有提供商、是否可以提交共享提供商等。

**认证**: JWT 令牌 (仅限超级用户)

**响应**:
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "permission_type": "create_private_provider | submit_shared_provider | unlimited_providers | private_provider_limit | ...",
    "permission_value": "string | null",
    "expires_at": "datetime | null",
    "notes": "string | null",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

---

### 6. 管理员授予或更新用户权限

**接口**: `POST /admin/users/{user_id}/permissions`

**描述**: 管理员为用户授予或更新某一项权限/配额。

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "permission_type": "create_private_provider | submit_shared_provider | unlimited_providers | private_provider_limit | ...",
  "permission_value": "string | null",
  "expires_at": "datetime | null",
  "notes": "string | null"
}
```

**响应**: 与权限列表中的单条记录结构相同。

---

### 7. 管理员撤销用户权限

**接口**: `DELETE /admin/users/{user_id}/permissions/{permission_id}`

**描述**: 管理员撤销用户的一条权限记录。

**认证**: JWT 令牌 (仅限超级用户)

**成功响应**: 204 No Content

---

### 8. 超级管理员管理角色与权限（RBAC）

以下接口仅面向超级管理员 (`is_superuser = true`)，用于通过“角色 + 权限”集中管理用户能力。  
权限判断统一走后端的 `UserPermissionService.has_permission(user_id, permission_code)`，会综合：
- `is_superuser`
- 用户直挂权限 `user_permissions.permission_type`
- 用户所属角色上的权限 `permissions.code`

#### 8.1 查询权限定义列表

**接口**: `GET /admin/permissions`

**描述**: 列出系统中所有可用的权限定义（`Permission.code`），供前端做勾选。

**认证**: JWT 令牌 (仅限超级用户)

**响应**:
```json
[
  {
    "id": "uuid",
    "code": "create_private_provider",
    "description": "允许创建私有 Provider",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

---

#### 8.2 查询角色列表

**接口**: `GET /admin/roles`

**描述**: 列出所有已创建的角色。

**认证**: JWT 令牌 (仅限超级用户)

**响应**:
```json
[
  {
    "id": "uuid",
    "code": "system_admin",
    "name": "系统管理员",
    "description": "拥有系统全部管理能力",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

---

#### 8.3 创建角色

**接口**: `POST /admin/roles`

**描述**: 创建新角色，例如 `system_admin`、`operator`、`viewer` 等。

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "code": "system_admin",          // 角色唯一编码，建议使用小写+下划线
  "name": "系统管理员",             // 展示名称
  "description": "拥有系统全部管理能力" // 可选描述
}
```

**响应**: 与角色列表中的单条记录结构相同。

**错误响应**:
- 400: 角色编码已存在

---

#### 8.4 更新角色

**接口**: `PUT /admin/roles/{role_id}`

**描述**: 更新角色的名称和描述（`code` 视为稳定主键，不允许修改）。

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "name": "新的角色名称",
  "description": "新的角色描述"
}
```

**响应**: 与角色列表中的单条记录结构相同。

---

#### 8.5 删除角色

**接口**: `DELETE /admin/roles/{role_id}`

**描述**: 删除一个角色，会级联删除该角色上的权限绑定和用户角色绑定。

**认证**: JWT 令牌 (仅限超级用户)

**成功响应**: 204 No Content

**注意**: 删除角色不会删除 `permissions` 中的权限定义，也不会影响用户直挂的 `user_permissions`。

---

#### 8.6 查询角色已绑定的权限

**接口**: `GET /admin/roles/{role_id}/permissions`

**描述**: 查看指定角色当前绑定的权限列表。

**认证**: JWT 令牌 (仅限超级用户)

**响应**:
```json
{
  "role_id": "uuid",
  "role_code": "system_admin",
  "permission_codes": [
    "manage_users",
    "manage_user_permissions",
    "admin_view_providers",
    "manage_provider_keys"
  ]
}
```

---

#### 8.7 设置角色的权限列表（全量覆盖）

**接口**: `PUT /admin/roles/{role_id}/permissions`  
**别名**: `POST /admin/roles/{role_id}/permissions`

**描述**: 将角色的权限列表设置为给定的 `permission_codes` 集合，采用“全量覆盖”语义：  
- 请求体为空数组 → 清空角色的全部权限  
- 请求体为非空数组 → 删除多余权限、添加缺少权限

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "permission_codes": [
    "manage_users",
    "manage_user_permissions",
    "admin_view_providers"
  ]
}
```

**响应**:
```json
{
  "role_id": "uuid",
  "role_code": "system_admin",
  "permission_codes": [
    "manage_users",
    "manage_user_permissions",
    "admin_view_providers"
  ]
}
```

**错误响应**:
- 400: 存在无效的权限编码  
  - `details.missing_permission_codes`: 无效的 `code` 列表

---

#### 8.8 查询用户当前角色列表

**接口**: `GET /admin/users/{user_id}/roles`

**描述**: 查看指定用户当前拥有的角色列表。

**认证**: JWT 令牌 (仅限超级用户)

**响应**:
```json
[
  {
    "id": "uuid",
    "code": "system_admin",
    "name": "系统管理员",
    "description": "拥有系统全部管理能力",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

---

#### 8.9 为用户设置角色列表（全量覆盖）

**接口**: `PUT /admin/users/{user_id}/roles`  
**别名**: `POST /admin/users/{user_id}/roles`

**描述**: 为用户设置角色列表，采用“全量覆盖”语义：
- `role_ids` 为空数组 → 清空用户的所有角色
- `role_ids` 非空 → 移除不在列表中的角色，添加新增角色

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "role_ids": [
    "uuid-of-system-admin-role",
    "uuid-of-operator-role"
  ]
}
```

**响应**: 与用户当前角色列表结构相同（`list[RoleResponse]`）。

**错误响应**:
- 400: 存在无效的角色 ID  
  - `details.missing_role_ids`: 无效的 `role_id` 列表

---

## API密钥管理

> 说明：后台 Celery 定时任务会自动扫描已过期或高错误率的 API Key 并标记 `is_active=false`，同时在响应体中返回 `disabled_reason`，客户端应在 UI 中提示并允许重新生成/启用新密钥。

### 1. 获取API密钥列表

**接口**: `GET /users/{user_id}/api-keys`

**描述**: 获取指定用户的所有API密钥。

**认证**: JWT 令牌

**响应**:
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "name": "string",
    "key_prefix": "string",
    "expiry_type": "week/month/year/never",
    "expires_at": "datetime | null",
    "is_active": true,
    "disabled_reason": "string | null",
    "created_at": "datetime",
    "updated_at": "datetime",
    "has_provider_restrictions": true/false,
    "allowed_provider_ids": ["string"]
  }
]
```

---

### 2. 创建API密钥

**接口**: `POST /users/{user_id}/api-keys`

**描述**: 创建新的API密钥。

**认证**: JWT 令牌

**请求体**:
```json
{
  "name": "string (1-255字符)",
  "expiry": "week/month/year/never (可选, 默认never)",
  "allowed_provider_ids": ["string"] (可选, 限制可访问的提供商)
}
```

**响应**:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "string",
  "key_prefix": "string",
    "expiry_type": "week/month/year/never",
    "expires_at": "datetime | null",
    "is_active": true,
    "disabled_reason": "string | null",
    "created_at": "datetime",
    "updated_at": "datetime",
    "has_provider_restrictions": true/false,
  "allowed_provider_ids": ["string"],
  "token": "string" // 完整密钥，仅在创建时返回
}
```

**错误响应**:
- 400: 密钥名称已存在

---

### 3. 更新API密钥

**接口**: `PUT /users/{user_id}/api-keys/{key_id}`

**描述**: 更新API密钥信息。

**认证**: JWT 令牌

**请求体**:
```json
{
  "name": "string (可选)",
  "expiry": "week/month/year/never (可选)",
  "allowed_provider_ids": ["string"] (可选, 空数组表示清除限制)
}
```

**响应**:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "string",
  "key_prefix": "string",
    "expiry_type": "week/month/year/never",
    "expires_at": "datetime | null",
    "is_active": true,
    "disabled_reason": "string | null",
    "created_at": "datetime",
    "updated_at": "datetime",
    "has_provider_restrictions": true/false,
  "allowed_provider_ids": ["string"]
}
```

**错误响应**:
- 400: 密钥名称已存在

---

### 4. 获取API密钥允许的提供商

**接口**: `GET /users/{user_id}/api-keys/{key_id}/allowed-providers`

**描述**: 获取API密钥允许访问的提供商列表。

**认证**: JWT 令牌

**响应**:
```json
{
  "has_provider_restrictions": true/false,
  "allowed_provider_ids": ["string"]
}
```

---

### 5. 设置API密钥允许的提供商

**接口**: `PUT /users/{user_id}/api-keys/{key_id}/allowed-providers`

**描述**: 设置API密钥允许访问的提供商列表。

**认证**: JWT 令牌

**请求体**:
```json
{
  "allowed_provider_ids": ["string"] // 空数组表示清除限制
}
```

**响应**:
```json
{
  "has_provider_restrictions": true/false,
  "allowed_provider_ids": ["string"]
}
```

---

### 6. 删除API密钥允许的提供商

**接口**: `DELETE /users/{user_id}/api-keys/{key_id}/allowed-providers/{provider_id}`

**描述**: 从API密钥允许的提供商列表中移除指定的提供商。

**认证**: JWT 令牌

**成功响应**: 204 No Content

---

### 7. 删除API密钥

**接口**: `DELETE /users/{user_id}/api-keys/{key_id}`

**描述**: 删除指定的API密钥。

**认证**: JWT 令牌

**成功响应**: 204 No Content

---

## 积分与额度

系统支持按“用户账户积分”维度控制网关调用额度。所有通过 API Key 访问的网关请求，最终都会映射到某个用户账户下的积分余额。

> 说明：只有在环境变量 `ENABLE_CREDIT_CHECK=true` 时，积分不足才会阻断网关调用；默认情况下仅记录流水，不做强制限制。

当 `ENABLE_CREDIT_CHECK=true` 且用户余额小于等于 0 时：
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/messages`

会返回 `402 Payment Required`，错误体示例：

```json
{
  "detail": {
    "code": "CREDIT_NOT_ENOUGH",
    "message": "积分不足，请先充值后再调用接口",
    "balance": 0
  }
}
```

### 计费规则

网关在记录一次 LLM 调用的 usage 时，会根据 token 用量和配置计算本次应扣的积分：

- 基础单价：`CREDITS_BASE_PER_1K_TOKENS`（环境变量），表示“1x 模型每 1000 tokens 消耗多少积分”；  
- 模型倍率：`ModelBillingConfig.multiplier`，按模型或逻辑模型 ID 设置，例如：
  - `gpt-4o-mini` = 0.5  
  - `gpt-4o` = 2.0  
- Provider 结算系数：`Provider.billing_factor`，按具体 Provider 细化成本：
  - 默认 `1.0`，代表基准成本；
  - >1.0 表示该 Provider 更贵（同模型下会多扣积分）；
  - <1.0 表示该 Provider 更便宜或只收少量服务费（例如用户自建 Provider）。

综合起来，单次调用的积分消耗近似为：

```text
effective_multiplier = model_multiplier * billing_factor
cost_credits = ceil(total_tokens / 1000 * CREDITS_BASE_PER_1K_TOKENS * effective_multiplier)
```

因此，同一个模型在不同 Provider 下，实际扣除的积分可以不同，用于反映不同厂商或不同渠道的成本差异。

### 1. 查询当前用户积分

**接口**: `GET /v1/credits/me`  
**认证**: JWT 令牌

**成功响应示例**:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "balance": 1200,
  "daily_limit": null,
  "status": "active",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-02T12:34:56Z"
}
```

### 2. 查询当前用户积分流水

**接口**: `GET /v1/credits/me/transactions`  
**认证**: JWT 令牌

**查询参数**:
- `limit` (int, 默认 50, 1-100): 返回的最大记录数  
- `offset` (int, 默认 0): 起始偏移量

**成功响应示例**:
```json
[
  {
    "id": "uuid",
    "account_id": "uuid",
    "user_id": "uuid",
    "api_key_id": "uuid",
    "amount": -25,
    "reason": "usage",
    "description": null,
    "model_name": "gpt-4o-mini",
    "input_tokens": 500,
    "output_tokens": 300,
    "total_tokens": 800,
    "created_at": "2025-01-02T12:34:56Z"
  }
]
```

### 3. 管理员为用户充值积分

**接口**: `POST /v1/credits/admin/users/{user_id}/topup`  
**认证**: JWT 令牌（仅限超级管理员）

**请求体**:
```json
{
  "amount": 1000,
  "description": "测试充值 / 赠送额度"
}
```

**成功响应**: 返回更新后的用户积分账户结构，字段与 `GET /v1/credits/me` 相同。

---

## 厂商密钥管理

### 1. 获取厂商API密钥列表

**接口**: `GET /providers/{provider_id}/keys`

**描述**: 获取指定厂商的所有API密钥。

**认证**: JWT 令牌 (仅限超级用户)

**响应**:
```json
[
  {
    "id": "string",
    "provider_id": "string",
    "label": "string",
    "weight": 1.0,
    "max_qps": 1000,
    "status": "active/inactive",
    "created_at": "datetime",
    "updated_at": "datetime | null"
  }
]
```

---

### 2. 创建厂商API密钥

**接口**: `POST /providers/{provider_id}/keys`

**描述**: 为指定厂商创建新的API密钥。

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "key": "string", // API认证密钥或令牌
  "label": "string", // 密钥的可识别标签
  "weight": 1.0, // 相对路由权重
  "max_qps": 1000, // 可选的每密钥QPS限制
  "status": "active/inactive" // 密钥状态
}
```

**响应**:
```json
{
  "id": "string",
  "provider_id": "string",
  "label": "string",
  "weight": 1.0,
  "max_qps": 1000,
  "status": "active/inactive",
  "created_at": "datetime",
  "updated_at": "datetime | null"
}
```

---

### 3. 获取厂商API密钥详情

**接口**: `GET /providers/{provider_id}/keys/{key_id}`

**描述**: 获取指定的厂商API密钥详情。

**认证**: JWT 令牌 (仅限超级用户)

**响应**:
```json
{
  "id": "string",
  "provider_id": "string",
  "label": "string",
  "weight": 1.0,
  "max_qps": 1000,
  "status": "active/inactive",
  "created_at": "datetime",
  "updated_at": "datetime | null"
}
```

**错误响应**:
- 404: 密钥不存在

---

### 4. 更新厂商API密钥

**接口**: `PUT /providers/{provider_id}/keys/{key_id}`

**描述**: 更新指定的厂商API密钥。

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "key": "string", // 可选
  "label": "string", // 可选
  "weight": 1.0, // 可选
  "max_qps": 1000, // 可选
  "status": "active/inactive" // 可选
}
```

**响应**:
```json
{
  "id": "string",
  "provider_id": "string",
  "label": "string",
  "weight": 1.0,
  "max_qps": 1000,
  "status": "active/inactive",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

### 5. 删除厂商API密钥

**接口**: `DELETE /providers/{provider_id}/keys/{key_id}`

**描述**: 删除指定的厂商API密钥。

**认证**: JWT 令牌 (仅限超级用户)

**成功响应**: 204 No Content

---

## 提供商管理

### 1. 获取提供商列表

**接口**: `GET /providers`

**描述**: 获取所有已配置的提供商列表（从数据库加载）。

**认证**: API密钥

**响应**:
```json
{
  "providers": [
  {
    "id": "string",
    "name": "string",
    "base_url": "url",
    "api_key": "string | null",
    "api_keys": [
      {
        "key": "string",
        "weight": 1.0,
        "max_qps": 1000,
        "label": "string"
      }
    ],
    "models_path": "/v1/models",
    "messages_path": "/v1/message",
    "chat_completions_path": "/v1/chat/completions",
    "responses_path": "/v1/responses 或 null",
    "weight": 1.0,
    "region": "string | null",
    "cost_input": 0.0,
    "cost_output": 0.0,
    "billing_factor": 1.0,
    "max_qps": 1000,
    "custom_headers": {},
    "retryable_status_codes": [429, 500, 502, 503, 504],
    "static_models": [],
    "transport": "http/sdk",
    "provider_type": "native/aggregator",
    "sdk_vendor": "openai/google/claude 或 null",
    "supported_api_styles": ["openai", "responses", "claude"] 或 null
  }
],
  "total": 1
}
```

> 说明：
> - 当 `transport = "sdk"` 时，必须在后台配置 `sdk_vendor` 为 `openai` / `google` / `claude`，网关才会走对应官方 SDK；
> - 当 `transport = "http"` 时，`sdk_vendor` 一律为 `null`，表示纯 HTTP 代理模式。

---

### 2. 获取指定提供商信息

**接口**: `GET /providers/{provider_id}`

**描述**: 获取指定提供商的配置信息。

**认证**: API密钥

**响应**:
```json
{
  "id": "string",
  "name": "string",
  "base_url": "url",
  "api_key": "string | null",
  "api_keys": [
    {
      "key": "string",
      "weight": 1.0,
      "max_qps": 1000,
      "label": "string"
    }
  ],
  "models_path": "/v1/models",
  "messages_path": "/v1/message",
  "chat_completions_path": "/v1/chat/completions",
  "responses_path": "/v1/responses 或 null",
  "weight": 1.0,
  "region": "string | null",
  "cost_input": 0.0,
  "cost_output": 0.0,
  "billing_factor": 1.0,
  "max_qps": 1000,
  "custom_headers": {},
  "retryable_status_codes": [429, 500, 502, 503, 504],
  "static_models": [],
  "transport": "http/sdk",
  "provider_type": "native/aggregator",
  "sdk_vendor": "openai/google/claude 或 null",
  "supported_api_styles": ["openai", "responses", "claude"] 或 null
}
```

**错误响应**:
- 404: 提供商不存在

---

### 3. 获取提供商模型列表

**接口**: `GET /providers/{provider_id}/models`

**描述**: 获取指定提供商支持的模型列表。

**认证**: API密钥

**响应**:
```json
{
  "models": [
    {
      "id": "string",
      "object": "string",
      "created": 1234567890,
      "owned_by": "string"
    }
  ],
  "total": 1
}
```

---

### 4. 检查提供商健康状态

**接口**: `GET /providers/{provider_id}/health`

**描述**: 执行轻量级健康检查。

**认证**: API密钥

**响应**:
```json
{
  "status": "healthy/degraded/down",
  "last_check": 1234567890.0,
  "metadata": {}
}
```

**错误响应**:
- 404: 提供商不存在

---

### 5. 获取提供商路由指标（实时快照）

**接口**: `GET /providers/{provider_id}/metrics`

**描述**: 获取提供商的路由指标实时快照（来自 Redis，按逻辑模型聚合）。

**认证**: API密钥

**查询参数**:
- `logical_model` (可选): 逻辑模型过滤器；若提供，则返回该逻辑模型与 Provider 的一条聚合记录

**响应**:
```json
{
  "metrics": [
    {
      "logical_model": "gpt-4",
      "provider_id": "openai",
      "latency_p95_ms": 200.0,
      "latency_p99_ms": 350.0,
      "error_rate": 0.02,
      "success_qps_1m": 3.5,
      "total_requests_1m": 220,
      "last_updated": 1733212345.123,
      "status": "healthy"  // healthy / degraded / down
    }
  ]
}
```

**错误响应**:
- 404: 提供商不存在

---

### 5.1 获取 Provider 路由指标时间序列（按分钟）

**接口**: `GET /metrics/providers/timeseries`

**描述**: 获取指定 Provider + 逻辑模型在给定时间范围内的分钟级指标时间序列，可用于绘制折线图。

**认证**: API 密钥

**查询参数**:
- `provider_id` (必填): 厂商 ID，例如 `openai`
- `logical_model` (必填): 逻辑模型 ID，例如 `gpt-4`
- `time_range` (可选): 时间范围，支持：
  - `today`: 今天 0 点以来
  - `7d`: 过去 7 天（默认）
  - `30d`: 过去 30 天
  - `all`: 全部历史数据
- `bucket` (可选): 时间粒度，当前仅支持 `minute`
- `transport` (可选): 传输模式过滤：
  - `http`: 仅统计 HTTP 调用
  - `sdk`: 仅统计 SDK 调用
  - `all` (默认): 统计所有模式
- `is_stream` (可选): 流式过滤：
  - `true`: 仅统计流式调用
  - `false`: 仅统计非流式调用
  - `all` (默认): 统计所有调用

**响应**:
```json
{
  "provider_id": "openai",
  "logical_model": "gpt-4",
  "time_range": "7d",
  "bucket": "minute",
  "transport": "all",
  "is_stream": "all",
  "points": [
    {
      "window_start": "2025-12-03T10:00:00Z",
      "total_requests": 120,
      "success_requests": 115,
      "error_requests": 5,
      "latency_avg_ms": 120.5,
      "latency_p95_ms": 250.0,
      "latency_p99_ms": 350.0,
      "error_rate": 0.0417
    }
  ]
}
```

**错误响应**:
- 400: 不支持的 bucket 等参数
- 500: 查询指标失败

---

### 5.2 获取 Provider 路由指标汇总

**接口**: `GET /metrics/providers/summary`

**描述**: 获取指定 Provider + 逻辑模型在给定时间范围内的汇总指标，可用于仪表卡片展示（总请求数、错误率、平均延迟等）。

**认证**: API 密钥

**查询参数**:
- `provider_id` (必填): 厂商 ID，例如 `openai`
- `logical_model` (必填): 逻辑模型 ID，例如 `gpt-4`
- `time_range` (可选): 时间范围，支持 `today`、`7d`、`30d`、`all`，语义同上
- `transport` (可选): 传输模式过滤（同上）
- `is_stream` (可选): 流式过滤（同上）
- `user_id` (可选): 若提供，则仅统计该用户下的调用
- `api_key_id` (可选): 若提供，则仅统计该 API Key 下的调用

**响应**:
```json
{
  "provider_id": "openai",
  "logical_model": "gpt-4",
  "time_range": "7d",
  "transport": "all",
  "is_stream": "all",
  "user_id": null,
  "api_key_id": null,
  "total_requests": 1234,
  "success_requests": 1200,
  "error_requests": 34,
  "error_rate": 0.0275,
  "latency_avg_ms": 110.3
}
```

**错误响应**:
- 500: 查询指标失败

---

### 5.3 按用户汇总路由指标

**接口**: `GET /metrics/users/summary`

**描述**: 按 `user_id` 聚合指定时间范围内的路由指标，跨 Provider 与 Logical Model，用于查看某个用户在系统中的整体使用情况。

**认证**: API 密钥

**查询参数**:
- `user_id` (必填): 用户 ID（UUID）
- `time_range` (可选): 时间范围，支持：
  - `today`: 今天 0 点以来
  - `7d`: 过去 7 天（默认）
  - `30d`: 过去 30 天
  - `all`: 全部历史数据
- `transport` (可选): 传输模式过滤：
  - `http`: 仅统计 HTTP 调用
  - `sdk`: 仅统计 SDK 调用
  - `all` (默认): 统计所有模式
- `is_stream` (可选): 流式过滤：
  - `true`: 仅统计流式调用
  - `false`: 仅统计非流式调用
  - `all` (默认): 统计所有调用

**响应**:
```json
{
  "user_id": "uuid",
  "time_range": "7d",
  "transport": "all",
  "is_stream": "all",
  "total_requests": 1234,
  "success_requests": 1200,
  "error_requests": 34,
  "error_rate": 0.0275,
  "latency_avg_ms": 110.3
}
```

**错误响应**:
- 500: 查询指标失败

---

### 5.4 按 API Key 汇总路由指标

**接口**: `GET /metrics/api-keys/summary`

**描述**: 按 `api_key_id` 聚合指定时间范围内的路由指标，跨 Provider 与 Logical Model，用于查看某个 API Key 的整体使用情况（例如单个调用方的额度统计）。

**认证**: API 密钥

**查询参数**:
- `api_key_id` (必填): API Key ID（UUID）
- `time_range` (可选): 时间范围，支持：
  - `today`: 今天 0 点以来
  - `7d`: 过去 7 天（默认）
  - `30d`: 过去 30 天
  - `all`: 全部历史数据
- `transport` (可选): 传输模式过滤：
  - `http`: 仅统计 HTTP 调用
  - `sdk`: 仅统计 SDK 调用
  - `all` (默认): 统计所有模式
- `is_stream` (可选): 流式过滤：
  - `true`: 仅统计流式调用
  - `false`: 仅统计非流式调用
  - `all` (默认): 统计所有调用

**响应**:
```json
{
  "api_key_id": "uuid",
  "time_range": "7d",
  "transport": "all",
  "is_stream": "all",
  "total_requests": 1234,
  "success_requests": 1200,
  "error_requests": 34,
  "error_rate": 0.0275,
  "latency_avg_ms": 110.3
}
```

**错误响应**:
- 500: 查询指标失败

---

> 提示：当客户端使用带有 `allowed_provider_ids` 限制的 API 密钥访问 `/models` 或聊天接口时，
> 实际可用的模型和路由候选 Provider 会根据该密钥允许的 `provider_id` 自动过滤。

### 6. 获取用户可用的提供商列表（私有 + 公共）

**接口**: `GET /users/{user_id}/providers`

**描述**: 获取用户可用的所有提供商列表，包括用户的私有提供商和系统的公共提供商。

**认证**: JWT 令牌

**查询参数**:
- `visibility` (可选): 过滤可见性
  - `all`: 全部可用（默认）
  - `private`: 仅私有提供商
  - `public`: 仅公共提供商

**响应**:
```json
{
  "private_providers": [
    {
      "id": "uuid",
      "provider_id": "my-openai-proxy",
      "name": "我的 OpenAI 代理",
      "base_url": "https://my-proxy.com",
      "provider_type": "native",
      "transport": "http",
      "sdk_vendor": null,
      "visibility": "private",
      "owner_id": "uuid",
      "status": "healthy",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ],
  "public_providers": [
    {
      "id": "uuid",
      "provider_id": "openai",
      "name": "OpenAI",
      "base_url": "https://api.openai.com",
      "provider_type": "native",
      "transport": "http",
      "sdk_vendor": null,
      "visibility": "public",
      "owner_id": null,
      "status": "healthy",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ],
  "total": 2
}
```

**错误响应**:
- 403: 无权查看其他用户的提供商列表

---

### 7. 获取用户私有提供商列表

**接口**: `GET /users/{user_id}/private-providers`

**描述**: 获取指定用户的所有私有提供商，仅该用户本人或超级管理员可访问。

**认证**: JWT 令牌

**响应**:
```json
[
  {
    "id": "uuid",
    "provider_id": "string",
    "name": "string",
    "base_url": "url",
    "provider_type": "native/aggregator",
    "transport": "http/sdk",
    "sdk_vendor": "openai/google/claude 或 null",
    "preset_id": "string | null",
    "visibility": "private",
    "owner_id": "uuid",
    "status": "healthy/degraded/down",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

---

### 8. 创建用户私有提供商

**接口**: `POST /users/{user_id}/private-providers`

**描述**: 为指定用户创建新的私有提供商，仅该用户的 API Key 可以选择使用。

**认证**: JWT 令牌  
**权限要求**:
- 只能为自己创建（除非是超级管理员）  
- 需要具备 `create_private_provider` 权限  
- 受系统配置或用户权限中的私有提供商数量上限限制

**请求体（核心字段）**:
```json
{
  "name": "string (1-100字符)",
  "base_url": "url",
  "api_key": "string",
  "provider_type": "native 或 aggregator (可选, 默认native)",
  "transport": "http 或 sdk (可选, 默认http)",
  "sdk_vendor": "openai/google/claude (当 transport=sdk 时必填)"
  // 其余可选字段: weight, region, cost_input, cost_output, max_qps,
  // retryable_status_codes, custom_headers,
  // models_path, messages_path, chat_completions_path, responses_path,
  // static_models, supported_api_styles
}
```
> 说明：`provider_id` 由系统自动根据用户与厂商信息生成，无需在请求体中提供。

**响应**:
```json
{
  "id": "uuid",
  "provider_id": "string",
  "name": "string",
  "base_url": "url",
  "provider_type": "native/aggregator",
  "transport": "http/sdk",
   "sdk_vendor": "openai/google/claude 或 null",
   "preset_id": "string | null",
  "visibility": "private",
  "owner_id": "uuid",
  "status": "healthy",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**错误响应**:
- 403: 无权为其他用户创建私有提供商或没有创建权限  
- 403: 已达到私有提供商数量限制  
- 400: provider_id 已存在

---

### 9. 更新用户私有提供商

**接口**: `PUT /users/{user_id}/private-providers/{provider_id}`

**描述**: 更新用户私有提供商的基础配置（不允许修改 provider_id）。

**认证**: JWT 令牌

**请求体**:
```json
{
  "name": "string (可选)",
  "base_url": "url (可选)",
  "provider_type": "native/aggregator (可选)",
  "transport": "http/sdk (可选)",
  "sdk_vendor": "openai/google/claude (可选；当 transport 变更为 sdk 时建议显式设置)",
  "weight": 1.0,
  "region": "string | null",
  "cost_input": 0.0,
  "cost_output": 0.0,
  "max_qps": 1000,
  "retryable_status_codes": [429, 500, 502, 503, 504],
  "custom_headers": { "Header-Name": "value" },
  "models_path": "/v1/models",
  "messages_path": "/v1/message",
  "chat_completions_path": "/v1/chat/completions",
  "responses_path": "/v1/responses",
  "static_models": [ /* 可选的静态模型配置 */ ],
  "supported_api_styles": ["openai", "responses", "claude"]
}
```

**响应**: 同 “创建用户私有提供商”。

**错误响应**:
- 404: Private provider 不存在  
- 403: 无权修改其他用户的私有提供商

---

### 10. 删除用户私有提供商

**接口**: `DELETE /users/{user_id}/private-providers/{provider_id}`

**描述**: 删除用户的私有提供商。

**认证**: JWT 令牌

**成功响应**: 204 No Content

**错误响应**:
- 403: 无权删除其他用户的私有提供商
- 404: 私有提供商不存在

---

### 11. 用户提交共享提供商

**接口**: `POST /providers/submissions`

**描述**: 用户提交一个新的共享提供商，经过管理员审核后可加入全局提供商池。

**认证**: JWT 令牌  
**权限要求**: 需要具备 `submit_shared_provider` 权限

**请求体**:
```json
{
  "name": "string (1-100字符)",
  "provider_id": "string (1-50字符, 作为全局 provider_id)",
  "base_url": "url",
  "provider_type": "native 或 aggregator (可选, 默认native)",
  "api_key": "string",
  "description": "string (可选, 最长约2000字符)",
  "extra_config": {
    // 可选扩展配置，如自定义 header、模型路径等
  }
}
```

**响应**:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "string",
  "provider_id": "string",
  "base_url": "url",
  "provider_type": "native/aggregator",
  "description": "string | null",
  "approval_status": "pending",
  "reviewed_by": null,
  "review_notes": null,
  "reviewed_at": null,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**错误响应**:
- 403: 当前用户未被授权提交共享提供商  
- 400: 提供商配置验证失败（如无法访问 /models）

---

### 12. 管理员查看共享提供商提交

**接口**: `GET /providers/submissions?status=pending|approved|rejected`

**描述**: 管理员查看所有用户提交的共享提供商。

**认证**: JWT 令牌 (仅限超级用户)

**响应**:
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "name": "string",
    "provider_id": "string",
    "base_url": "url",
    "provider_type": "native/aggregator",
    "description": "string | null",
    "approval_status": "pending/approved/rejected",
    "reviewed_by": "uuid | null",
    "review_notes": "string | null",
    "reviewed_at": "datetime | null",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

---

### 13. 管理员审核共享提供商提交

**接口**: `PUT /providers/submissions/{submission_id}/review`

**描述**: 管理员审核用户提交的共享提供商。通过后会自动创建对应的全局 Provider。

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "approved": true,
  "review_notes": "string (可选)"
}
```

**响应**:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "string",
  "provider_id": "string",
  "base_url": "url",
  "provider_type": "native/aggregator",
  "description": "string | null",
  "approval_status": "approved/rejected",
  "reviewed_by": "uuid | null",
  "review_notes": "string | null",
  "reviewed_at": "datetime | null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**错误响应**:
- 404: 提交记录不存在  
- 403: 需要管理员权限

---

### 14. 管理员查看 Provider 列表（含可见性/所有者）

**接口**: `GET /admin/providers`

**描述**: 管理员查看所有 Provider 列表，可按可见性和所有者过滤。

**认证**: JWT 令牌 (仅限超级用户)

**查询参数**:
- `visibility` (可选): `public` / `private` / `restricted`  
- `owner_id` (可选): 指定所有者用户 ID

**响应**:
```json
{
  "providers": [
    {
      "id": "uuid",
      "provider_id": "string",
      "name": "string",
      "base_url": "url",
      "provider_type": "native/aggregator",
      "transport": "http/sdk",
      "visibility": "public/private/restricted",
      "owner_id": "uuid | null",
      "status": "healthy/degraded/down",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ],
  "total": 1
}
```

---

### 15. 管理员更新 Provider 可见性

**接口**: `PUT /admin/providers/{provider_id}/visibility`

**描述**: 管理员更新指定 Provider 的可见性（例如从 private 提升为 public）。

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "visibility": "public | private | restricted"
}
```

**响应**: 与管理员 Provider 列表中的单条 Provider 结构相同。

**错误响应**:
- 404: Provider 不存在  
- 403: 需要管理员权限

---

## 逻辑模型管理

### 1. 获取逻辑模型列表

**接口**: `GET /logical-models`

**描述**: 获取所有存储在 Redis 中的逻辑模型。

**认证**: API密钥

**响应**:
```json
{
  "models": [
    {
      "logical_id": "string",
      "name": "string",
      "description": "string",
      "enabled": true,
      "capabilities": ["text_completion", "chat_completion"],
      "default_strategy": "string",
      "upstreams": [
        {
          "provider_id": "string",
          "model_id": "string",
          "region": "string | null",
          "cost_input": 0.0,
          "cost_output": 0.0,
          "enabled": true,
          "weight": 1.0
        }
      ],
      "metadata": {}
    }
  ],
  "total": 1
}
```

---

### 2. 获取逻辑模型详情

**接口**: `GET /logical-models/{logical_model_id}`

**描述**: 获取指定逻辑模型的详情。

**认证**: API密钥

**响应**:
```json
{
  "logical_id": "string",
  "name": "string",
  "description": "string",
  "enabled": true,
  "capabilities": ["text_completion", "chat_completion"],
  "default_strategy": "string",
  "upstreams": [
    {
      "provider_id": "string",
      "model_id": "string",
      "region": "string | null",
      "cost_input": 0.0,
      "cost_output": 0.0,
      "enabled": true,
      "weight": 1.0
    }
  ],
  "metadata": {}
}
```

**错误响应**:
- 404: 逻辑模型不存在

---

### 3. 获取逻辑模型上游

**接口**: `GET /logical-models/{logical_model_id}/upstreams`

**描述**: 获取映射到逻辑模型的上游物理模型。

**认证**: API密钥

**响应**:
```json
{
  "upstreams": [
    {
      "provider_id": "string",
      "model_id": "string",
      "region": "string | null",
      "cost_input": 0.0,
      "cost_output": 0.0,
      "enabled": true,
      "weight": 1.0
    }
  ]
}
```

**错误响应**:
- 404: 逻辑模型不存在

---

## 路由管理

### 1. 路由决策

**接口**: `POST /routing/decide`

**描述**: 计算逻辑模型请求的路由决策。

**认证**: API密钥

**请求体**:
```json
{
  "logical_model": "string",
  "conversation_id": "string (可选, 用于粘性会话)",
  "user_id": "string (可选, 暂未使用)",
  "preferred_region": "string (可选, 首选上游选择的区域)",
  "strategy": "latency_first/cost_first/reliability_first/balanced (可选)",
  "exclude_providers": ["string"] (可选, 要排除的提供商ID列表)
}
```

**响应**:
```json
{
  "logical_model": "string",
  "selected_upstream": {
    "provider_id": "string",
    "model_id": "string",
    "region": "string | null",
    "cost_input": 0.0,
    "cost_output": 0.0,
    "enabled": true,
    "weight": 1.0
  },
  "decision_time": 10.0,
  "reasoning": "string",
  "alternative_upstreams": [],
  "strategy_used": "string",
  "all_candidates": [
    {
      "upstream": {
        "provider_id": "string",
        "model_id": "string",
        "region": "string | null",
        "cost_input": 0.0,
        "cost_output": 0.0,
        "enabled": true,
        "weight": 1.0
      },
      "score": 0.99,
      "metrics": {
        "logical_model": "string",
        "provider_id": "string",
        "success_rate": 0.99,
        "avg_latency_ms": 100,
        "p95_latency_ms": 200,
        "p99_latency_ms": 300,
        "last_success": 1234567890.0,
        "last_failure": 1234567890.0,
        "consecutive_failures": 0,
        "total_requests": 1000,
        "total_failures": 10,
        "window_start": 1234567890.0,
        "window_duration": 300.0
      }
    }
  ]
}
```

**错误响应**:
- 404: 逻辑模型不存在
- 503: 没有可用的上游
- 503: 逻辑模型已禁用

---

## 会话管理

### 1. 获取会话信息

**接口**: `GET /routing/sessions/{conversation_id}`

**描述**: 获取会话信息。

**认证**: API密钥

**响应**:
```json
{
  "conversation_id": "string",
  "logical_model": "string",
  "provider_id": "string",
  "model_id": "string",
  "created_at": 1234567890.0,
  "last_used_at": 1234567890.0
}
```

**错误响应**:
- 404: 会话不存在

---

### 2. 删除会话

**接口**: `DELETE /routing/sessions/{conversation_id}`

**描述**: 删除会话（取消粘性）。

**认证**: API密钥

**成功响应**: 204 No Content

**错误响应**:
- 404: 会话不存在

---

## 系统管理

### 1. 生成系统主密钥

**接口**: `POST /system/secret-key/generate`

**描述**: 生成系统主密钥。

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "length": 64 (可选, 范围32-256, 默认64)
}
```

**响应**:
```json
{
  "secret_key": "string"
}
```

**错误响应**:
- 403: 只有超级管理员可以生成系统密钥
- 500: 生成密钥失败

---

### 2. 初始化系统管理员

**接口**: `POST /system/admin/init`

**描述**: 初始化系统管理员账户。

**请求体**:
```json
{
  "username": "string (3-50字符)",
  "email": "string",
  "display_name": "System Administrator (可选)"
}
```

**响应**:
```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "api_key": "string"
}
```

**错误响应**:
- 400: 系统已有用户或初始化失败
- 500: 初始化失败

---

### 3. 轮换系统主密钥

**接口**: `POST /system/secret-key/rotate`

**描述**: 轮换系统主密钥（警告：这将使所有现有的密码哈希和API密钥失效！）。

**认证**: JWT 令牌 (仅限超级用户)

**响应**:
```json
{
  "secret_key": "string"
}
```

**错误响应**:
- 403: 只有超级管理员可以轮换系统密钥
- 500: 轮换密钥失败

---

### 4. 验证密钥强度

**接口**: `POST /system/key/validate`

**描述**: 验证密钥强度。

**请求体**:
```json
{
  "key": "string"
}
```

**响应**:
```json
{
  "is_valid": true/false,
  "message": "string"
}
```

---

### 5. 获取系统 Provider 限制配置

**接口**: `GET /system/provider-limits`

**描述**: 获取与提供商相关的系统级配额与审核配置。

**认证**: JWT 令牌 (仅限超级用户)

**响应**:
```json
{
  "default_user_private_provider_limit": 3,
  "max_user_private_provider_limit": 20,
  "require_approval_for_shared_providers": true
}
```

---

### 6. 更新系统 Provider 限制配置

**接口**: `PUT /system/provider-limits`

**描述**: 更新与提供商相关的系统级配额与审核配置（仅当前进程内生效，重启后以环境变量为准）。

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "default_user_private_provider_limit": 3,
  "max_user_private_provider_limit": 20,
  "require_approval_for_shared_providers": true
}
```

**响应**: 同 “获取系统 Provider 限制配置”。

**错误响应**:
- 400: 默认上限大于最大上限  
- 403: 只有超级管理员可以更新提供商限制配置

---

### 7. 获取系统状态

**接口**: `GET /system/status`

**描述**: 获取系统状态。

**认证**: JWT 令牌 (仅限超级用户)

**响应**:
```json
{
  "status": "healthy",
  "message": "系统运行正常"
}
```

**错误响应**:
- 403: 只有超级管理员可以查看系统状态

---

## 认证方式

### JWT 令牌认证

对于需要 JWT 令牌认证的 API，需要在请求头中添加：

```
Authorization: Bearer {access_token}
```

### API 密钥认证

对于需要 API 密钥认证的 API，需要在请求头中添加：

```
X-API-Key: {api_key}
```

---

## 错误响应格式

所有错误响应都遵循以下格式：

```json
{
  "detail": "错误描述"
}
```

---

## 响应状态码

- `200 OK`: 请求成功
- `201 Created`: 资源创建成功
- `204 No Content`: 请求成功，无内容返回
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 未认证
- `403 Forbidden`: 无权限
- `404 Not Found`: 资源不存在
- `429 Too Many Requests`: 请求频率超限
- `500 Internal Server Error`: 服务器内部错误
- `503 Service Unavailable`: 服务不可用
