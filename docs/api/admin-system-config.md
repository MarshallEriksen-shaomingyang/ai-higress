# Admin System Config（动态系统配置）API

> 说明：本组接口用于管理员（`require_superuser`）管理**运行时可动态修改**的系统级 Key-Value 配置。

## 鉴权
- 需要 JWT，并且用户必须是超级管理员（superuser）。

## 配置项：全局 Embedding 模型

Key：
- `KB_GLOBAL_EMBEDDING_LOGICAL_MODEL`

行为：
- 后端读取时优先读 DB（`system_configs` 表），未命中则回退到环境变量/`settings`；
- 当 `QDRANT_KB_USER_COLLECTION_STRATEGY=shared` 时，管理员更新该 Key 会触发**维度安全校验**：
  - 会试跑一次 Embedding，获得新模型的向量维度；
  - 对比当前 Qdrant Collection（`QDRANT_KB_USER_SHARED_COLLECTION`，默认 `kb_shared_v1`）的维度；
  - 若维度不一致，则拒绝切换，避免 shared collection 写入失败/炸库。

## 接口

### 1) 获取某个配置（读 DB，缺失则回退 env）
`GET /v1/admin/system/configs/{key}`

返回：`AdminSystemConfigResponse`
- `key`
- `value`：可能为 `null`
- `source`：`db` / `env`

### 2) 写入/更新某个配置（动态生效）
`POST /v1/admin/system/configs`

Body：`AdminSystemConfigUpsertRequest`
- `key`：必填
- `value`：可为 `null`（表示清空 DB 覆盖并回退到 env）
- `description`：可选（仅用于管理端展示）

返回：`AdminSystemConfigResponse`

## 错误码说明（关键场景）
- 403：非超级管理员
- 400：
  - shared 策略下尝试清空 `KB_GLOBAL_EMBEDDING_LOGICAL_MODEL`
  - Qdrant 未配置导致无法进行维度校验
  - Embedding 试跑失败（上游返回空向量/响应解析失败）
- 409：维度不一致，拒绝切换

