import type { Language } from "../i18n-context";

export const logicalModelsTranslations: Record<Language, Record<string, string>> = {
  en: {
    // Page
    "logical_models.title": "Logical Models",
    "logical_models.subtitle":
      "Manage business-facing logical models and their mappings to physical upstream models.",

    // Table
    "logical_models.table_title": "All Logical Models",
    "logical_models.table_description":
      "Logical models decouple your public model ids from underlying providers and physical models.",
    "logical_models.column_name": "Name",
    "logical_models.column_logical_id": "Logical ID",
    "logical_models.column_capabilities": "Capabilities",
    "logical_models.column_upstreams": "Upstreams",
    "logical_models.column_status": "Status",
    "logical_models.column_qps": "Max QPS",
    "logical_models.column_updated_at": "Last Updated",
    "logical_models.column_actions": "Actions",
    "logical_models.status_active": "Active",
    "logical_models.status_inactive": "Inactive",
    "logical_models.empty": "No logical models found. Configure providers and models to auto-generate mappings.",
    "logical_models.loading": "Loading logical models...",
    "logical_models.error_loading": "Failed to load logical models",
    "logical_models.action_view_details": "View details",

    // Detail dialog
    "logical_models.detail_title": "Logical Model Details",
    "logical_models.detail_basic_info": "Basic Information",
    "logical_models.detail_description": "Description",
    "logical_models.detail_capabilities": "Capabilities",
    "logical_models.detail_upstreams": "Mapped Upstreams",
    "logical_models.detail_upstreams_help":
      "Each upstream represents a concrete provider+model mapping that can serve this logical model.",
    "logical_models.detail.provider": "Provider",
    "logical_models.detail.model_id": "Model ID",
    "logical_models.detail.endpoint": "Endpoint",
    "logical_models.detail.region": "Region",
    "logical_models.detail.weight": "Weight",
    "logical_models.detail.max_qps": "Max QPS",
    "logical_models.detail.api_style": "API Style",
    "logical_models.detail.updated_at": "Updated At",
    "logical_models.detail.close": "Close",
  },
  zh: {
    // Page
    "logical_models.title": "逻辑模型",
    "logical_models.subtitle":
      "管理对外暴露的业务模型名称及其与底层物理模型的映射关系。",

    // Table
    "logical_models.table_title": "全部逻辑模型",
    "logical_models.table_description":
      "逻辑模型用于将业务侧的模型标识与不同厂商的物理模型解耦，支持平滑切换和多活路由。",
    "logical_models.column_name": "名称",
    "logical_models.column_logical_id": "逻辑 ID",
    "logical_models.column_capabilities": "能力",
    "logical_models.column_upstreams": "上游模型数",
    "logical_models.column_status": "状态",
    "logical_models.column_qps": "最大 QPS",
    "logical_models.column_updated_at": "最后更新",
    "logical_models.column_actions": "操作",
    "logical_models.status_active": "运行中",
    "logical_models.status_inactive": "未启用",
    "logical_models.empty": "当前没有逻辑模型。请先配置 Provider 和模型，系统会自动聚合出逻辑模型。",
    "logical_models.loading": "正在加载逻辑模型...",
    "logical_models.error_loading": "加载逻辑模型失败",
    "logical_models.action_view_details": "查看详情",

    // Detail dialog
    "logical_models.detail_title": "逻辑模型详情",
    "logical_models.detail_basic_info": "基础信息",
    "logical_models.detail_description": "描述",
    "logical_models.detail_capabilities": "能力",
    "logical_models.detail_upstreams": "上游映射",
    "logical_models.detail_upstreams_help":
      "每一行代表一个具体的 Provider + 物理模型组合，用于为该逻辑模型提供服务。",
    "logical_models.detail.provider": "Provider",
    "logical_models.detail.model_id": "模型 ID",
    "logical_models.detail.endpoint": "上游地址",
    "logical_models.detail.region": "区域",
    "logical_models.detail.weight": "权重",
    "logical_models.detail.max_qps": "最大 QPS",
    "logical_models.detail.api_style": "API 风格",
    "logical_models.detail.updated_at": "更新时间",
    "logical_models.detail.close": "关闭",
  },
};

