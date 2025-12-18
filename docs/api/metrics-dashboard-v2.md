# Dashboard 指标接口（/metrics/*）

> 本文档描述“Dashboard v2（用户页 + 系统页）”使用的指标接口。
>
> 设计目标：让用户/管理员在 5 秒内回答“系统健康吗？Token 用了多少？（用户页另含个人 credits）”。
>
> **注意**：`Token` 口径不依赖扣费/定价是否发生；当上游未返回 usage 时，会使用请求参数做保守估算，并通过 `estimated_requests` 标记“估算请求数”用于解释口径。
>
> 对于流式请求：默认在首包到达时基于 `max_tokens/max_tokens_to_sample/max_output_tokens`（或 `STREAMING_MIN_TOKENS`）写入一次保守估算，保证趋势连续。

## 鉴权

- 全部接口需要登录用户（JWT）。
- `/metrics/system-dashboard/*` 仅管理员（`is_superuser=true`）可访问，非管理员返回 `403 Forbidden`。

## 缓存

- 全部接口使用 Redis 缓存，TTL=60s。
- 用户接口缓存 key 包含 user_id，避免跨用户污染。
- 分钟桶历史数据会按系统配置自动清理：`GET/PUT /system/gateway-config` 中的 `metrics_retention_days`（默认 15 天，范围 7..30）。

## 后台统计（Celery rollup）

为降低 7d/30d 查询的聚合成本，后端提供 hour/day 两张 rollup 表（由 Celery 定时任务写入）：

- `provider_routing_metrics_hourly`：小时级聚合
- `provider_routing_metrics_daily`：天级聚合

Dashboard v2 在 `time_range != today` 时会**优先查询 rollup 表**，若 rollup 尚未产出则回退到分钟桶聚合（保证开箱可用）。

相关任务（需启动 Celery worker + beat 才会持续产出）：
- `tasks.metrics.rollup_hourly` / `tasks.metrics.rollup_daily`
- `tasks.metrics.cleanup_history`（分钟桶清理）
- `tasks.metrics.cleanup_hourly` / `tasks.metrics.cleanup_daily`（rollup 清理）

并发说明（Postgres）：
- 任务内部使用 `pg_try_advisory_lock` 做互斥，避免多实例/多 beat 重复跑同一类任务导致 IO 浪费；
- 清理任务采用“分批删除”，降低单次大事务带来的锁与膨胀风险。

可通过环境变量调优（见 `app/settings.py`）：
- `DASHBOARD_METRICS_ROLLUP_ENABLED`
- `DASHBOARD_METRICS_ROLLUP_HOURLY_INTERVAL_SECONDS` / `DASHBOARD_METRICS_ROLLUP_DAILY_INTERVAL_SECONDS`
- `DASHBOARD_METRICS_HOURLY_RETENTION_DAYS` / `DASHBOARD_METRICS_DAILY_RETENTION_DAYS`
- `DASHBOARD_METRICS_CLEANUP_BATCH_SIZE`

## Postgres 分区（分钟桶表）

为避免 `provider_routing_metrics_history`（分钟桶事实表）在高写入/长期运行下出现 bloat 与大 DELETE 锁问题，后端提供 **按天 RANGE 分区**方案：

- 迁移：`0040_partition_provider_routing_metrics_history_by_day`
- 分区命名：`provider_routing_metrics_history_pYYYYMMDD`（UTC 天）
- DEFAULT 分区：`provider_routing_metrics_history_default`（兜底，理论上应很少写入）
- 清理策略：`tasks.metrics.cleanup_history` 在 Postgres 分区表场景下会优先执行“创建近期分区 + drop 过期分区”，而不是扫表 delete

注意：
- 分区迁移需要对表做结构调整与数据搬迁，首次升级可能会有一定耗时（与历史数据量相关）。
- 该方案在 Postgres 下默认生效，属于“以运维稳定为目标”的推荐配置；如你确实不希望启用分区，请自行 fork/调整迁移策略。

---

## 1) 用户页 KPI

`GET /metrics/user-dashboard/kpis`

Query：
- `time_range`: `today|7d|30d`（默认 `7d`）
- `transport`: `http|sdk|claude_cli|all`（默认 `all`）
- `is_stream`: `true|false|all`（默认 `all`）

响应（示例）：

```jsonc
{
  "time_range": "7d",
  "total_requests": 120000,
  "error_rate": 0.0123,
  "latency_p95_ms": 850.2,
  "tokens": {
    "input": 5000000,
    "output": 3200000,
    "total": 8200000,
    "estimated_requests": 120
  },
  "credits_spent": 420
}
```

说明：
- `tokens.*` 来自分钟桶事实表 `provider_routing_metrics_history` 的 token 聚合字段；
- `credits_spent` 来自 `credit_transactions`，只统计 `reason in (usage, stream_usage)` 的扣减流水（避免 `stream_estimate` 双计）。

---

