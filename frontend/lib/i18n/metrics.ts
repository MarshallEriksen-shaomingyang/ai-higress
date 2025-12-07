import type { Language } from "../i18n-context";

export const metricsTranslations: Record<Language, Record<string, string>> = {
  en: {
    // Metrics pages
    "metrics.providers.title": "Provider Metrics",
    "metrics.providers.subtitle": "Aggregated performance metrics for all providers.",
    "metrics.providers.time_range": "Time range",
    "metrics.providers.time_today": "Today",
    "metrics.providers.time_7d": "Last 7 days",
    "metrics.providers.time_30d": "Last 30 days",
    "metrics.providers.time_all": "All time",
    "metrics.providers.loading": "Loading provider metrics...",
    "metrics.providers.empty": "No provider metrics",
    "metrics.providers.column.provider": "Provider",
    "metrics.providers.column.total_requests": "Total Requests",
    "metrics.providers.column.success_rate": "Success Rate",
    "metrics.providers.column.error_rate": "Error Rate",
    "metrics.providers.column.latency_p95": "P95 Latency",
  },
  zh: {
    // Metrics pages
    "metrics.providers.title": "Provider 指标",
    "metrics.providers.subtitle": "按 Provider 聚合的性能指标。",
    "metrics.providers.time_range": "时间范围",
    "metrics.providers.time_today": "今天",
    "metrics.providers.time_7d": "过去 7 天",
    "metrics.providers.time_30d": "过去 30 天",
    "metrics.providers.time_all": "全部时间",
    "metrics.providers.loading": "正在加载 Provider 指标...",
    "metrics.providers.empty": "暂无 Provider 指标数据",
    "metrics.providers.column.provider": "Provider",
    "metrics.providers.column.total_requests": "总请求数",
    "metrics.providers.column.success_rate": "成功率",
    "metrics.providers.column.error_rate": "错误率",
    "metrics.providers.column.latency_p95": "P95 延迟",
  },
};

