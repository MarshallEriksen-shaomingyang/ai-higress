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
- [通知](#通知)
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
  "requires_manual_activation": false,
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

**说明**:
- 当当前窗口为人工审核模式时，成功响应会携带 `is_active=false` 且 `requires_manual_activation=true`，表示账号创建成功但需管理员审核后才能登录，前端不应自动登录，应提示“待人工审核”。
- `role_codes` 默认包含 `default_user`，权限能力标记根据角色与用户权限计算。

---

### 1.1 定时开放注册管理（管理员）

**接口**:

- `POST /admin/registration-windows/auto`：创建一个自动激活的注册窗口。
- `POST /admin/registration-windows/manual`：创建一个需要手动激活的注册窗口。
- `GET /admin/registration-windows/active`：查看当前正在生效的注册窗口（没有时返回 `null`）。
- `POST /admin/registration-windows/{window_id}/close`：立即关闭指定的注册窗口（仅管理员）。

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
- `close` 接口会将窗口状态置为 `closed`，后续注册将直接返回 403。

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

### 3. 上传当前用户头像

**接口**: `POST /users/me/avatar`

**描述**: 为当前登录用户上传并更新头像图片。

**认证**: JWT 令牌

**请求**:

- Content-Type: `multipart/form-data`
- 表单字段：

| 字段名 | 类型        | 必填 | 说明                                      |
|--------|-------------|------|-------------------------------------------|
| file   | binary file | 是   | 头像图片文件，支持 PNG/JPEG/WebP 等常见格式 |

**行为说明**:

- 头像文件会暂时保存到本地磁盘目录（由环境变量 `AVATAR_LOCAL_DIR` 控制，默认 `backend/media/avatars`）；
- 数据库中 `users.avatar` 字段只保存相对路径 / 对象 key，例如：`"<user_id>/<uuid>.png"`；
- 对外返回的 `avatar` 字段为前端可直接访问的完整 URL：
  - 如果配置了 `AVATAR_OSS_BASE_URL`，则为：`<AVATAR_OSS_BASE_URL>/<key>`；
  - 否则为：`<GATEWAY_API_BASE_URL>/<AVATAR_LOCAL_BASE_URL>/<key>`，默认等价于 `http://localhost:8000/media/avatars/<key>`；当未显式配置网关地址或仍使用默认 localhost 时，会优先使用当前请求的 base_url（包含 `X-Forwarded-Proto`/`Host`）来拼接，避免返回错误域名。

**响应**:

成功时返回更新后的用户信息，结构与 `GET /users/me` 相同：

```json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "display_name": "string | null",
  "avatar": "string | null", // 完整头像访问 URL
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

### 4. 搜索用户

**接口**: `GET /users/search`

**描述**: 根据关键字（邮箱 / 用户名 / 昵称）或一组用户 ID 查询可分享的用户列表，返回精简信息，便于前端在“私有分享”等场景中进行选择。

**认证**: JWT 令牌

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `q` | string | 否 | 搜索关键字，支持模糊匹配邮箱、用户名、昵称，至少 1 个字符 |
| `ids` | string[] (UUID) | 否 | 直接按用户 ID 精确查询，可重复提供多个 `ids` 参数 |
| `limit` | int | 否 | 返回条数，默认 10，最大 50；仅对 `q` 搜索生效 |

> `q` 和 `ids` 至少需要提供其中之一。

**响应**:
```json
[
  {
    "id": "uuid",
    "username": "string",
    "email": "string",
    "display_name": "string | null"
  }
]
```

**错误响应**:
- 400: 未提供 `q` 或 `ids`

---

### 5. 更新用户信息

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

### 6. 更新用户状态

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

### 7. 管理员获取用户列表

**接口**: `GET /admin/users`

**描述**: 管理员获取系统中所有用户的概要信息，用于用户管理页面。

**认证**: JWT 令牌 (仅限超级用户)

**说明**:
- `credit_auto_topup`：该用户的自动充值规则（结构同 `GET /v1/credits/admin/users/{user_id}/auto-topup` 的成功响应）；未配置时为 `null`。

**响应**:
```json
[
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
    "credit_auto_topup": {
      "id": "uuid",
      "user_id": "uuid",
      "min_balance_threshold": 100,
      "target_balance": 200,
      "is_active": true,
      "created_at": "datetime",
      "updated_at": "datetime"
    },
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

---

### 8. 管理员获取用户权限列表

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

### 9. 管理员授予或更新用户权限

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

### 10. 管理员撤销用户权限

**接口**: `DELETE /admin/users/{user_id}/permissions/{permission_id}`

**描述**: 管理员撤销用户的一条权限记录。

**认证**: JWT 令牌 (仅限超级用户)

**成功响应**: 204 No Content

---

### 11. 超级管理员管理角色与权限（RBAC）

以下接口仅面向超级管理员 (`is_superuser = true`)，用于通过“角色 + 权限”集中管理用户能力。  
权限判断统一走后端的 `UserPermissionService.has_permission(user_id, permission_code)`，会综合：
- `is_superuser`
- 用户直挂权限 `user_permissions.permission_type`
- 用户所属角色上的权限 `permissions.code`

#### 11.1 查询权限定义列表

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

#### 11.2 查询角色列表

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

#### 11.3 创建角色

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

#### 11.4 更新角色

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

#### 11.5 删除角色

**接口**: `DELETE /admin/roles/{role_id}`

**描述**: 删除一个角色，会级联删除该角色上的权限绑定和用户角色绑定。

**认证**: JWT 令牌 (仅限超级用户)

**成功响应**: 204 No Content

**注意**: 删除角色不会删除 `permissions` 中的权限定义，也不会影响用户直挂的 `user_permissions`。

---

#### 11.6 查询角色已绑定的权限

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

#### 11.7 设置角色的权限列表（全量覆盖）

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

#### 11.8 查询用户当前角色列表

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

#### 11.9 为用户设置角色列表（全量覆盖）

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
- `POST /v1/images/generations`

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

> 额外说明：若某个逻辑模型的上游仅配置为 `responses` 风格（即仅支持 Responses API），
> 则通过 `POST /v1/chat/completions` 调用该模型可能返回 `400 Bad Request`，
> 提示“该模型仅支持 Responses API，请使用 /responses 入口调用”。此时请改用 `POST /v1/responses`。
>
> 说明：当 `stream=true` 或请求头 `Accept: text/event-stream` 触发流式响应时，若在开始推流前发生可预判错误
> （例如模型不可用、或仅支持 `/responses` 入口），网关仍会返回常规的 `4xx` JSON 错误体（而不是 SSE）。

---

## 图像生成（文生图）

### 1. 生成图片

**接口**: `POST /v1/images/generations`

**描述**: OpenAI 兼容的文生图接口（固定对外为 OpenAI Images API 格式），根据 `model` 自动选择上游链路：
- OpenAI 系模型（如 `gpt-image-*` / `dall-e-*`）：走 OpenAI-compatible Provider 的 `/v1/images/generations`；
- Google 系模型：
  - Gemini 原生出图（如 `gemini-*-*-image` / `*-flash-image` / `nano-banana`）：走 Gemini API `generateContent`（`v1beta/models/{model}:generateContent`）并将结果转换为 OpenAI Images 响应结构（从 `candidates[].content.parts[].inlineData.data` 提取 base64）。
  - Imagen 专用模型（如 `imagen-3.*` / `imagen-4.*`）：走 Gemini API 的 `predict`（`v1beta/models/{model}:predict`），并将 `predictions[].bytesBase64Encoded` 转换为 OpenAI Images 响应结构。

> 配置提示：当 Provider 的 `base_url` 配置为 `https://generativelanguage.googleapis.com` 时，网关会按 Gemini/Imagen 原生 API 调用；
> 其他 `base_url` 会被视为 OpenAI-compatible Provider（走 `/v1/images/generations`）。

**认证**: API Key（`Authorization: Bearer <token>`）

**返回字段说明**:
- 当 `response_format="b64_json"`：`data[*].b64_json` 返回 base64 图片；
- 当 `response_format="url"`：
  - 若配置了对象存储（`IMAGE_STORAGE_PROVIDER` + `IMAGE_OSS_*`），网关会把图片写入对应存储（默认阿里 OSS，也可 S3/R2 兼容），并返回网关域名下的签名短链 URL（`/media/images/...`）；
  - 若未配置 OSS，网关会退化为 `data:image/...;base64,...` 的 Data URL（兼容前端直接渲染）。
- `extra_body`（可选）：网关保留扩展字段，用于透传上游厂商高级参数（避免网关 schema 落后导致能力缺失）。
  - `extra_body.openai`：在 OpenAI lane 下合并到上游请求体（覆盖同名字段）。
  - `extra_body.google`：在 Google lane 下合并到上游请求体（覆盖同名字段）。
    - Gemini `generateContent`：通常透传 `generationConfig` / `contents` 等字段。
    - Imagen `predict`：通常透传 `parameters`（如 `sampleCount`/`aspectRatio`/`imageSize`/`personGeneration` 等）或高级能力开关。

> 兼容性提示：网关当前不会把上游 `stream=true` 的 SSE 直接透传给调用方（会导致 JSON 解析失败），请使用 Chat 的 SSE 方案（`/v1/conversations/{conversation_id}/image-generations`）获得更好的等待体验。

**请求体（示例）**:
```json
{
  "prompt": "A cute cat, studio lighting",
  "model": "gpt-image-1",
  "n": 1,
  "size": "1024x1024",
  "response_format": "b64_json"
}
```

**请求体（示例：Google lane 透传高级参数）**:
```json
{
  "prompt": "A futuristic city in cyberpunk style",
  "model": "gemini-3-pro-image-preview",
  "n": 1,
  "size": "1792x1024",
  "response_format": "url",
  "extra_body": {
    "google": {
      "generationConfig": {
        "imageConfig": {"aspectRatio": "16:9"}
      }
    }
  }
}
```

**请求体（示例：Imagen predict 透传 parameters）**:
```json
{
  "prompt": "Robot holding a red skateboard",
  "model": "imagen-4.0-generate-001",
  "n": 4,
  "response_format": "b64_json",
  "extra_body": {
    "google": {
      "parameters": {
        "sampleCount": 4,
        "aspectRatio": "16:9",
        "imageSize": "2K"
      }
    }
  }
}
```

**响应（示例）**:
```json
{
  "created": 1700000000,
  "data": [
    {
      "b64_json": "BASE64_IMAGE_DATA",
      "revised_prompt": "A cute cat, studio lighting"
    }
  ]
}
```



### 2. 短链图片读取（签名 URL）

当 `POST /v1/images/generations` 返回的 `data[*].url` 为网关短链（`/media/images/...`）时，
该 URL 可在有效期内直接访问图片内容（无需登录/无需 API Key）。

**接口**: `GET /media/images/{object_key}`

**描述**: 通过签名短链获取 OSS 私有桶图片对象的预签名下载地址（网关返回 302 跳转，直下）。

**认证**: 无（通过签名参数校验）

**查询参数**:
- `expires` (int, 必填): 过期时间戳（Unix seconds）
- `sig` (string, 必填): HMAC 签名

**成功响应**: `302 Found`，响应头 `Location` 为 OSS 预签名 GET URL；客户端跟随跳转后由 OSS 返回图片二进制内容（`Content-Type` 为 `image/png`/`image/jpeg`/`image/webp` 等）

### 计费规则

网关在记录一次 LLM 调用的 usage 时，会根据 token 用量和配置计算本次应扣的积分：

- Provider 模型单价：`provider_models.pricing` JSON 中的 `input`/`output`（单位：每 1000 tokens 所需积分）。  
  - 只有配置了对应 Provider + 模型的价格，系统才会扣费；  
  - 未设置价格时视为该模型暂不计费，只记录调用流水。  
- 模型倍率：`ModelBillingConfig.multiplier`，按模型或逻辑模型 ID 设置，例如：
  - `gpt-4o-mini` = 0.5  
  - `gpt-4o` = 2.0  
- Provider 结算系数：`Provider.billing_factor`，按具体 Provider 细化成本：
  - 默认 `1.0`，代表基准成本；
  - >1.0 表示该 Provider 更贵（同模型下会多扣积分）；
  - <1.0 表示该 Provider 更便宜或只收少量服务费（例如用户自建 Provider）。

综合起来，单次调用的积分消耗为：

```text
input_cost = (prompt_tokens / 1000) * pricing.input
output_cost = (completion_tokens / 1000) * pricing.output
fallback_cost = (total_tokens / 1000) * (pricing.output or pricing.input)
raw_cost = (input_cost + output_cost) if usage 拆分了输入/输出 else fallback_cost
cost_credits = ceil(raw_cost * ModelBillingConfig.multiplier * Provider.billing_factor)
```

> 注：平台不再按照 `CREDITS_BASE_PER_1K_TOKENS` 做统一折算，也不会在未配置价格时扣积分。

#### 流式请求预扣（可选）

默认情况下系统不会对流式调用做预扣费（`ENABLE_STREAMING_PRECHARGE=false`），
只会在收到上游 usage 后才生成 `usage`/`stream_usage` 流水。
若希望在流式响应开始前先按 `max_tokens` 或 `STREAMING_MIN_TOKENS`
估算一笔 `stream_estimate` 扣费，可在环境变量中将
`ENABLE_STREAMING_PRECHARGE` 设为 `true`。预扣同样依赖 `provider_models.pricing`
（若未配置单价则跳过），并继续叠加模型倍率和 Provider 结算系数。

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
    "provider_id": "openai",
    "provider_model_id": "gpt-4o-mini",
    "input_tokens": 500,
    "output_tokens": 300,
    "total_tokens": 800,
    "created_at": "2025-01-02T12:34:56Z"
  }
]
```

### 2.1 查询积分消耗概览

**接口**: `GET /v1/credits/me/consumption/summary`  
**认证**: JWT 令牌  
**描述**: 针对当前用户在指定时间范围内的积分消耗做聚合分析，方便仪表盘展示「本期总消耗」「环比」「预计可用天数」等指标。

**查询参数**:
- `time_range` (`today`/`7d`/`30d`/`90d`/`all`，默认 `30d`)

**响应示例**:
```json
{
  "time_range": "30d",
  "start_at": "2025-01-01T00:00:00Z",
  "end_at": "2025-01-31T23:59:59Z",
  "spent_credits": 420,
  "spent_credits_prev": 300,
  "transactions": 58,
  "avg_daily_spent": 14,
  "balance": 1280,
  "projected_days_left": 91.4
}
```

字段说明：
- `spent_credits`：统计窗口内扣除的积分总和（仅统计 `usage`/`stream_usage`/`stream_estimate` 等消费型流水）；
- `spent_credits_prev`：上一对比周期的消耗（`time_range=all` 时为 `null`）；
- `avg_daily_spent`：按窗口长度折算的日均消耗；
- `projected_days_left`：若保持当前日均消耗，预计可用天数，适合做“余额可用 X 天”提示。

### 2.2 查询 Provider 消耗排行

**接口**: `GET /v1/credits/me/consumption/providers`  
**认证**: JWT 令牌  
**描述**: 统计当前用户在不同 Provider 上的积分消耗，帮助识别哪些上游占用了最多预算。

**查询参数**:
- `time_range`（同上，默认 `30d`）
- `limit`（默认 6，范围 1-50）：返回的 Provider 数量，按消耗降序。

**响应示例**:
```json
{
  "time_range": "30d",
  "total_spent": 420,
  "items": [
    {
      "provider_id": "openai",
      "provider_name": "OpenAI",
      "total_spent": 300,
      "transaction_count": 40,
      "percentage": 0.714,
      "last_transaction_at": "2025-01-31T20:10:00Z"
    },
    {
      "provider_id": "anthropic",
      "provider_name": "Anthropic",
      "total_spent": 120,
      "transaction_count": 18,
      "percentage": 0.286,
      "last_transaction_at": "2025-01-29T18:02:00Z"
    }
  ]
}
```

### 2.3 查询积分消耗时间序列

**接口**: `GET /v1/credits/me/consumption/timeseries`  
**认证**: JWT 令牌  
**描述**: 以日期为粒度返回积分消耗时间序列，可用于概览页折线图 / 柱状图。

**查询参数**:
- `time_range`（同上，默认 `30d`）
- `bucket`（目前仅支持 `day`）
- `max_points`（默认 90，范围 10-365）：限制返回的最大点数。

**响应示例**:
```json
{
  "time_range": "30d",
  "bucket": "day",
  "points": [
    { "window_start": "2025-01-29T00:00:00Z", "spent_credits": 40 },
    { "window_start": "2025-01-30T00:00:00Z", "spent_credits": 55 },
    { "window_start": "2025-01-31T00:00:00Z", "spent_credits": 38 }
  ]
}
```

---

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

### 4. 管理员配置每日自动充值

**接口 1**: `GET /v1/credits/admin/users/{user_id}/auto-topup`  
**认证**: JWT 令牌（仅限超级管理员）  
**描述**: 查询指定用户当前的自动充值配置。若未配置则返回 `null`。

**响应示例**:
```json
{
  "id": "f3b1c1a0-1234-5678-9abc-def012345678",
  "user_id": "2b5c9290-9d2e-4c9f-a9b8-0123456789ab",
  "min_balance_threshold": 100,
  "target_balance": 200,
  "is_active": true,
  "created_at": "2025-01-02T12:34:56Z",
  "updated_at": "2025-01-02T12:34:56Z"
}
```

**接口 2**: `PUT /v1/credits/admin/users/{user_id}/auto-topup`  
**认证**: JWT 令牌（仅限超级管理员）  
**描述**: 为指定用户创建或更新自动充值规则。

**请求体**:
```json
{
  "min_balance_threshold": 100,
  "target_balance": 200,
  "is_active": true
}
```

字段说明：
- `min_balance_threshold`：当用户余额 **低于** 该值时触发自动充值；
- `target_balance`：自动充值后希望达到的余额（必须大于 `min_balance_threshold`）；
- `is_active`：是否启用该规则。

**成功响应**: 返回最新的自动充值配置，结构同 `GET` 接口。

**接口 3**: `DELETE /v1/credits/admin/users/{user_id}/auto-topup`  
**认证**: JWT 令牌（仅限超级管理员）  
**描述**: 禁用指定用户的自动充值规则。若规则不存在则视为幂等成功。  
**成功响应**: `204 No Content`

### 5. 管理员批量配置自动充值

**接口**: `POST /v1/credits/admin/auto-topup/batch`  
**认证**: JWT 令牌（仅限超级管理员）  
**描述**: 为一批用户一次性创建或更新相同的自动充值规则。常用于“将多名用户加入同一自动充值策略”。

**请求体**:
```json
{
  "user_ids": [
    "2b5c9290-9d2e-4c9f-a9b8-0123456789ab",
    "8e2fbe90-1234-5678-9abc-def012345678"
  ],
  "min_balance_threshold": 100,
  "target_balance": 200,
  "is_active": true
}
```

**响应示例**:
```json
{
  "updated_count": 2,
  "configs": [
    {
      "id": "f3b1c1a0-1234-5678-9abc-def012345678",
      "user_id": "2b5c9290-9d2e-4c9f-a9b8-0123456789ab",
      "min_balance_threshold": 100,
      "target_balance": 200,
      "is_active": true,
      "created_at": "2025-01-02T12:34:56Z",
      "updated_at": "2025-01-02T12:34:56Z"
    }
  ]
}
```

校验规则与单用户接口一致：
- `user_ids` 必须为非空列表；
- `target_balance` 必须大于 `min_balance_threshold`；
- 仅超级管理员可调用。

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

**认证**: JWT 令牌

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
    "messages_path": "/v1/messages",
    "chat_completions_path": "/v1/chat/completions",
    "responses_path": "/v1/responses 或 null",
    "images_generations_path": "/v1/images/generations 或 null",
    "weight": 1.0,
    "region": "string | null",
    "cost_input": 0.0,
    "cost_output": 0.0,
    "billing_factor": 1.0,
    "max_qps": 1000,
    "custom_headers": {},
    "retryable_status_codes": [429, 500, 502, 503, 504],
    "static_models": [],
    "transport": "http/sdk/claude_cli",
    "provider_type": "native/aggregator",
    "sdk_vendor": "string | null（参见 /providers/sdk-vendors，例如 openai/google/claude/vertexai）",
    "supported_api_styles": ["openai", "responses", "claude"] 或 null
  }
],
  "total": 1
}
```

