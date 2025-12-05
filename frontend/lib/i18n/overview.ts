import type { Language } from "../i18n-context";

export const overviewTranslations: Record<Language, Record<string, string>> = {
  en: {
    // Overview dashboard page
    "overview.title": "Dashboard Overview",
    "overview.subtitle": "Welcome back, here's what's happening today.",
    "overview.total_requests": "Total Requests",
    "overview.active_providers": "Active Providers",
    "overview.cache_hit_rate": "Cache Hit Rate",
    "overview.from_last_month": "from last month",
    "overview.view_all": "View All",
    "overview.status_healthy": "Healthy",
    "overview.status_degraded": "Degraded",
    "overview.recent_activity": "Recent Activity",
    "overview.recent_activity_placeholder": "Activity Chart Placeholder",
    // Hero section
    "hero.welcome": "Welcome to AI Higress, a powerful API gateway designed for the AI era. This project demonstrates a unique \"Ink Wash\" (Shui-mo) design language, blending traditional Chinese aesthetics with modern web technology.",
    "hero.explore": "Explore our dashboard to see the style in action, managing AI providers and metrics with elegance.",
  },
  zh: {
    // Overview dashboard page
    "overview.title": "仪表盘概览",
    "overview.subtitle": "欢迎回来，以下是今天的整体运行情况。",
    "overview.total_requests": "总请求数",
    "overview.active_providers": "活跃提供商",
    "overview.cache_hit_rate": "缓存命中率",
    "overview.from_last_month": "相比上个月",
    "overview.view_all": "查看全部",
    "overview.status_healthy": "健康",
    "overview.status_degraded": "性能下降",
    "overview.recent_activity": "近期活动",
    "overview.recent_activity_placeholder": "活动图表占位",
    // Hero section
    "hero.welcome": "欢迎使用 AI Higress，专为 AI 时代打造的强大 API 网关。本项目展示了独特的"水墨"设计语言，将中国传统美学与现代 Web 技术完美融合。",
    "hero.explore": "探索我们的仪表盘，体验优雅地管理 AI 提供商和指标。",
  },
};
