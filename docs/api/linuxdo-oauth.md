# LinuxDo OAuth 接入说明

本文档描述后端新增的 LinuxDo Connect OAuth 登录能力及相关 API。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `LINUXDO_OAUTH_ENABLED` | 是否启用 LinuxDo OAuth，默认 `false` |
| `LINUXDO_CLIENT_ID` | 在 Connect.Linux.Do 申请的 Client ID |
| `LINUXDO_CLIENT_SECRET` | 对应的 Client Secret |
| `LINUXDO_REDIRECT_URI` | LinuxDo 回调地址（通常指向前端 `/callback` 页面） |
| `LINUXDO_AUTHORIZE_ENDPOINT` | 授权端点，默认 `https://connect.linux.do/oauth2/authorize` |
| `LINUXDO_TOKEN_ENDPOINT` | Token 端点，默认 `https://connect.linux.do/oauth2/token` |
| `LINUXDO_USERINFO_ENDPOINT` | 用户信息端点，默认 `https://connect.linux.do/api/user` |

## 流程概览

1. 前端请求 `GET /auth/oauth/linuxdo/authorize`，服务端生成 `state` 并重定向到 LinuxDo 授权页面。
2. 用户完成授权后回到前端 `/callback` 页面，前端将 `code` 和 `state` POST 到 `/auth/oauth/callback`。
3. 后端校验 `state`、用授权码交换 access token，并从 LinuxDo 拉取用户信息。
4. 若用户首次登录则会视为“注册”，必须处于管理员配置的注册窗口内才能创建账号并关联 `Identity` 记录；若窗口为人工审核模式（`auto_activate=false`），账号会创建成功但不签发 JWT，需要管理员激活后才能登录。
5. 若用户已存在（已有 `Identity` 绑定），则不受注册窗口限制，直接签发本地 JWT。

## API 详情

### GET `/auth/oauth/linuxdo/authorize`

- **说明**：生成授权 URL 并 307 重定向到 LinuxDo。
- **响应**：`307 Temporary Redirect`，`Location` 指向 LinuxDo 授权页，包含 `client_id`、`redirect_uri`、`state` 等参数。
- **错误**：
  - `503 Service Unavailable`：OAuth 未启用或配置不完整。

### POST `/auth/oauth/callback`

- **请求体**

```json
{
  "code": "授权码",
  "state": "state 参数"
}
```

- **响应**

```json
{
  "access_token": "jwt-access",
  "refresh_token": "jwt-refresh",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "username": "linuxdo-user",
    "email": "928374@linux.do",
    "display_name": "LinuxDo 昵称",
    "avatar": "https://cdn.example.com/avatar/240.png",
    "is_active": true,
    "is_superuser": false,
    "role_codes": ["default_user"],
    "permission_flags": [],
    "created_at": "2025-01-01T12:34:56+00:00",
    "updated_at": "2025-01-01T12:34:56+00:00"
  }
}
```

- **错误**：
  - `400 Bad Request`：`state` 缺失或无效、授权码为空等。
  - `403 Forbidden`：当前未开放注册窗口/注册时间已结束/名额耗尽（首次登录）；或账号已创建但需要管理员激活（人工审核窗口）。
  - `502 Bad Gateway`：LinuxDo token / 用户信息接口返回异常。
  - `503 Service Unavailable`：OAuth 未启用或配置缺失。

## 账户同步策略

- 以 LinuxDo `id` 作为外部唯一标识，写入 `identities` 表（`provider=linuxdo`）。
- 若用户不存在，自动创建账号，邮箱统一为 `<id>@linux.do`，用户名优先使用 LinuxDo `username`。
- 自动创建积分账户并授予默认角色。
- 每次登录会刷新头像、昵称和 `is_active` 状态，保持与 LinuxDo 同步。

## 前端配合要点

- 在跳转授权页面前调用 `oauthRedirect.save()` 保持意图页面。
- `/callback` 页面获取 `code` 和 `state`，POST 至 `/auth/oauth/callback` 后存储返回的 JWT。
- 发生错误时根据响应 `detail` 展示提示并引导回登录页。