> 说明：
> - 当 `transport = "sdk"` 时，必须在后台配置 `sdk_vendor`，其值需来自 `/providers/sdk-vendors` 返回列表（例如 `openai/google/claude/vertexai`），网关才会走对应官方 SDK；
> - 当 `sdk_vendor = "vertexai"` 时，建议将 `api_key` 填写为 GCP 服务账号 JSON（将被加密存储）；网关会优先使用该 JSON 中的 `project_id`，并从 `base_url` 推断 `location`（如 `https://us-central1-aiplatform.googleapis.com/`），否则回退到环境变量 `VERTEXAI_PROJECT/GOOGLE_CLOUD_PROJECT` 与 `VERTEXAI_LOCATION/GOOGLE_CLOUD_LOCATION`；
> - 当 `transport = "http"` 时，`sdk_vendor` 一律为 `null`，表示纯 HTTP 代理模式；
> - 当 `transport = "claude_cli"` 时，网关会伪装成 Claude Code CLI 客户端，自动添加 CLI 特有的请求头、生成 user_id、转换消息格式，并使用 TLS 指纹伪装技术。适用于需要 Claude CLI 特征的 API 端点。

---

### 1.1 获取已注册的 SDK 厂商列表

**接口**: `GET /providers/sdk-vendors`

