# 上游代理池管理（管理员）前端接入与页面设计

## 目标与范围

为“上游请求代理池（HTTP/HTTPS/SOCKS5）”提供管理员可视化配置能力，覆盖以下场景：
- 管理员启用/关闭“管理式代理池”（DB 配置 + Celery 测活 + Redis 可用集合）。
- 管理员维护代理来源：
  - `static_list`：手动录入/批量导入代理条目；
  - `remote_text_list`：配置远程下载 URL（例如 Webshare download），定时刷新条目。
- 管理员手动触发：刷新远程来源、测活并重建 Redis 可用池。
- 查看代理池状态：来源数、条目数、可用数，以及来源刷新错误/条目测活失败原因等。

非目标（后续可扩展）：
- 动态代理接口（每次请求返回一个随机代理）provider；
- 多测活目标/分级测活策略（basic/both/upstream）；
- Celery task 进度/结果查询（当前只返回 task_id）。

设计约束：
- 视觉遵循 `ui-prompt.md`：极简/留白/墨水风格。
- 所有用户可见文案必须走 `useI18n()`，不写死字符串。
- 页面/组件优先复用 `@/components/ui`，不在 page 里堆原生标签。
- 前端请求使用 `@/lib/swr`（`useApiGet/useApiPost/useApiPut/useApiDelete`），不直接 fetch/axios。

---

## 路由与信息架构

建议采用“系统管理页入口 + 专用管理页”的两层结构，避免在 `/system/admin` 堆过多交互：

1) 入口卡片（概览）
- 路由：`/system/admin`
- 展示：
  - 代理池状态摘要（可用数/总条目数/来源数）
  - 快捷操作：打开“代理池管理”页面

2) 代理池管理页（全量管理）
- 路由：`/system/admin/upstream-proxy`
- 页面区域（最多 3~4 块）：
  - A. 全局配置（启用开关、fallback、测活 URL/超时/间隔）
  - B. 状态与操作（status + 手动触发 refresh/check）
  - C. 来源管理（sources 表格 + 新增/编辑 dialog）
  - D. 条目管理（endpoints 表格 + 过滤 + 批量导入 dialog）

---

## 后端 API 映射（前端对接点）

### 配置与状态
- `GET /admin/upstream-proxy/config`：读取全局配置（仅管理员）
- `PUT /admin/upstream-proxy/config`：更新全局配置（仅管理员）
- `GET /admin/upstream-proxy/status`：读取状态摘要（仅管理员）

### 来源 sources
- `GET /admin/upstream-proxy/sources`
- `POST /admin/upstream-proxy/sources`
- `PUT /admin/upstream-proxy/sources/{source_id}`
- `DELETE /admin/upstream-proxy/sources/{source_id}`

### 条目 endpoints
- `GET /admin/upstream-proxy/endpoints?source_id=...`
- `POST /admin/upstream-proxy/endpoints`
- `PUT /admin/upstream-proxy/endpoints/{endpoint_id}`
- `DELETE /admin/upstream-proxy/endpoints/{endpoint_id}`
- `POST /admin/upstream-proxy/endpoints/import`

### 任务触发（Celery）
- `POST /admin/upstream-proxy/tasks/refresh`：返回 `{ task_id }`
- `POST /admin/upstream-proxy/tasks/check`：返回 `{ task_id }`

---

## 前端数据层接入（类型与 SWR）

### TypeScript 类型
在 `frontend/lib/api-types.ts` 增加（命名建议）：
- `UpstreamProxyConfig` / `UpdateUpstreamProxyConfigRequest`
- `UpstreamProxyStatus`
- `UpstreamProxySource` / `CreateUpstreamProxySourceRequest` / `UpdateUpstreamProxySourceRequest`
- `UpstreamProxyEndpoint` / `CreateUpstreamProxyEndpointRequest` / `UpdateUpstreamProxyEndpointRequest`
- `UpstreamProxyImportRequest` / `UpstreamProxyImportResponse`
- `UpstreamProxyTaskResponse`

类型字段直接对齐后端响应（注意：不会返回敏感明文，如 `remote_url`、`password`）。

### SWR Hook（领域化封装）
新增 `frontend/lib/swr/use-upstream-proxy.ts`，提供：
- `useUpstreamProxyConfig()`：
  - GET config（`strategy: 'static'`）
  - PUT config（保存后 `mutate` + toast）
- `useUpstreamProxyStatus()`：
  - GET status（`strategy: 'frequent'`，或手动 refresh）
- `useUpstreamProxySources()`：
  - GET sources（`strategy: 'static'`）
  - POST/PUT/DELETE source（成功后 `mutate` 刷新 sources 与 status）
- `useUpstreamProxyEndpoints(params)`：
  - GET endpoints（`strategy: 'frequent'`，支持 `source_id` 过滤）
  - POST/PUT/DELETE endpoint（成功后刷新 endpoints 与 status）
- `useUpstreamProxyTasks()`：
  - POST refresh/check（toast 显示 task_id，并触发 status/endpoints 的 refresh）

缓存策略建议：
- config/sources：`static`（变化少）
- status/endpoints：`frequent`（测活/失败剔除会变化），或在任务触发后手动 `refresh()`

