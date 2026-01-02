# Admin Memory（系统记忆审核/发布）API

> 说明：本组接口用于管理员（`require_superuser`）对 **system scope** 的 Qdrant 记忆进行候选列表、审核发布与手动创建。
>
> 重要：管理员在 Dashboard 操作时通常只有 **JWT 登录态**，但 Embedding 调用必须走网关的标准管道（路由/配额/审计），因此 **需要显式提供 `project_id`（即 API Key ID）** 来作为“调用上下文”。

## 鉴权
- 需要 JWT，并且用户必须是超级管理员（superuser）。

## 为什么 Create/Approve 需要 `project_id`？
Embedding 通过 `app/services/embedding_service.py:embed_text()` 复用 `RequestHandler`，而 `RequestHandler` 的路由/配额/审计逻辑依赖 `AuthenticatedAPIKey`（即项目上下文）。  
因此管理员在后台执行 “创建系统知识 / 审核通过（可能触发重新 embedding）” 时，必须显式选择使用哪个项目（API Key）上下文来完成该次 embedding 调用。

## 接口

### 1) 列出待审核候选
`GET /v1/admin/memories/candidates`

Query：
- `limit`：1~100
- `offset`：可选，分页游标

返回：`AdminMemoryListResponse`

### 2) 列出已发布（已审核）内容
`GET /v1/admin/memories/published`

Query：
- `limit`：1~100
- `offset`：可选，分页游标

返回：`AdminMemoryListResponse`

### 3) 审核通过候选（可选编辑内容）
`POST /v1/admin/memories/{point_id}/approve`

Body：`AdminMemoryApproveRequest`
- `project_id`：必填，用于本次 embedding 的项目上下文（API Key ID）
- `content`：可选，修正后的内容；若内容发生变化会触发重新 embedding
- `categories`：可选
- `keywords`：可选

返回：`AdminMemoryItemResponse`

### 4) 手动创建并直接发布系统记忆
`POST /v1/admin/memories`

Body：`AdminMemoryCreateRequest`
- `project_id`：必填，用于本次 embedding 的项目上下文（API Key ID）
- `content`：必填
- `categories`：可选
- `keywords`：可选

返回：`AdminMemoryItemResponse`

### 5) 删除系统记忆（候选/已发布都可）
`DELETE /v1/admin/memories/{point_id}`

返回：204