**描述**: 返回后端当前注册的 SDK 厂商枚举，前端表单可据此动态渲染选项。

**认证**: JWT 令牌

**响应**:
```json
{
  "vendors": ["openai", "google", "claude", "vertexai"],
  "total": 4
}
```

---

### 2. 获取指定提供商信息

**接口**: `GET /providers/{provider_id}`

**描述**: 获取指定提供商的配置信息。

**认证**: JWT 令牌

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
  "messages_path": "/v1/messages",
  "chat_completions_path": "/v1/chat/completions",
  "responses_path": "/v1/responses 或 null",
  "images_generations_path": "/v1/images/generations 或 null",
  "weight": 1.0,
  "region": "string | null",
  "cost_input": 0.0,
  "cost_output": 0.0,
  "billing_factor": 1.0,
  "max_qps": 1000,
  "custom_headers": {},
  "retryable_status_codes": [429, 500, 502, 503, 504],
  "static_models": [],
  "transport": "http/sdk/claude_cli",
  "provider_type": "native/aggregator",
  "sdk_vendor": "openai/google/claude/vertexai 或 null",
  "supported_api_styles": ["openai", "responses", "claude"] 或 null
}
```

**错误响应**:
- 404: 提供商不存在

---

### 3. 获取提供商模型列表

**接口**: `GET /providers/{provider_id}/models`

**描述**: 获取指定提供商支持的模型列表。

**认证**: JWT 令牌

**响应**:
```json
{
  "models": [
    {
      "id": "string",
      "object": "string",
      "created": 1234567890,
      "owned_by": "string",
      "alias": "string (optional, logical alias such as \"claude-sonnet-4-5\")",
      "disabled": "boolean (optional, true 表示该 Provider 下该模型已被禁用)"
    }
  ],
  "total": 1
}
```

**错误响应**:
- 404: 提供商不存在
- 502: 上游模型发现失败（例如上游 `/models` 返回 404/5xx、超时，或 Provider 未配置可用的 `static_models` 回退）

502 错误体示例：
```json
{
  "detail": {
    "error": "provider_models_discovery_failed",
    "message": "无法获取该 Provider 的模型列表：上游 /models 返回 404。请检查 base_url/models_path 是否正确，或配置 static_models 以跳过远端发现。",
    "code": 502,
    "details": {
      "provider_id": "provider-models-upstream-404",
      "upstream_status_code": 404,
      "upstream_url": "https://upstream.example.com/openai/v1/models"
    }
  }
}
```

---

### 4. 获取提供商健康状态

**接口**: `GET /providers/{provider_id}/health`

**描述**: 返回最近一次探针/巡检写入的健康状态（DB + Redis 缓存）；接口本身不会对上游发起请求。

> 兼容说明  
> - 若 Provider 记录存在但尚未执行过健康检查（没有 `last_check`），接口仍然返回 `200`，并根据当前 Provider 状态字段返回一个默认健康状态；  
> - 仅当 Provider 记录本身不存在时才会返回 `404`。

**认证**: JWT 令牌

**响应**:
```json
{
  "provider_id": "string",
  "status": "healthy/degraded/down",
  "timestamp": 1234567890.0,
  "response_time_ms": 42.0,
  "error_message": null,
  "last_successful_check": 1234567890.0
}
```

**错误响应**:
- 404: 提供商不存在

---

### 3.1 管理单个模型的别名映射

> 仅限：超级管理员或该私有 Provider 的所有者。

**接口（获取）**: `GET /providers/{provider_id}/models/{model_id}/mapping`  
**描述**: 获取指定 provider+model 的别名映射配置，用于将上游的长模型 ID 映射为更短、更稳定的逻辑名称。  
**认证**: JWT 令牌  

**响应示例**:
```json
{
  "provider_id": "claude-official",
  "model_id": "claude-sonnet-4-5-20250929",
  "alias": "claude-sonnet-4-5"
}
```

当尚未为该模型配置别名时，`alias` 字段为 `null`。

**接口（更新）**: `PUT /providers/{provider_id}/models/{model_id}/mapping`  
**描述**: 为指定 provider+model 设置或清除别名映射。  
**认证**: JWT 令牌  

**请求体**:
```json
{
  "alias": "claude-sonnet-4-5"
}
```

行为说明：
- `alias` 为非空字符串时：将请求体中的值设置为该物理模型的别名；
- `alias` 为 `null` 或空字符串时：清除当前别名映射；
- 同一 Provider 下，别名必须唯一，否则返回 400 错误。

**错误响应**:
- 400: 别名与同一 Provider 下其它模型冲突；
- 403: 当前用户无权修改该 Provider 的模型配置；
- 404: Provider 不存在。

---

### 3.2 管理单个模型的禁用状态

> 仅限：超级管理员或该私有/受限 Provider 的所有者。

当某个 provider+model 被禁用后：
- 该模型不会参与聊天路由选择；
- 网关的 `/models` 聚合列表也不会包含该模型；
- 若调用方仍请求该模型，且在当前可用 provider 范围内已无任何可路由的候选，上游会返回 `400`，并提示“该模型已被禁用”。

**接口（获取）**: `GET /providers/{provider_id}/models/{model_id}/disabled`  
**认证**: JWT 令牌  

**响应示例**:
```json
{
  "provider_id": "my-private-provider",
  "model_id": "gpt-4o",
  "disabled": true
}
```

**接口（更新）**: `PUT /providers/{provider_id}/models/{model_id}/disabled`  
**认证**: JWT 令牌  

**请求体**:
```json
{
  "disabled": true
}
```

**错误响应**:
- 403: 当前用户无权修改该 Provider 的模型配置；
- 404: Provider 不存在。

---

### 3.3 管理单个模型的能力（capabilities）

> 仅限：超级管理员或该私有/受限 Provider 的所有者。

当上游 `/models` 未正确声明模型能力（例如把文生图挂在 chat 接口、或缺少 `image_generation` 标记）时，可在网关侧为单个 provider+model 配置能力覆盖。

**接口（获取）**: `GET /providers/{provider_id}/models/{model_id}/capabilities`  
**认证**: JWT 令牌  

**响应示例**:
```json
{
  "provider_id": "my-private-provider",
  "model_id": "nano-banana-pro",
  "capabilities": ["chat", "image_generation"]
}
```

**接口（更新）**: `PUT /providers/{provider_id}/models/{model_id}/capabilities`  
**认证**: JWT 令牌  

**请求体**:
```json
{
  "capabilities": ["chat", "image_generation"]
}
```

支持的能力值：
- `chat`
- `completion`
- `embedding`
- `vision`
- `audio`
- `function_calling`
- `image_generation`

**错误响应**:
- 403: 当前用户无权修改该 Provider 的模型配置；
- 404: Provider 不存在；
- 422: capabilities 包含未知枚举值或为空。

---

### 5. 获取提供商路由指标（实时快照）

**接口**: `GET /providers/{provider_id}/metrics`

**描述**: 获取提供商的路由指标实时快照（来自 Redis，按逻辑模型聚合）。

**认证**: JWT 令牌

**查询参数**:
- `logical_model` (可选): 逻辑模型过滤器
  - 若提供，则返回该 Provider 在指定逻辑模型下的指标（最多一条）
  - 若不提供，则返回该 Provider 在所有逻辑模型下的指标列表

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
    },
    {
      "logical_model": "gpt-3.5-turbo",
      "provider_id": "openai",
      "latency_p95_ms": 150.0,
      "latency_p99_ms": 280.0,
      "error_rate": 0.01,
      "success_qps_1m": 5.2,
      "total_requests_1m": 315,
      "last_updated": 1733212345.123,
      "status": "healthy"
    }
  ]
}
```