---

## 页面 UI 设计（组件拆分）

### 推荐目录结构
- `frontend/app/system/admin/upstream-proxy/page.tsx`（服务端组件，布局）
- `frontend/app/system/admin/upstream-proxy/components/upstream-proxy-client.tsx`（客户端容器）
- `frontend/app/system/admin/components/upstream-proxy-card.tsx`（系统管理页入口卡片，可选）
- `frontend/components/forms/upstream-proxy/`（表单/对话框组件）
- `frontend/lib/swr/use-upstream-proxy.ts`

### 组件清单（建议）

1) `UpstreamProxyConfigCard`（Card）
- 字段：
  - `enabled`（Switch）
  - `healthcheck_url`（Input）
  - `healthcheck_method`（Select：GET/HEAD）
  - `healthcheck_timeout_ms`（Input number）
  - `healthcheck_interval_seconds`（Input number）
- 操作：
  - Reset / Save（Button）
- 交互：
  - 保存成功 toast；失败 toast（复用现有错误展示策略）
  - `enabled=false` 时，页面状态提示“当前直连（未启用管理式代理池）”

2) `UpstreamProxyStatusCard`（Card）
- 展示：
  - `total_sources / total_endpoints / available_endpoints`
  - `config_enabled`
- 操作：
  - “刷新远程来源”（POST tasks/refresh）
  - “测活并重建”（POST tasks/check）
- 反馈：
  - 返回 task_id：toast 显示（例如 “已提交任务：xxxx”）
  - 任务触发后，主动 refresh status/endpoints（不做轮询，MVP 足够）

3) `UpstreamProxySourcesTable`（Table + Dialog）
- 列：
  - name / source_type / enabled / default_scheme / refresh_interval / last_refresh_at / last_refresh_error
- 行操作：
  - Edit（Dialog）
  - Delete（二次确认 Dialog）
- 新增来源：
  - 静态来源：只需 name/default_scheme/enabled
  - 远程来源：额外 remote_url、refresh_interval、remote_headers（JSON textarea）
- 安全展示：
  - `remote_url` 只显示 `***`（后端已返回 masked 字段）

4) `UpstreamProxyEndpointsTable`（Table + Filter + Dialog）
- 顶部筛选：
  - source 下拉（来自 sources）
  - enabled 过滤（可选）
- 列（尽量短）：
  - scheme / host:port / username / enabled / last_ok / last_latency_ms / consecutive_failures / last_error
- 行操作：
  - enable/disable（Switch 或 Button）
  - delete
- 批量导入（ImportDialog）：
  - 选择 source
  - default_scheme（Select；未带 scheme 的行会按此解析）
  - text（Textarea；支持 `ip:port`、`ip:port:user:pass`、完整 URL）
  - 提交后 toast 显示 `inserted_or_updated`

UI 风格细节：
- 表格尽量无线条/细线，靠行间距区分；
- 错误信息（如 last_refresh_error/last_error）用 muted 文本 + tooltip 展开，避免视觉噪音；
- destructive 操作（delete）使用 shadcn 的 destructive variant。

---

## 权限与错误处理

权限：
- 所有接口均为管理员（JWT + superuser）。前端不强依赖路由守卫，但要在 403 时显示明确提示。

错误处理（建议遵循现有模式）：
- SWR error：在 Card/Table 顶部显示轻量错误（`ErrorContent`/toast）
- 操作失败：toast.error，优先取后端 `detail`；其次 fallback 到 i18n 文案 key

---

## 国际化（i18n）键建议

在 `frontend/lib/i18n/system.ts` 增加（示例命名）：
- `system.upstream_proxy.title`
- `system.upstream_proxy.subtitle`
- `system.upstream_proxy.config.title`
- `system.upstream_proxy.config.enabled`
- `system.upstream_proxy.config.healthcheck_url`
- `system.upstream_proxy.config.healthcheck_method`
- `system.upstream_proxy.config.healthcheck_timeout_ms`
- `system.upstream_proxy.config.healthcheck_interval_seconds`
- `system.upstream_proxy.actions.refresh_sources`
- `system.upstream_proxy.actions.check_health`
- `system.upstream_proxy.sources.title`
- `system.upstream_proxy.endpoints.title`
- `system.upstream_proxy.import.title`
- `system.upstream_proxy.save_success` / `system.upstream_proxy.save_error`
- `system.upstream_proxy.task_submitted`
- `system.upstream_proxy.permission_denied`

---

## 开发/联调步骤（前端）

1) 补 TS 类型（`frontend/lib/api-types.ts`）
2) 补 SWR Hooks（`frontend/lib/swr/use-upstream-proxy.ts`）
3) 新增页面与组件：
   - `/system/admin/upstream-proxy`（管理页）
   - `/system/admin` 增加入口卡片（可选）
4) 补 i18n（`frontend/lib/i18n/system.ts` 与 `frontend/lib/i18n/index.ts` 若需要合并导出）
5) 手动联调：
   - 创建来源 -> 导入条目 -> 启用代理池 -> 触发测活 -> 查看 available 数变化
