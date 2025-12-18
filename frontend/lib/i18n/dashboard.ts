import type { Language } from "../i18n-context";

export const dashboardV2Translations: Record<Language, Record<string, string>> = {
  en: {
    // Page title (通用键)
    "dashboard.title": "Dashboard Overview",
    "dashboard.subtitle": "Real-time monitoring and analytics",
    
    // Page title (v2 兼容键)
    "dashboard_v2.title": "Dashboard Overview",
    "dashboard_v2.subtitle": "Real-time monitoring and analytics",
    "dashboardV2.title": "Dashboard Overview",
    
    // System Dashboard title
    "dashboardV2.system.title": "System Dashboard",
    "dashboardV2.system.subtitle": "Global monitoring and analytics",

    // Filter bar
    "dashboard_v2.filter.time_range.label": "Time Range",
    "dashboard_v2.filter.time_range.today": "Today",
    "dashboard_v2.filter.time_range.7d": "Last 7 Days",
    "dashboard_v2.filter.time_range.30d": "Last 30 Days",
    
    "dashboard_v2.filter.transport.label": "Transport",
    "dashboard_v2.filter.transport.all": "All",
    "dashboard_v2.filter.transport.http": "HTTP",
    "dashboard_v2.filter.transport.sdk": "SDK",
    "dashboard_v2.filter.transport.claude_cli": "Claude CLI",
    
    "dashboard_v2.filter.stream.label": "Stream",
    "dashboard_v2.filter.stream.all": "All",
    "dashboard_v2.filter.stream.true": "Streaming",
    "dashboard_v2.filter.stream.false": "Non-Streaming",

    // Health badge
    "dashboard_v2.health.normal": "Normal",
    "dashboard_v2.health.unstable": "Unstable",
    "dashboard_v2.health.critical": "Critical",
    
    // Health badge (new keys for HealthBadge component)
    "dashboardV2.healthBadge.loading": "Loading...",
    "dashboardV2.healthBadge.healthy": "Normal",
    "dashboardV2.healthBadge.degraded": "Degraded",
    "dashboardV2.healthBadge.unhealthy": "Unhealthy",

    // KPI Cards
    "dashboard_v2.kpi.total_requests": "Total Requests",
    "dashboard_v2.kpi.credits_spent": "Credits Spent",
    "dashboard_v2.kpi.latency_p95": "P95 Latency",
    "dashboard_v2.kpi.error_rate": "Error Rate",
    "dashboard_v2.kpi.total_tokens": "Total Tokens",
    "dashboard_v2.kpi.input_tokens": "Input",
    "dashboard_v2.kpi.output_tokens": "Output",

    // Charts
    "dashboard_v2.chart.requests_errors.title": "Requests & Errors Trend",
    "dashboard_v2.chart.requests_errors.subtitle": "Last 24 hours",
    "dashboard_v2.chart.latency_percentiles.title": "Latency Percentiles",
    "dashboard_v2.chart.latency_percentiles.subtitle": "Last 24 hours",
    "dashboard_v2.chart.latency.title": "Latency Percentiles",
    "dashboard_v2.chart.latency.subtitle": "Last 24 hours",
    "dashboard_v2.chart.apps_usage.title": "Top Client Apps",
    "dashboard_v2.chart.apps_usage.subtitle": "Top {limit}",
    "dashboard_v2.chart.apps_usage.requests": "Requests",
    "dashboard_v2.chart.token_usage.title": "Token Usage",
    "dashboard_v2.chart.token_usage.subtitle": "Input vs Output",
    "dashboard_v2.chart.token_usage.input_tokens": "Input Tokens",
    "dashboard_v2.chart.token_usage.output_tokens": "Output Tokens",
    "dashboard_v2.chart.token_usage.total_tokens": "Total Tokens",
    "dashboard_v2.chart.token_usage.estimated_tooltip": "{count} requests have estimated token counts",
    "dashboard_v2.chart.tokens.title": "Token Usage",
    "dashboard_v2.chart.tokens.subtitle": "Input vs Output",
    "dashboard_v2.chart.cost.title": "Cost by Provider",
    "dashboard_v2.chart.cost.subtitle": "Distribution",
    "dashboard_v2.chart.top_models.title": "Top Models",
    "dashboard_v2.chart.top_models.subtitle": "Most used models",
    
    // System Dashboard Charts
    "dashboardV2.system.charts.requestsErrors": "Requests & Errors Trend",
    "dashboardV2.system.charts.latencyPercentiles": "Latency Percentiles",
    "dashboardV2.system.charts.tokenUsage": "Token Usage",
    "dashboardV2.system.topModels.title": "Top Models",

    // Error labels for charts
    "dashboard_v2.chart.error.label": "Errors",
    "dashboard_v2.chart.error.4xx": "4xx Errors",
    "dashboard_v2.chart.error.5xx": "5xx Errors",
    "dashboard_v2.chart.error.429": "429 Errors",
    "dashboard_v2.chart.error.timeout": "Timeout Errors",

    // Latency labels
    "dashboard_v2.chart.latency.p50": "P50",
    "dashboard_v2.chart.latency.p95": "P95",
    "dashboard_v2.chart.latency.p99": "P99",

    // Cost chart labels
    "dashboard_v2.chart.cost.credits_label": "Credits",
    "dashboard_v2.chart.cost.percentage_label": "Percentage",
    "dashboard_v2.chart.cost.total_label": "Total Credits",

    // Loading & Error states
    "dashboard_v2.loading": "Loading...",
    "dashboard_v2.error": "Failed to load data",
    "dashboard_v2.error.retry": "Retry",
    "dashboard_v2.empty": "No data available",

    // Tooltips
    "dashboard_v2.tooltip.estimated_requests": "Some tokens are estimated",

    // Top Models Table
    "dashboardV2.topModels.title": "Top Models",
    "dashboardV2.topModels.modelName": "Model Name",
    "dashboardV2.topModels.requests": "Requests",
    "dashboardV2.topModels.totalTokens": "Total Tokens",

    // Provider Status
    "dashboardV2.provider.title": "Provider Status",
    "dashboardV2.provider.totalCount": "{count} Providers",
    "dashboardV2.provider.noData": "No Providers",
    "dashboardV2.provider.noDataDescription": "No provider data available at the moment",
    
    "dashboardV2.provider.operationStatus": "Operation Status",
    "dashboardV2.provider.operationStatus.active": "Active",
    "dashboardV2.provider.operationStatus.inactive": "Inactive",
    "dashboardV2.provider.operationStatus.maintenance": "Maintenance",
    
    "dashboardV2.provider.healthStatus": "Health Status",
    "dashboardV2.provider.healthStatus.healthy": "Healthy",
    "dashboardV2.provider.healthStatus.degraded": "Degraded",
    "dashboardV2.provider.healthStatus.unhealthy": "Unhealthy",
    
    "dashboardV2.provider.auditStatus": "Audit Status",
    "dashboardV2.provider.auditStatus.approved": "Approved",
    "dashboardV2.provider.auditStatus.pending": "Pending",
    "dashboardV2.provider.auditStatus.rejected": "Rejected",
    
    "dashboardV2.provider.lastCheck.label": "Last Check",
    "dashboardV2.provider.lastCheck.justNow": "Just now",
    "dashboardV2.provider.lastCheck.minutesAgo": "{count} minutes ago",
    "dashboardV2.provider.lastCheck.hoursAgo": "{count} hours ago",
    "dashboardV2.provider.lastCheck.daysAgo": "{count} days ago",
    "dashboardV2.provider.lastCheck.unknown": "Unknown",

    // Error states (通用键)
    "dashboard.errors.loadFailed": "Failed to load data",
    "dashboard.errors.noData": "No data available",
    "dashboard.errors.retry": "Retry",
    
    // Error states (v2 兼容键)
    "dashboardV2.error.loadFailed": "Failed to load data",
    "dashboardV2.error.noData": "No data available",
    "dashboardV2.errors.loadFailed": "Failed to load data",
    "dashboardV2.errors.noData": "No data available",
    "dashboardV2.errors.retry": "Retry",
  },
  zh: {
    // Page title (通用键)
    "dashboard.title": "仪表盘概览",
    "dashboard.subtitle": "实时监控与分析",
    
    // Page title (v2 兼容键)
    "dashboard_v2.title": "仪表盘概览",
    "dashboard_v2.subtitle": "实时监控与分析",
    "dashboardV2.title": "仪表盘概览",
    
    // System Dashboard title
    "dashboardV2.system.title": "系统仪表盘",
    "dashboardV2.system.subtitle": "全局监控与分析",

    // Filter bar
    "dashboard_v2.filter.time_range.label": "时间范围",
    "dashboard_v2.filter.time_range.today": "今天",
    "dashboard_v2.filter.time_range.7d": "过去 7 天",
    "dashboard_v2.filter.time_range.30d": "过去 30 天",
    
    "dashboard_v2.filter.transport.label": "传输方式",
    "dashboard_v2.filter.transport.all": "全部",
    "dashboard_v2.filter.transport.http": "HTTP",
    "dashboard_v2.filter.transport.sdk": "SDK",
    "dashboard_v2.filter.transport.claude_cli": "Claude CLI",
    
    "dashboard_v2.filter.stream.label": "流式",
    "dashboard_v2.filter.stream.all": "全部",
    "dashboard_v2.filter.stream.true": "流式",
    "dashboard_v2.filter.stream.false": "非流式",

    // Health badge
    "dashboard_v2.health.normal": "正常",
    "dashboard_v2.health.unstable": "抖动",
    "dashboard_v2.health.critical": "异常",
    
    // Health badge (new keys for HealthBadge component)
    "dashboardV2.healthBadge.loading": "加载中...",
    "dashboardV2.healthBadge.healthy": "正常",
    "dashboardV2.healthBadge.degraded": "抖动",
    "dashboardV2.healthBadge.unhealthy": "异常",

    // KPI Cards
    "dashboard_v2.kpi.total_requests": "总请求数",
    "dashboard_v2.kpi.credits_spent": "Credits 花费",
    "dashboard_v2.kpi.latency_p95": "P95 延迟",
    "dashboard_v2.kpi.error_rate": "错误率",
    "dashboard_v2.kpi.total_tokens": "Token 总量",
    "dashboard_v2.kpi.input_tokens": "输入",
    "dashboard_v2.kpi.output_tokens": "输出",

    // Charts
    "dashboard_v2.chart.requests_errors.title": "请求 & 错误趋势",
    "dashboard_v2.chart.requests_errors.subtitle": "近 24 小时",
    "dashboard_v2.chart.latency_percentiles.title": "延迟分位数趋势",
    "dashboard_v2.chart.latency_percentiles.subtitle": "近 24 小时",
    "dashboard_v2.chart.latency.title": "延迟分位数",
    "dashboard_v2.chart.latency.subtitle": "近 24 小时",
    "dashboard_v2.chart.apps_usage.title": "客户端使用排行",
    "dashboard_v2.chart.apps_usage.subtitle": "Top {limit}",
    "dashboard_v2.chart.apps_usage.requests": "请求数",
    "dashboard_v2.chart.token_usage.title": "Token 使用趋势",
    "dashboard_v2.chart.token_usage.subtitle": "输入 vs 输出",
    "dashboard_v2.chart.token_usage.input_tokens": "输入 Token",
    "dashboard_v2.chart.token_usage.output_tokens": "输出 Token",
    "dashboard_v2.chart.token_usage.total_tokens": "Token 总量",
    "dashboard_v2.chart.token_usage.estimated_tooltip": "{count} 个请求的 Token 来自估算",
    "dashboard_v2.chart.tokens.title": "Token 使用",
    "dashboard_v2.chart.tokens.subtitle": "输入 vs 输出",
    "dashboard_v2.chart.cost.title": "按 Provider 成本",
    "dashboard_v2.chart.cost.subtitle": "分布情况",
    "dashboard_v2.chart.top_models.title": "热门模型",
    "dashboard_v2.chart.top_models.subtitle": "使用最多的模型",
    
    // System Dashboard Charts
    "dashboardV2.system.charts.requestsErrors": "请求 & 错误趋势",
    "dashboardV2.system.charts.latencyPercentiles": "延迟分位数趋势",
    "dashboardV2.system.charts.tokenUsage": "Token 使用趋势",
    "dashboardV2.system.topModels.title": "热门模型",

    // Error labels for charts
    "dashboard_v2.chart.error.label": "错误数",
    "dashboard_v2.chart.error.4xx": "4xx 错误",
    "dashboard_v2.chart.error.5xx": "5xx 错误",
    "dashboard_v2.chart.error.429": "429 错误",
    "dashboard_v2.chart.error.timeout": "超时错误",

    // Latency labels
    "dashboard_v2.chart.latency.p50": "P50",
    "dashboard_v2.chart.latency.p95": "P95",
    "dashboard_v2.chart.latency.p99": "P99",

    // Cost chart labels
    "dashboard_v2.chart.cost.credits_label": "Credits",
    "dashboard_v2.chart.cost.percentage_label": "占比",
    "dashboard_v2.chart.cost.total_label": "总 Credits",

    // Loading & Error states
    "dashboard_v2.loading": "加载中...",
    "dashboard_v2.error": "加载数据失败",
    "dashboard_v2.error.retry": "重试",
    "dashboard_v2.empty": "暂无数据",

    // Tooltips
    "dashboard_v2.tooltip.estimated_requests": "部分 Token 来自估算",

    // Top Models Table
    "dashboardV2.topModels.title": "热门模型",
    "dashboardV2.topModels.modelName": "模型名称",
    "dashboardV2.topModels.requests": "请求量",
    "dashboardV2.topModels.totalTokens": "Token 总量",

    // Provider Status
    "dashboardV2.provider.title": "Provider 状态",
    "dashboardV2.provider.totalCount": "共 {count} 个 Provider",
    "dashboardV2.provider.noData": "暂无 Provider",
    "dashboardV2.provider.noDataDescription": "当前没有可用的 Provider 数据",
    
    "dashboardV2.provider.operationStatus": "运行状态",
    "dashboardV2.provider.operationStatus.active": "运行中",
    "dashboardV2.provider.operationStatus.inactive": "未运行",
    "dashboardV2.provider.operationStatus.maintenance": "维护中",
    
    "dashboardV2.provider.healthStatus": "健康状态",
    "dashboardV2.provider.healthStatus.healthy": "健康",
    "dashboardV2.provider.healthStatus.degraded": "降级",
    "dashboardV2.provider.healthStatus.unhealthy": "不健康",
    
    "dashboardV2.provider.auditStatus": "审核状态",
    "dashboardV2.provider.auditStatus.approved": "已批准",
    "dashboardV2.provider.auditStatus.pending": "待审核",
    "dashboardV2.provider.auditStatus.rejected": "已拒绝",
    
    "dashboardV2.provider.lastCheck.label": "最后检查",
    "dashboardV2.provider.lastCheck.justNow": "刚刚",
    "dashboardV2.provider.lastCheck.minutesAgo": "{count} 分钟前",
    "dashboardV2.provider.lastCheck.hoursAgo": "{count} 小时前",
    "dashboardV2.provider.lastCheck.daysAgo": "{count} 天前",
    "dashboardV2.provider.lastCheck.unknown": "未知",

    // Error states (通用键)
    "dashboard.errors.loadFailed": "加载数据失败",
    "dashboard.errors.noData": "暂无数据",
    "dashboard.errors.retry": "重试",
    
    // Error states (v2 兼容键)
    "dashboardV2.error.loadFailed": "加载数据失败",
    "dashboardV2.error.noData": "暂无数据",
    "dashboardV2.errors.loadFailed": "加载数据失败",
    "dashboardV2.errors.noData": "暂无数据",
    "dashboardV2.errors.retry": "重试",
  },
};