## 2) 用户页 Pulse（近 24h，分钟）

`GET /metrics/user-dashboard/pulse`

Query：
- `transport`: `http|sdk|claude_cli|all`
- `is_stream`: `true|false|all`

响应：

```jsonc
{
  "points": [
    {
      "window_start": "2025-12-18T01:00:00Z",
      "total_requests": 123,
      "error_4xx_requests": 1,
      "error_5xx_requests": 2,
      "error_429_requests": 3,
      "error_timeout_requests": 0,
      "latency_p50_ms": 180.1,
      "latency_p95_ms": 850.2,
      "latency_p99_ms": 1200.4
    }
  ]
}
```

说明：
- `points` 会对缺失分钟做补零，避免折线“断裂”造成误读；
- 延迟分位数为分钟桶内的采样近似，并在聚合时做加权平均（展示趋势为主）。

---

## 3) 用户页 Token 趋势（hour/day）

`GET /metrics/user-dashboard/tokens`

Query：
- `time_range`: `today|7d|30d`（默认 `7d`）
- `bucket`: `hour|day`（默认 `hour`）
- `transport`: `http|sdk|claude_cli|all`
- `is_stream`: `true|false|all`

响应：

```jsonc
{
  "time_range": "7d",
  "bucket": "hour",
  "points": [
    {
      "window_start": "2025-12-18T01:00:00Z",
      "input_tokens": 120000,
      "output_tokens": 80000,
      "total_tokens": 200000,
      "estimated_requests": 3
    }
  ]
}
```

---

## 4) 用户页 Top Models

`GET /metrics/user-dashboard/top-models`

Query：
- `time_range`: `today|7d|30d`（默认 `7d`）
- `limit`: `1..50`（默认 `10`）
- `transport`: `http|sdk|claude_cli|all`
- `is_stream`: `true|false|all`

响应：

```jsonc
{
  "items": [
    { "model": "gpt-4-turbo", "requests": 12000, "tokens_total": 3200000 }
  ]
}
```

---

## 5) 用户页 成本结构（credits by provider）

`GET /metrics/user-dashboard/cost-by-provider`

Query：
- `time_range`: `today|7d|30d`（默认 `7d`）
- `limit`: `1..50`（默认 `12`）

响应：

```jsonc
{
  "items": [
    { "provider_id": "openai", "credits_spent": 320, "transactions": 40 }
  ]
}
```

---

## 6) 用户页 Provider 指标（用于 Provider 卡片）

`GET /metrics/user-dashboard/providers`

Query：
- `time_range`: `today|7d|30d`（默认 `7d`）
- `bucket`: `hour`（默认 `hour`，目前仅支持该值）
- `provider_ids`: 逗号分隔的 `provider_id` 列表（可选；不传则返回该用户最活跃的 providers，最多 `limit` 个）
- `limit`: `1..50`（默认 `12`；仅在未传 `provider_ids` 时生效）
- `transport`: `http|sdk|claude_cli|all`（默认 `all`）
- `is_stream`: `true|false|all`（默认 `all`）

响应（示例）：

```jsonc
{
  "time_range": "7d",
  "bucket": "hour",
  "items": [
    {
      "provider_id": "openai",
      "total_requests": 12000,
      "error_rate": 0.0123,
      "latency_p95_ms": 850.2,
      "qps": 0.42,
      "points": [
        { "window_start": "2025-12-18T01:00:00Z", "qps": 0.30, "error_rate": 0.01 }
      ]
    }
  ]
}
```

说明：
- `points` 固定为近 24h 的小时桶（用于卡片小图），缺失时间桶会补零，避免折线“断裂”；
- `qps` 为 `points` 的最后一个时间桶的平均 QPS（该小时总请求数 / 3600）；
- `error_rate / latency_p95_ms` 为 `time_range` 窗口内聚合指标（按请求量加权）。

---

## 7) 系统页 KPI（管理员）

`GET /metrics/system-dashboard/kpis`

Query：
- `time_range`: `today|7d|30d`（默认 `7d`）
- `transport`: `http|sdk|claude_cli|all`
- `is_stream`: `true|false|all`

响应与用户版一致，但无 `credits_spent` 字段。

---

## 8) 系统页 Pulse（管理员）

`GET /metrics/system-dashboard/pulse`

同用户版，但为全局聚合。

---

## 9) 系统页 Token 趋势（管理员）

`GET /metrics/system-dashboard/tokens`

同用户版，但为全局聚合。

---

## 10) 系统页 Top Models（管理员）

`GET /metrics/system-dashboard/top-models`

同用户版，但为全局聚合。

---

## 11) 系统页 Provider 状态（管理员）

`GET /metrics/system-dashboard/providers`

响应：

```jsonc
{
  "items": [
    {
      "provider_id": "openai",
      "operation_status": "active",
      "status": "healthy",
      "audit_status": "approved",
      "last_check": "2025-12-18T01:20:00Z"
    }
  ]
}
```
