# 用户维度概览 API

> 新增于 `001-user-overview` Feature，用于支持“我的请求表现”仪表盘。

## 1. 路由一览

| Endpoint | 描述 | 缓存 | 备注 |
|----------|------|------|------|
| `GET /metrics/user-overview/summary` | 我的总请求 / 成功率 / 活跃 Provider 汇总，含上一周期对比 | Redis `metrics:user-overview:summary:{user_id}:...`，TTL=60s | 依赖 `UserRoutingMetricsHistory` |
| `GET /metrics/user-overview/providers` | 我的 Provider 排行榜（按请求量排序） | Redis `metrics:user-overview:providers:{user_id}:...`，TTL=60s | 支持 `limit`、`transport`、`is_stream` |
| `GET /metrics/user-overview/timeseries` | 我的近期活动/成功率趋势 | Redis `metrics:user-overview:timeseries:{user_id}:...`，TTL=60s | 仅支持 `bucket=minute` |
| `GET /metrics/user-overview/apps` | 我的 App/客户端使用排行（按请求量排序） | Redis `metrics:user-overview:apps:{user_id}:...`，TTL=60s | 依赖 `UserAppRequestMetricsHistory`（入口请求口径） |

所有接口均要求登录态（JWT），后端自动从 `current_user` 中获取 `user_id`，不接受任意用户 ID。

## 2. 数据模型

后端新增 `user_routing_metrics_history` 表，按以下维度聚合：

- `user_id`, `provider_id`, `logical_model`
- `transport`（http/sdk/all）
- `is_stream`（true/false）
- `window_start`（分钟粒度）

每条记录包含 `total_requests`、`success_requests`、`error_requests` 以及 `latency_avg/p95/p99`。写入链路与 Provider 指标共享同一打点逻辑，确保实时性。

## 3. 请求参数

| 参数 | 说明 | 取值 |
|------|------|------|
| `time_range` | 时间范围 | `today` / `7d` / `30d` / `all`（默认 `7d`） |
| `transport` | 传输模式过滤 | `http` / `sdk` / `all`（默认 `all`） |
| `is_stream` | 是否流式过滤 | `true` / `false` / `all`（默认 `all`） |
| `bucket` | 时间序列粒度（仅 timeseries） | 目前仅支持 `minute` |
| `limit` | Provider 排行数量（仅 providers） | 1 ~ 50，默认 4 |
| `limit` | App 排行数量（仅 apps） | 1 ~ 50，默认 10 |

## 4. 响应示例

### 4.1 Summary

```json
{
  "scope": "user",
  "user_id": "00000000-0000-0000-0000-000000000000",
  "time_range": "7d",
  "transport": "all",
  "is_stream": "all",
  "total_requests": 1234,
  "success_requests": 1190,
  "error_requests": 44,
  "success_rate": 0.9643,
  "total_requests_prev": 980,
  "success_requests_prev": 910,
  "error_requests_prev": 70,
  "success_rate_prev": 0.9286,
  "active_providers": 6,
  "active_providers_prev": 5
}
```

### 4.2 Providers

```json
{
  "scope": "user",
  "user_id": "00000000-0000-0000-0000-000000000000",
  "time_range": "7d",
  "transport": "all",
  "is_stream": "all",
  "items": [
    {
      "provider_id": "openai",
      "total_requests": 800,
      "success_requests": 780,
      "error_requests": 20,
      "success_rate": 0.975,
      "latency_p95_ms": 110.3
    },
    {
      "provider_id": "claude",
      "total_requests": 200,
      "success_requests": 160,
      "error_requests": 40,
      "success_rate": 0.8,
      "latency_p95_ms": 140.0
    }
  ]
}
```

### 4.3 Timeseries

```json
{
  "scope": "user",
  "user_id": "00000000-0000-0000-0000-000000000000",
  "time_range": "7d",
  "bucket": "minute",
  "transport": "all",
  "is_stream": "all",
  "points": [
    {
      "window_start": "2025-01-12T10:00:00Z",
      "total_requests": 40,
      "success_requests": 35,
      "error_requests": 5,
      "latency_avg_ms": 120.5,
      "latency_p95_ms": 180.2,
      "latency_p99_ms": 240.0,
      "error_rate": 0.125
    }
  ]
}
```

当用户无数据时，`total_requests=0` 且 `points=[]`。

### 4.4 Apps

```json
{
  "scope": "user",
  "user_id": "00000000-0000-0000-0000-000000000000",
  "time_range": "7d",
  "items": [
    {
      "app_name": "Cherry Studio",
      "total_requests": 123,
      "last_seen_at": "2025-12-18T13:53:00Z"
    },
    {
      "app_name": "Roo Code",
      "total_requests": 45,
      "last_seen_at": "2025-12-18T13:52:00Z"
    }
  ]
}
```

`app_name` 推断规则（从高到低）：

1. `X-Title` / `x-title`
2. `User-Agent` 第一个 product token（如 `RooCode/3.36.12` -> `RooCode`；浏览器 UA 会退化）
3. `Referer`/`Origin` 的 hostname
4. `unknown`

## 5. 缓存与清理

所有 key 均以 `metrics:user-overview:*` 开头，并通过 `CacheSegment.USER_METRICS_OVERVIEW` 统一清理：

- `metrics:user-overview:summary:{user_id}:{time_range}:{transport}:{is_stream}`
- `metrics:user-overview:providers:{user_id}:{time_range}:{transport}:{is_stream}:{limit}`
- `metrics:user-overview:timeseries:{user_id}:{time_range}:{transport}:{is_stream}:{bucket}`

管理员可通过 `POST /system/cache/clear` 并在 `segments` 中传入 `["user_metrics_overview"]` 来清空这些缓存。

## 6. 前端对接要点

- 使用 `frontend/lib/swr/use-user-overview-metrics.ts` 中的 Hook，避免与系统级指标混用。
- 所有文案通过 `overview.my_*` / `success_rate_trend.user_title` 等 i18n key 表达“我的”语义。
- FilterBar 需提示“查看系统监控”，引导用户切换维度。
