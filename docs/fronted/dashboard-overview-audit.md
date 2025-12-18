# 仪表盘概览页（Dashboard Overview）检测报告

更新时间：2025-12-18  
范围：`/dashboard/overview`（用户维度概览），以及其直接依赖的数据与组件。

## 1. 入口与页面结构（现状）

- 页面入口：`frontend/app/dashboard/overview/page.tsx`
- 客户端容器：`frontend/app/dashboard/overview/components/overview-client.tsx`
- 当前布局（从上到下）：
  - 时间范围筛选：`FilterBar`
  - 关键指标 3 卡：`StatsGrid`
  - 2x2 图表卡片：`ConsumptionSummaryCard` / `LatencyTrendCard` / `ProviderRankingCard` / `SuccessRateTrendCard`
  - “实时性能”三卡：`PerformanceGauges`
  - 活跃 Provider 状态：`ActiveProviders`
  - 近期活动：`RecentActivity`

> 设计风格要求请对照根目录 `ui-prompt.md`：强调极简/墨水风格、减少网格线/图例/动画、避免过度装饰。

## 2. 数据源与接口（现状盘点）

### 2.1 用户维度 Metrics（后端 `/metrics/user-overview/*`）

前端 Hook：`frontend/lib/swr/use-user-overview-metrics.ts`

- 汇总（关键指标卡）：`GET /metrics/user-overview/summary`
  - 用于：`StatsGrid`
  - 字段：`total_requests / active_providers / success_rate` + 上一周期对比 `*_prev`
- 时间序列（活动/延迟/成功率等复用）：`GET /metrics/user-overview/timeseries?bucket=minute`
  - 用于：`LatencyTrendCard` / `SuccessRateTrendCard` / `PerformanceGauges` / `RecentActivity`
  - 字段：`total_requests / success_requests / error_requests / latency_avg_ms / latency_p95_ms / latency_p99_ms / error_rate`
- Provider 聚合排行：`GET /metrics/user-overview/providers`
  - 用于：`ProviderRankingCard` / `ActiveProviders`
  - 字段：`provider_id / total_requests / success_rate / latency_p95_ms`

### 2.2 费用/积分（后端 `/v1/credits/*`）

前端 Hook：`frontend/lib/swr/use-credits.ts`

- 积分消耗汇总：`GET /v1/credits/me/consumption/summary`
  - 用于：`ConsumptionSummaryCard`（但趋势图目前是“模拟数据”，详见问题清单）
- Provider 维度积分消耗：`GET /v1/credits/me/consumption/providers`
  - 目前未在概览页使用（但非常适合做“成本结构/Top Provider 成本”）

## 3. 关键问题（你现在“看着不舒服/不可信”的来源）

### 3.1 数据正确性问题（必须优先修）

1) **成功率计算逻辑错误（导致“全成功时显示 0%”）**  
`frontend/components/dashboard/overview/success-rate-trend-card.tsx`：用 `point.error_requests ? ... : 0` 计算成功率；当 `error_requests = 0` 时被判定为 0，而不是 100%。

2) **“积分消耗趋势图”使用随机模拟数据（不可用于生产）**  
`frontend/components/dashboard/overview/consumption-summary-card.tsx`：`sparklineData` 通过 `Math.random()` 生成（即便接口数据稳定，曲线也会抖动），容易让用户失去信任。

3) **Provider 排行卡文案/排序与数据不一致**  
`frontend/components/dashboard/overview/provider-ranking-card.tsx`：
  - 注释与文案写“消耗排行榜”，但排序是按 `total_requests`（且没有显示“消耗/成本”字段）。
  - `CardDescription` 固定使用 `overview.from_last_month`，但用户切换时间范围后仍显示“相比上个月”，语义不严谨。

### 3.2 信息架构问题（导致“内容感觉不对”）

- 概览页混合了“用户维度概览”与“系统监控”的部分语义，但筛选维度不足：后端已支持 `transport / is_stream`，UI 未暴露，用户无法解释曲线变化。
- “实时性能”使用 `timeRange` 的 7d/30d 数据再截最近 10 个点来近似实时（`PerformanceGauges`），语义容易被误解：实时应固定最近 N 分钟/小时，不应受 timeRange 影响。

### 3.3 图表选择与标注问题（与 `ui-prompt.md` 冲突）

- 多张图表启用了 Legend、网格线、点标记、动画与多色方案（例如 `LatencyTrendCard` / `RecentActivity`），整体视觉偏“监控面板”，与“极简/墨水风格”不一致。
- 多处轴标题/空态文案直接写死中文（不走 i18n），与项目 i18n 规范冲突：例如 `LatencyTrendCard`、`SuccessRateTrendCard`、`RecentActivity`、`PerformanceGauges`。