**说明**:
- 当不提供 `logical_model` 参数时，返回该 Provider 在所有逻辑模型下的指标
- 如果该 Provider 没有任何路由指标数据，返回空数组 `[]`

**错误响应**:
- 404: 提供商不存在

---

### 5.1 获取 Provider 路由指标时间序列（按分钟）

**接口**: `GET /metrics/providers/timeseries`

**描述**: 获取指定 Provider + 逻辑模型在给定时间范围内的分钟级指标时间序列，可用于绘制折线图。

**认证**: JWT 令牌

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

**认证**: JWT 令牌

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

**认证**: JWT 令牌

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

**认证**: JWT 令牌

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

### 6. 获取用户可用的提供商列表（私有 + 授权 + 公共）

**接口**: `GET /users/{user_id}/providers`

**描述**: 获取用户可用的所有提供商列表，包括用户的私有提供商、被授权的受限（restricted）提供商以及系统的公共提供商。

**认证**: JWT 令牌

**查询参数**:
- `visibility` (可选): 过滤可见性
  - `all`: 全部可用（默认）
  - `private`: 仅私有提供商
  - `shared`: 仅被授权的提供商（visibility=restricted）
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
      "shared_user_ids": ["other-user-uuid"],
      "status": "healthy",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ],
  "shared_providers": [
    {
      "id": "uuid",
      "provider_id": "friend-provider",
      "name": "好友共享的 Provider",
      "base_url": "https://friend.example.com",
      "provider_type": "native",
      "transport": "http",
      "sdk_vendor": null,
      "visibility": "restricted",
      "owner_id": "owner-uuid",
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
    "transport": "http/sdk/claude_cli",
    "sdk_vendor": "openai/google/claude/vertexai 或 null",
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
  "transport": "http 或 sdk 或 claude_cli (可选, 默认http)",
  "sdk_vendor": "openai/google/claude/vertexai (当 transport=sdk 时必填)"
  // 其余可选字段: weight, region, cost_input, cost_output, max_qps,
  // retryable_status_codes, custom_headers,
  // models_path, messages_path, chat_completions_path, responses_path, images_generations_path,
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
  "transport": "http/sdk/claude_cli",
   "sdk_vendor": "openai/google/claude/vertexai 或 null",
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
  "transport": "http/sdk/claude_cli (可选)",
  "sdk_vendor": "openai/google/claude/vertexai (可选；当 transport 变更为 sdk 时建议显式设置)",
  "weight": 1.0,
  "region": "string | null",
  "cost_input": 0.0,
  "cost_output": 0.0,
  "max_qps": 1000,
  "retryable_status_codes": [429, 500, 502, 503, 504],
  "custom_headers": { "Header-Name": "value" },
  "models_path": "/v1/models",
  "messages_path": "/v1/messages",
  "chat_completions_path": "/v1/chat/completions",
  "responses_path": "/v1/responses",
  "images_generations_path": "/v1/images/generations",
  "static_models": [ /* 可选的静态模型配置 */ ],
  "supported_api_styles": ["openai", "responses", "claude"]
}
```
> 注意：部分上游（尤其是某些代理/私有部署）可能不提供 `GET /v1/models` 或 `GET /models`，会返回 `404`。  
> 这类场景请显式设置 `models_path` 为对方支持的模型列表路径，或直接配置 `static_models` 让网关跳过远端模型发现（否则动态路由/按模型自动匹配会受影响）。

**响应**: 同 “创建用户私有提供商”。

**错误响应**:
- 404: Private provider 不存在  
- 403: 无权修改其他用户的私有提供商

---

#### 9.1 查询/更新私有分享用户列表

**接口（查询）**: `GET /users/{user_id}/private-providers/{provider_id}/shared-users`  
**接口（更新）**: `PUT /users/{user_id}/private-providers/{provider_id}/shared-users`

**描述**: 查看或设置该私有 Provider 授权给哪些用户使用（可见性自动切换为 `restricted`）。仅支持 Provider 拥有者或超级管理员。

**认证**: JWT 令牌

**更新请求体**:
```json
{
  "user_ids": ["uuid", "uuid2"] // 留空表示仅自己可见，visibility 将恢复为 private
}
```

**响应**（查询/更新一致）:
```json
{
  "provider_id": "my-openai-proxy",
  "visibility": "restricted",
  "shared_user_ids": ["uuid", "uuid2"]
}
```

**错误响应**:
- 404: Private provider 不存在  
- 403: 无权管理其他用户的私有提供商  

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

### 11.0 从私有提供商一键提交共享提供商

**接口**: `POST /users/{user_id}/private-providers/{provider_id}/submit-shared`

**描述**: 将指定用户的私有 Provider 一键提交到共享池，进入管理员审核流程。  
后端会自动读取该私有 Provider 的配置和上游 API 密钥进行一次连通性验证（调用 `/v1/models` 等），验证通过后创建提交记录。

**认证**: JWT 令牌  
**权限要求**: 需要具备 `submit_shared_provider` 权限，且仅允许本人或超级管理员操作。

**请求体**: 无（后端从私有 Provider 记录中提取所需信息）

**响应**: 同 “用户提交共享提供商” (`POST /providers/submissions`)：
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
- 403: 当前用户未被授权提交共享提供商 / 无权操作其他用户的私有提供商  
- 404: 私有提供商不存在  
- 400:  
  - 当前私有提供商未配置可用的上游 API 密钥  
  - 提供商配置验证失败（如无法访问 /models）

---

### 11.1 用户探针任务（真实对话探针）

**说明**：用户可在自己的私有 Provider 下创建探针任务，系统会按设定频率对上游发起一次极小的“真实对话请求”（而不是请求 `/models`），并记录响应结果供前端展示；同时会把结果写入 Provider 的健康状态（DB + Redis 缓存），因此 `GET /providers/{provider_id}/health` 也会反映该探针的最新结果。  
**注意**：探针会消耗上游额度与资源，服务端会限制最低频率与最大 `max_tokens`。

#### 11.1.1 列出探针任务

**接口**: `GET /users/{user_id}/private-providers/{provider_id}/probe-tasks`

**认证**: JWT 令牌（仅本人或超级管理员）

**响应**:
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "provider_id": "string",
    "name": "string",
    "model_id": "string",
    "prompt": "string",
    "interval_seconds": 300,
    "max_tokens": 16,
    "api_style": "auto/openai/claude/responses",
    "enabled": true,
    "in_progress": false,
    "last_run_at": "datetime | null",
    "next_run_at": "datetime | null",
    "last_run": {
      "id": "uuid",
      "task_id": "uuid",
      "user_id": "uuid",
      "provider_id": "string",
      "model_id": "string",
      "api_style": "string",
      "success": true,
      "status_code": 200,
      "latency_ms": 123,
      "error_message": null,
      "response_text": "string | null",
      "response_excerpt": "string | null",
      "response_json": {}
    },
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

#### 11.1.2 创建探针任务

**接口**: `POST /users/{user_id}/private-providers/{provider_id}/probe-tasks`

**请求体**:
```json
{
  "name": "string",
  "model_id": "string",
  "prompt": "string",
  "interval_seconds": 300,
  "max_tokens": 16,
  "api_style": "auto/openai/claude/responses",
  "enabled": true
}
```

**响应**: 同 “列出探针任务” 中单个元素结构。

**错误响应**:
- 400: 参数非法（如 interval_seconds 过低、prompt 过长、max_tokens 过大等）
- 404: 私有 Provider 不存在
- 403: 无权操作其他用户的私有 Provider

#### 11.1.3 更新探针任务

**接口**: `PUT /users/{user_id}/private-providers/{provider_id}/probe-tasks/{task_id}`

**请求体**（均可选）:
```json
{
  "name": "string",
  "model_id": "string",
  "prompt": "string",
  "interval_seconds": 600,
  "max_tokens": 16,
  "api_style": "auto/openai/claude/responses",
  "enabled": true
}
```

**响应**: 同 “列出探针任务” 中单个元素结构。

#### 11.1.4 删除探针任务

**接口**: `DELETE /users/{user_id}/private-providers/{provider_id}/probe-tasks/{task_id}`

**成功响应**: 204 No Content

#### 11.1.5 立即执行一次探针

**接口**: `POST /users/{user_id}/private-providers/{provider_id}/probe-tasks/{task_id}/run`

**请求体**: 空对象 `{}`（或不传）

**说明**:
- 该接口用于“一次性连通性/可用性检查”，不要求任务必须处于启用状态。
- 当任务 `enabled=false` 时也允许手动运行一次；接口不会修改任务的 `enabled`，也不会为其生成后续调度（即不会开启自动执行）。

**响应**:
```json
{
  "id": "uuid",
  "task_id": "uuid",
  "user_id": "uuid",
  "provider_id": "string",
  "model_id": "string",
  "api_style": "string",
  "success": true,
  "status_code": 200,
  "latency_ms": 123,
  "error_message": null,
  "response_text": "pong",
  "response_excerpt": "{...}",
  "response_json": {}
}
```

#### 11.1.6 查看探针执行记录

**接口**: `GET /users/{user_id}/private-providers/{provider_id}/probe-tasks/{task_id}/runs?limit=20`

**响应**: `UserProbeRunResponse[]`（同 11.1.5 的结构）。

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
- 400: provider_id 已存在或提供商配置验证失败（如无法访问 /models）

---

### 11.1 用户查看自己的共享提供商提交

**接口**: `GET /providers/submissions/me`

**描述**: 当前登录用户查看自己提交的共享提供商列表。

**认证**: JWT 令牌

**查询参数**:
- `status` (可选): `pending` / `approved` / `rejected`，按审批状态过滤

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
- 400: provider_id 已存在或提交已无法再次审批  
- 404: 提交记录不存在  
- 403: 需要管理员权限

---

### 13.1 用户取消自己的共享提供商提交

**接口**: `DELETE /providers/submissions/{submission_id}`

**描述**: 当前登录用户取消自己的共享提供商提交记录。

根据提交状态执行不同的操作：
- `pending`: 直接删除提交记录
- `approved`: 删除对应的公共 Provider 和提交记录
- `rejected`: 直接删除提交记录

**认证**: JWT 令牌

**成功响应**: 204 No Content

**错误响应**:
- 404: 提交记录不存在  
- 403: 无权取消他人的提交

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
      "transport": "http/sdk/claude_cli",
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

### 16. 管理员导出提供商预设

**接口**: `GET /admin/provider-presets/export`

**描述**: 导出当前所有官方提供商预设，便于批量备份或迁移。返回值中的 `presets` 字段可直接作为导入接口的输入。

**认证**: JWT 令牌 (仅限超级用户)

**响应示例**:
```json
{
  "presets": [
    {
      "preset_id": "openai",
      "display_name": "OpenAI",
      "description": "官方 OpenAI 预设",
      "provider_type": "native",
      "transport": "http",
      "sdk_vendor": null,
      "base_url": "https://api.openai.com",
      "models_path": "/v1/models",
      "messages_path": "/v1/messages",
      "chat_completions_path": "/v1/chat/completions",
      "responses_path": null,
      "images_generations_path": null,
      "supported_api_styles": ["openai"],
      "retryable_status_codes": [429, 500],
      "custom_headers": {"X-Test": "1"},
      "static_models": [{"id": "gpt-4o"}]
    }
  ],
  "total": 1
}
```

---

### 17. Provider 审核与运营（管理员）

**状态字段**:  
- `audit_status`: `pending/testing/approved/approved_limited/rejected`  
- `operation_status`: `active/paused/offline`  
- 管理端列表与详情的响应已补充 `latest_test_result`（最近一次测试的摘要）。
 - 可查询最近测试与审核日志：`GET /admin/providers/{id}/tests`、`GET /admin/providers/{id}/audit-logs`（仅管理员）。

**接口**: `POST /admin/providers/{provider_id}/test`  
**描述**: 触发一次基础探针或自定义测试，立即写入测试记录并返回摘要。  
**请求体**:
```json
{
  "mode": "auto | custom | cron",
  "remark": "可选备注",
  "input_text": "当 mode=custom 时的测试输入，可选"
}
```
**响应示例**:
```json
{
  "id": "uuid",
  "provider_id": "audit-provider",
  "mode": "auto",
  "success": true,
  "summary": "基础探针完成",
  "probe_results": [
    {"case": "ping", "status": "success", "latency_ms": 120}
  ],
  "latency_ms": 120,
  "error_code": null,
  "cost": 0.0,
  "started_at": "2025-12-09T08:00:00Z",
  "finished_at": "2025-12-09T08:00:00Z",
  "created_at": "2025-12-09T08:00:00Z",
  "updated_at": "2025-12-09T08:00:00Z"
}
```

**审核流转接口**:  
- `POST /admin/providers/{provider_id}/approve`：审核通过  
- `POST /admin/providers/{provider_id}/approve-limited`：限速通过，`limit_qps` 可选  
- `POST /admin/providers/{provider_id}/reject`：拒绝，`remark` 必填  
- `POST /admin/providers/{provider_id}/pause`：运营状态标记为 `paused`  
- `POST /admin/providers/{provider_id}/resume`：恢复为 `active`  
- `POST /admin/providers/{provider_id}/offline`：下线为 `offline`
- `PUT /admin/providers/{provider_id}/probe-config`：更新自动探针配置（`probe_enabled`/`probe_interval_seconds`/`probe_model`）

请求体（除 test 外通用）:
```json
{
  "remark": "审核或运维备注，可选；拒绝时必填",
  "limit_qps": 2
}
```

**自动化巡检**: 系统会以较低频率自动探针（默认待审核 30 分钟一次、已上线 60 分钟一次），失败会将运营状态标记为 `paused` 并记录日志。可通过环境变量调整：
- `PROVIDER_AUDIT_AUTO_PROBE_INTERVAL_SECONDS`（默认 1800）
- `PROVIDER_AUDIT_CRON_INTERVAL_SECONDS`（默认 3600）
- 管理员可按 Provider 单独关闭探针、设置自定义频率或指定测试模型，避免过于频繁占用用户上游额度。
- `probe_prompt` 为预留字段：系统管理员可在 `/system/gateway-config` 配置以便将来复用，但当前版本的自动探针不会读取该提示词向上游发起请求。

---

### 18. 管理员导入提供商预设

**接口**: `POST /admin/provider-presets/import`

**描述**: 批量导入官方提供商预设。默认跳过已存在的同名预设，传入 `overwrite=true` 可覆盖更新。

**认证**: JWT 令牌 (仅限超级用户)

**请求体**:
```json
{
  "overwrite": false,
  "presets": [
    {
      "preset_id": "openai",
      "display_name": "OpenAI",
      "provider_type": "native",
      "transport": "http",
      "base_url": "https://api.openai.com",
      "models_path": "/v1/models",
      "messages_path": "/v1/messages",
      "chat_completions_path": "/v1/chat/completions",
      "responses_path": null,
      "images_generations_path": null,
      "supported_api_styles": ["openai"],
      "retryable_status_codes": [429],
      "custom_headers": null,
      "static_models": []
    }
  ]
}
```

**响应示例**:
```json
{
  "created": ["claude"],
  "updated": ["openai"],
  "skipped": [],
  "failed": [
    {
      "preset_id": "bad-preset",
      "reason": "preset_id 已存在"
    }
  ]
}
```

---

## 逻辑模型管理

### 1. 获取逻辑模型列表

**接口**: `GET /logical-models`

**描述**: 获取所有存储在 Redis 中的逻辑模型。

**查询参数**:
- `project_id` (UUID，可选)：指定项目（API Key）时，仅返回该项目允许的 Provider 下可访问的逻辑模型；未指定则按用户可访问的 Provider 过滤。

**认证**: JWT 令牌

**响应**:
```json
{
  "models": [
    {
      "logical_id": "string",
      "display_name": "string",
      "description": "string",
      "enabled": true,
      "capabilities": ["chat", "completion", "image_generation"],
      "strategy": {
        "name": "balanced",
        "description": "Default routing strategy",
        "alpha": 0.3,
        "beta": 0.3,
        "gamma": 0.2,
        "delta": 0.2,
        "min_score": 0.1,
        "enable_stickiness": true,
        "stickiness_ttl": 7200
      },
      "upstreams": [
        {
          "provider_id": "string",
          "model_id": "string",
          "endpoint": "string",
          "base_weight": 1.0,
          "region": "string | null",
          "max_qps": 0,
          "meta_hash": "string | null",
          "updated_at": 0.0,
          "api_style": "openai"
        }
      ],
      "updated_at": 0.0
    }
  ],
  "total": 1
}
```

---

### 2. 获取逻辑模型详情

**接口**: `GET /logical-models/{logical_model_id}`

**描述**: 获取指定逻辑模型的详情。

**查询参数**:
- `project_id` (UUID，可选)：指定项目（API Key）时，仅返回该项目允许的 Provider 下可访问的上游；若无可访问上游将返回 404。

**认证**: JWT 令牌

**响应**:
```json
{
  "logical_id": "string",
  "display_name": "string",
  "description": "string",
  "enabled": true,
  "capabilities": ["chat", "completion", "image_generation"],
  "strategy": {
    "name": "balanced",
    "description": "Default routing strategy",
    "alpha": 0.3,
    "beta": 0.3,
    "gamma": 0.2,
    "delta": 0.2,
    "min_score": 0.1,
    "enable_stickiness": true,
    "stickiness_ttl": 7200
  },
  "upstreams": [
    {
      "provider_id": "string",
      "model_id": "string",
      "endpoint": "string",
      "base_weight": 1.0,
      "region": "string | null",
      "max_qps": 0,
      "meta_hash": "string | null",
      "updated_at": 0.0,
      "api_style": "openai"
    }
  ],
  "updated_at": 0.0
}
```

**错误响应**:
- 404: 逻辑模型不存在

---

### 3. 获取逻辑模型上游

**接口**: `GET /logical-models/{logical_model_id}/upstreams`

**描述**: 获取映射到逻辑模型的上游物理模型。

**查询参数**:
- `project_id` (UUID，可选)：指定项目（API Key）时，仅返回该项目允许的 Provider 下可访问的上游；若无可访问上游将返回 404。

**认证**: JWT 令牌

**响应**:
```json
{
  "upstreams": [
    {
      "provider_id": "string",
      "model_id": "string",
      "endpoint": "string",
      "base_weight": 1.0,
      "region": "string | null",
      "max_qps": 0,
      "meta_hash": "string | null",
      "updated_at": 0.0,
      "api_style": "openai"
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

**认证**: JWT 令牌

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

**认证**: JWT 令牌

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

**认证**: JWT 令牌

**成功响应**: 204 No Content

**错误响应**:
- 404: 会话不存在

---

## 通知

### 1. 获取当前用户通知列表

**接口**: `GET /v1/notifications`

**描述**: 返回当前用户可见的通知，支持 `status=all|unread` 以及分页参数 `limit`/`offset`，按创建时间倒序。

**认证**: JWT 令牌

**请求参数**:
- `status` (query，可选): `all` | `unread`，默认 `all`
- `limit` (query，可选): 返回数量，默认 50，最大 200
- `offset` (query，可选): 起始偏移，默认 0

**响应示例**:
```json
[
  {
    "id": "uuid",
    "title": "系统维护通知",
    "content": "今晚 23:00 维护 15 分钟",
    "level": "warning",
    "target_type": "all",
    "target_user_ids": [],
    "target_role_codes": [],
    "link_url": null,
    "expires_at": null,
    "created_at": "2024-05-01T12:00:00Z",
    "updated_at": "2024-05-01T12:00:00Z",
    "created_by": "uuid",
    "is_active": true,
    "is_read": false,
    "read_at": null
  }
]
```

### 2. 获取未读数量

**接口**: `GET /v1/notifications/unread-count`

**描述**: 返回当前用户未读通知数量。

**认证**: JWT 令牌

**响应**:
```json
{ "unread_count": 3 }
```

### 3. 批量标记为已读

**接口**: `POST /v1/notifications/read`

**描述**: 将指定通知标记为已读；用户只能标记自己可见的通知。

**请求体**:
```json
{ "notification_ids": ["uuid1", "uuid2"] }
```

**响应**:
```json
{ "updated_count": 2 }
```

### 4. 管理员创建通知/公告

**接口**: `POST /v1/admin/notifications`

**描述**: 超级管理员创建通知。`target_type` 支持 `all`（全部用户）或 `users`（指定用户列表）/`roles`（指定角色 codes）。

**字段说明**:
- `title` (必填): 通知标题，<=200 字符
- `content` (必填): 通知正文
- `level`: `info` | `success` | `warning` | `error`，默认 `info`
- `target_type`: `all` | `users` | `roles`
  - 当为 `users` 时需传 `target_user_ids`（UUID 数组）
  - 当为 `roles` 时需传 `target_role_codes`（角色 code 数组）
- `link_url` (可选): 点击通知的跳转链接
- `expires_at` (可选): 过期后不再展示

**请求体示例**:
```json
{
  "title": "系统升级",
  "content": "23:00 - 23:15 期间暂停服务",
  "level": "warning",
  "target_type": "users",
  "target_user_ids": ["uuid-of-user-a"],
  "expires_at": "2024-05-02T00:00:00Z"
}
```

**响应**: 返回通知详情（同上，含 `is_active` 字段）。

### 5. 管理员查询通知列表

**接口**: `GET /v1/admin/notifications`

**描述**: 管理员按创建时间倒序查看通知，支持 `limit`/`offset` 分页。

**认证**: JWT 令牌（仅超级管理员）

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
  "password": "string"
}
```

> 初始化仅返回管理员凭据，不再自动生成 API Key。请使用上述用户名/密码登录后，再在 API Key 管理页手动创建密钥。

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

### 8. 获取中转网关配置

**接口**: `GET /system/gateway-config`

**描述**: 获取当前中转网关的基础配置信息，供前端首页或文档页面展示给最终用户查看。

说明：`probe_prompt` 为预留字段（将来 health 全局扩展备用），当前版本不生效。

**认证**: JWT 令牌（任何已登录用户均可访问）

**响应**:
```json
{
  "api_base_url": "https://api.example.com",
  "max_concurrent_requests": 1000,
  "request_timeout_ms": 30000,
  "cache_ttl_seconds": 3600,
  "probe_prompt": "请回答一个简单问题用于健康检查。",
  "metrics_retention_days": 15
}
```

---

### 9. 更新中转网关配置

**接口**: `PUT /system/gateway-config`

**描述**: 更新中转网关的基础配置，并持久化到数据库中。环境变量只在首次创建配置记录时作为默认值使用。

**认证**: JWT 令牌 (仅限超级用户)

说明：`probe_prompt` 为预留字段（将来 health 全局扩展备用），当前版本不生效。

**请求体**:
```json
{
  "api_base_url": "https://api.example.com",
  "max_concurrent_requests": 1000,
  "request_timeout_ms": 30000,
  "cache_ttl_seconds": 3600,
  "probe_prompt": "请回答一个简单问题用于健康检查。",
  "metrics_retention_days": 15
}
```

**响应**: 同 “获取中转网关配置”。

**错误响应**:
- 403: 只有超级管理员可以更新网关配置

---

## 上游代理管理（管理员）

用于管理“上游请求代理池”（HTTP/HTTPS/SOCKS5），支持：
- 管理员在后台配置静态代理或远程代理列表；
- Celery 定时刷新远程列表并对代理测活；
- 聊天/上游请求从 Redis 中随机挑选“已测活可用”的代理；失败会触发冷却，避免短时间内反复使用坏节点。

说明：
- 所有接口均需要 JWT 且仅超级管理员可访问；
- 代理密码、远程列表 URL/headers 等敏感字段会加密存储，接口响应不会返回明文。

### 1. 获取上游代理全局配置

**接口**: `GET /admin/upstream-proxy/config`

**响应**（示例）:
```json
{
  "id": "00000000-0000-0000-0000-000000000000",
  "enabled": true,
  "selection_strategy": "random",
  "failure_cooldown_seconds": 120,
  "healthcheck_url": "https://ipv4.webshare.io/",
  "healthcheck_timeout_ms": 5000,
  "healthcheck_method": "GET",
  "healthcheck_interval_seconds": 300,
  "created_at": "2025-12-12T00:00:00Z",
  "updated_at": "2025-12-12T00:00:00Z"
}
```

### 2. 更新上游代理全局配置

**接口**: `PUT /admin/upstream-proxy/config`

**请求体**（字段均可选）:
```json
{
  "enabled": true,
  "failure_cooldown_seconds": 120,
  "healthcheck_url": "https://ipv4.webshare.io/",
  "healthcheck_timeout_ms": 5000,
  "healthcheck_method": "GET",
  "healthcheck_interval_seconds": 300
}
```

**响应**: 同“获取上游代理全局配置”。

### 3. 代理来源（sources）管理

- **接口**: `GET /admin/upstream-proxy/sources`：列出所有来源
- **接口**: `POST /admin/upstream-proxy/sources`：创建来源（`static_list`/`remote_text_list`）
- **接口**: `PUT /admin/upstream-proxy/sources/{source_id}`：更新来源
- **接口**: `DELETE /admin/upstream-proxy/sources/{source_id}`：删除来源（会级联删除其代理条目）

创建远程来源示例（Webshare 下载列表）：
```json
{
  "name": "webshare",
  "source_type": "remote_text_list",
  "enabled": true,
  "default_scheme": "http",
  "refresh_interval_seconds": 300,
  "remote_url": "https://proxy.webshare.io/api/v2/proxy/list/download/xxxx/-/any/username/direct/-/?plan_id=123"
}
```

### 4. 代理条目（endpoints）管理

- **接口**: `GET /admin/upstream-proxy/endpoints?source_id=...`：列出条目
- **接口**: `POST /admin/upstream-proxy/endpoints`：新增单条代理
- **接口**: `PUT /admin/upstream-proxy/endpoints/{endpoint_id}`：启用/禁用
- **接口**: `DELETE /admin/upstream-proxy/endpoints/{endpoint_id}`：删除
- **接口**: `POST /admin/upstream-proxy/endpoints/import`：批量导入（支持 `ip:port`、`ip:port:user:pass`、完整 URL）

批量导入示例：
```json
{
  "source_id": "00000000-0000-0000-0000-000000000000",
  "default_scheme": "http",
  "text": "142.111.48.253:7030:user:pass\\nhttp://1.2.3.4:8080\\nsocks5://5.6.7.8:1080"
}
```

### 5. 手动触发刷新/测活

- **接口**: `POST /admin/upstream-proxy/tasks/refresh`：触发远程列表刷新（返回 Celery task_id）
- **接口**: `POST /admin/upstream-proxy/tasks/check`：触发代理测活与 Redis 可用池重建（返回 Celery task_id）

### 6. 查看代理池状态

**接口**: `GET /admin/upstream-proxy/status`

**响应**（示例）:
```json
{
  "config_enabled": true,
  "total_sources": 1,
  "total_endpoints": 10,
  "available_endpoints": 8
}
```

---

## 认证方式

### JWT 令牌认证

对于需要 JWT 令牌认证的 API，需要在请求头中添加：

```
Authorization: Bearer {access_token}
```

**重要（生产环境校验规则）**：
- 当 `APP_ENV=production` 时，后端会要求 `access_token` 必须包含 `jti` 且该 token 必须在 Redis 中有登记记录（登录/刷新接口签发的 token 默认满足）。
- 缺少 `jti` 或 Redis 无记录/已撤销时将返回 `401 Unauthorized`，以保证撤销/黑名单/会话控制有效。

### API 密钥认证

对于需要 API 密钥认证的 API，需要在请求头中添加明文 API Key，支持两种写法：

```
Authorization: Bearer {api_key}
# 或
X-API-Key: {api_key}
```

> {api_key} 即创建密钥时返回的字符串，无需再做 Base64 编码。

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