### 3.4 文档与实现漂移（会导致后续持续返工）

`docs/fronted/dashboard-overview-refactor.md` 与当前实现存在多处不一致（时间范围选项、localStorage key、Provider 排行的口径等）。如果你准备按新方案重做，建议把“新口径”写回文档，避免前端/后端/设计再次漂移。

## 4. 按“AI 网关概览方案”对照的缺口（还需要添加什么）

下面按“健康度 / 性能 / 成本 / 风控与结构”四大目标列出缺口，并标注是否能用现有接口落地。

### 4.1 健康度（流量 & 成功率）

- 请求量趋势（支持堆叠：provider/model/route）：**部分可做**
  - 现有：只有全局（用户维度）总量 timeseries
  - 缺口：缺少按 provider/model/route 的时间序列切分
- 错误构成（4xx/5xx/超时/上游失败/鉴权失败/限流）：**需要后端**
  - 现有：只有 `error_requests` 与 `error_rate`，没有分类维度

### 4.2 性能（P50/P95/P99 & 长尾）

- 延迟 P50/P95/P99：**现有已做（P95/P99/avg）**，建议补 P50（需要后端或在网关侧补采样）
- 延迟分布（直方图/箱线图）：**需要后端**（或先做前端近似，但成本高且不准）

### 4.3 成本（Token/费用/单位成本）

- Token 用量（input/output/total）趋势：**需要后端**（或从交易流水聚合，短期可做）
- 费用/积分消耗趋势（真实趋势）：**需要后端**（最佳）或 **短期前端聚合**（次优）
  - 现状：概览页趋势图为模拟数据，必须替换
- Top Provider/Model 成本结构：**已有接口可以落地一版**
  - 现有：`/v1/credits/me/consumption/providers`

### 4.4 使用结构与风控（谁在用、用什么、是否异常）

- Top 调用方（API Key / 用户 / 项目 / 路由）：**部分需要后端与权限确认**
  - 后端已存在 `/metrics/api-keys/summary`、`/metrics/users/summary` 等接口，但当前实现未在前端消费；且需要先确认鉴权策略是否符合预期（避免越权读取）。
- 限流触发、鉴权失败等事件流与曲线标注：**需要后端**
  - 前端已有 `useOverviewEvents`/`EventStreamCard`，但仓库内未找到对应的后端 `/metrics/overview/events` 实现，属于“前端预留但后端缺失”。

## 5. 建议的改造路线（可执行清单）

### P0（立即改，提升可信度）

- 修复成功率曲线计算口径（`error_requests = 0` 时应为 100%）
- 移除“模拟 Sparkline”，改为：
  - 没有真实数据就不画趋势（展示占位/引导），或
  - 临时用 `/v1/credits/me/transactions` 聚合最近 N 天（可控范围）生成趋势
- 明确 Provider 排行卡的口径：要么改名为“请求排行/性能排行”，要么接入“积分消耗排行”（并展示占比/消耗额）
- 把所有硬编码用户可见文案迁移到 i18n（含轴标题、空态）

### P1（让图表“更像 AI 网关”）

- 新增“成本结构”卡：Top Provider 成本条形图/列表（可用 `/v1/credits/me/consumption/providers`）
- 筛选增强：在 FilterBar 增加 `transport / is_stream`（后端已支持）
- 统一图表风格：减少 Legend/网格线/动画；统一 tooltip；重点系列使用单色深浅或少量强调色（对照 `ui-prompt.md`）

### P2（需要后端配合，做出差异化）

- 新增成本与 token 的 timeseries 聚合接口（用户维度 + 可筛 provider/model）
- 新增错误分类维度（超时/鉴权/限流/上游错误等）与时间序列
- 新增事件流接口，并支持在图表上做“变更标注”（deploy/配置变更/Provider 故障）

## 6. 下一步需要你确认的两个关键选择（否则实现会摇摆）

1) 概览页的“Provider 排行”口径到底是：
   - A. 请求/性能（更像“运维监控”），还是
   - B. 成本/积分（更像“费用控制”），还是
   - C. 两者并存（一个看成本，一个看性能）
2) 成本趋势是否允许“短期前端聚合交易流水”过渡？
   - 允许：可以快速上线，但性能与口径需限制（例如最多 30 天、最多 2000 条流水）
   - 不允许：需要后端新增聚合接口后再上线趋势图

