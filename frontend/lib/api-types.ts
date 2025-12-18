// API 类型定义文件
// 此文件包含所有与后端 API 交互的 TypeScript 类型定义

// ============= 认证相关 =============
export interface UserInfo {
  id: string;
  username: string;
  email: string;
  display_name: string | null;
  avatar: string | null;
  is_active: boolean;
  is_superuser: boolean;
  role_codes?: string[];
  permission_flags?: Array<{
    key: string;
    value: boolean;
  }>;
  /**
   * 自动充值规则（管理员列表接口返回）；未配置时为 null。
   */
  credit_auto_topup?: CreditAutoTopupConfig | null;
  created_at: string;
  updated_at: string;
}

// ============= API 密钥相关 =============
export interface ApiKey {
  id: string;
  user_id: string;
  name: string;
  key_prefix: string;
  expiry_type: 'week' | 'month' | 'year' | 'never';
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  has_provider_restrictions: boolean;
  allowed_provider_ids: string[];
  token?: string; // 仅在创建时返回
}

export interface CreateApiKeyRequest {
  name: string;
  expiry?: 'week' | 'month' | 'year' | 'never';
  allowed_provider_ids?: string[];
}

export interface UpdateApiKeyRequest {
  name?: string;
  expiry?: 'week' | 'month' | 'year' | 'never';
  allowed_provider_ids?: string[];
}

// ============= 积分相关 =============
export interface CreditAccount {
  id: string;
  user_id: string;
  balance: number;
  daily_limit: number | null;
  status: 'active' | 'suspended';
  created_at: string;
  updated_at: string;
}

export interface CreditTransaction {
  id: string;
  account_id: string;
  user_id: string;
  api_key_id: string | null;
  amount: number;
  /**
   * 后端实际可能值示例：
   * - usage / stream_usage / stream_estimate
   * - admin_topup / auto_daily_topup / adjust 等
   *
   * 这里用 string 而不是严格枚举，避免前后端不一致导致类型错误。
   */
  reason: string;
  description: string | null;
  model_name: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  created_at: string;
}

export interface TopupRequest {
  amount: number;
  description?: string;
}

export interface CreditAutoTopupConfig {
  id: string;
  user_id: string;
  min_balance_threshold: number;
  target_balance: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreditAutoTopupConfigInput {
  min_balance_threshold: number;
  target_balance: number;
  is_active: boolean;
}

export interface CreditAutoTopupBatchRequest extends CreditAutoTopupConfigInput {
  user_ids: string[];
}

export interface CreditAutoTopupBatchResponse {
  updated_count: number;
  configs: CreditAutoTopupConfig[];
}

export interface TransactionQueryParams {
  limit?: number;
  offset?: number;
  start_date?: string;
  end_date?: string;
  reason?: string;
}

// ============= 厂商密钥相关 =============
export interface ProviderKey {
  id: string;
  provider_id: string;
  label: string;
  key_prefix?: string;  // 前端显示用，后端不返回完整密钥
  weight: number;
  max_qps: number | null;
  status: 'active' | 'inactive';
  created_at: string;
  updated_at: string | null;
}

export interface CreateProviderKeyRequest {
  key: string;
  label: string;
  weight?: number;
  max_qps?: number;
  status?: 'active' | 'inactive';
}

export interface UpdateProviderKeyRequest {
  key?: string;
  label?: string;
  weight?: number;
  max_qps?: number;
  status?: 'active' | 'inactive';
}

// ============= 会话管理相关 =============
export interface DeviceInfo {
  user_agent: string | null;
  ip_address: string | null;
}

export interface SessionResponse {
  session_id: string;
  created_at: string;
  last_used_at: string;
  device_info: DeviceInfo | null;
  is_current: boolean;
}

export interface ParsedDeviceInfo {
  browser: string;
  os: string;
  deviceType: 'desktop' | 'mobile' | 'tablet' | 'unknown';
  icon: 'Monitor' | 'Smartphone' | 'Tablet' | 'HelpCircle';
}

// ============= 用户权限相关 =============
export interface UserPermission {
  id: string;
  user_id: string;
  permission_type: string;
  permission_value: string | null;
  expires_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface GrantPermissionRequest {
  permission_type: string;
  permission_value?: string;
  expires_at?: string;
  notes?: string;
}

// ============= 指标 / Metrics =============

export interface MetricsDataPoint {
  window_start: string;
  total_requests: number;
  success_requests: number;
  error_requests: number;
  latency_avg_ms: number;
  latency_p95_ms: number;
  latency_p99_ms: number;
  error_rate: number;
}

export interface OverviewMetricsSummary {
  /**
   * 时间范围：today / 7d / 30d / all
   */
  time_range: string;
  /**
   * 传输模式过滤：http / sdk / all
   */
  transport: string;
  /**
   * 流式过滤：true / false / all
   */
  is_stream: string;

  total_requests: number;
  success_requests: number;
  error_requests: number;
  success_rate: number;

  total_requests_prev: number | null;
  success_requests_prev: number | null;
  error_requests_prev: number | null;
  success_rate_prev: number | null;

  active_providers: number;
  active_providers_prev: number | null;
}

export interface ActiveProviderMetrics {
  provider_id: string;
  total_requests: number;
  success_requests: number;
  error_requests: number;
  success_rate: number;
  latency_p95_ms: number | null;
}

export interface OverviewActiveProviders {
  time_range: string;
  transport: string;
  is_stream: string;
  items: ActiveProviderMetrics[];
}

export interface OverviewMetricsTimeSeries {
  time_range: string;
  bucket: string;
  transport: string;
  is_stream: string;
  points: MetricsDataPoint[];
}

export interface UserOverviewMetricsSummary {
  scope: "user";
  user_id: string;
  time_range: string;
  transport: string;
  is_stream: string;
  total_requests: number;
  success_requests: number;
  error_requests: number;
  success_rate: number;
  total_requests_prev: number | null;
  success_requests_prev: number | null;
  error_requests_prev: number | null;
  success_rate_prev: number | null;
  active_providers: number;
  active_providers_prev: number | null;
}

export interface UserActiveProviderMetrics {
  provider_id: string;
  total_requests: number;
  success_requests: number;
  error_requests: number;
  success_rate: number;
  latency_p95_ms: number | null;
}

export interface UserOverviewActiveProviders {
  scope: "user";
  user_id: string;
  time_range: string;
  transport: string;
  is_stream: string;
  items: UserActiveProviderMetrics[];
}

export interface UserOverviewMetricsTimeSeries {
  scope: "user";
  user_id: string;
  time_range: string;
  bucket: string;
  transport: string;
  is_stream: string;
  points: MetricsDataPoint[];
}

export interface UserAppUsageMetrics {
  app_name: string;
  total_requests: number;
  last_seen_at: string | null;
}

export interface UserOverviewAppUsage {
  scope: "user";
  user_id: string;
  time_range: string;
  items: UserAppUsageMetrics[];
}

// ============= 注册窗口 / Registration Windows =============

export type RegistrationWindowStatus = "scheduled" | "active" | "closed";

export interface RegistrationWindow {
  id: string;
  start_time: string;
  end_time: string;
  max_registrations: number;
  registered_count: number;
  auto_activate: boolean;
  status: RegistrationWindowStatus;
  created_at: string;
  updated_at: string;
}

export interface CreateRegistrationWindowRequest {
  start_time: string;
  end_time: string;
  max_registrations: number;
}

// ============= 系统配置 / 网关信息 =============

export interface GatewayConfig {
  api_base_url: string;
  max_concurrent_requests: number;
  request_timeout_ms: number;
  cache_ttl_seconds: number;
  probe_prompt?: string | null;
}

export interface ProviderLimits {
  default_user_private_provider_limit: number;
  max_user_private_provider_limit: number;
  require_approval_for_shared_providers: boolean;
}

export type UpdateProviderLimitsRequest = ProviderLimits;

// ============= 逻辑模型 / Logical Models =============

export type ModelCapability =
  | "chat"
  | "completion"
  | "embedding"
  | "vision"
  | "audio"
  | "function_calling";

export type ApiStyle = "openai" | "responses" | "claude";

export interface LogicalModelUpstream {
  provider_id: string;
  model_id: string;
  endpoint: string;
  base_weight: number;
  region: string | null;
  max_qps: number | null;
  cost_input?: number | null;
  cost_output?: number | null;
  meta_hash: string | null;
  updated_at: number;
  api_style: ApiStyle;
}

export interface LogicalModel {
  logical_id: string;
  display_name: string;
  description: string;
  capabilities: ModelCapability[];
  upstreams: LogicalModelUpstream[];
  enabled: boolean;
  updated_at: number;
}

export interface LogicalModelsResponse {
  models: LogicalModel[];
  total: number;
}

export interface LogicalModelUpstreamsResponse {
  upstreams: LogicalModelUpstream[];
}

export type UpdateGatewayConfigRequest = GatewayConfig;

// ============= 通知相关 =============

export type NotificationLevel = 'info' | 'success' | 'warning' | 'error';
export type NotificationTargetType = 'all' | 'users' | 'roles';

export interface Notification {
  id: string;
  title: string;
  content: string;
  level: NotificationLevel;
  target_type: NotificationTargetType;
  target_user_ids: string[];
  target_role_codes: string[];
  link_url: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  is_read: boolean;
  read_at: string | null;
}

export interface NotificationAdminView {
  id: string;
  title: string;
  content: string;
  level: NotificationLevel;
  target_type: NotificationTargetType;
  target_user_ids: string[];
  target_role_codes: string[];
  link_url: string | null;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

export interface CreateNotificationRequest {
  title: string;
  content: string;
  level?: NotificationLevel;
  target_type: NotificationTargetType;
  target_user_ids?: string[];
  target_role_codes?: string[];
  link_url?: string;
  expires_at?: string;
}

export interface MarkNotificationsReadRequest {
  notification_ids: string[];
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface NotificationQueryParams {
  status?: 'all' | 'unread';
  limit?: number;
  offset?: number;
}

// ============= 仪表盘概览页相关 =============

export interface CreditConsumptionSummary {
  time_range: string;
  total_consumption: number;
  daily_average: number;
  projected_days_left: number;
  current_balance: number;
  daily_limit?: number;
  warning_threshold: number; // 预警阈值（天数）
}

export interface ProviderConsumption {
  provider_id: string;
  provider_name: string;
  total_consumption: number;
  request_count: number;
  success_rate: number;
  latency_p95_ms?: number;
  percentage_of_total: number;
}

export interface SuccessRateTrend {
  timestamp: string;
  overall_success_rate: number;
  provider_success_rates: {
    provider_id: string;
    success_rate: number;
  }[];
}

export interface ActiveModel {
  model_id: string;
  model_name: string;
  call_count: number;
  success_rate: number;
  failure_count?: number;
}

export interface OverviewEvent {
  id: string;
  event_type: 'rate_limit' | 'error' | 'warning' | 'info';
  title: string;
  description: string;
  timestamp: string;
  provider_id?: string;
  model_id?: string;
}

export interface CreditConsumptionProvidersResponse {
  time_range: string;
  providers: ProviderConsumption[];
  total_consumption: number;
}

export interface ActiveModelsResponse {
  most_called: ActiveModel[];
  most_failed: ActiveModel[];
}

export interface OverviewEventsResponse {
  events: OverviewEvent[];
  total_count: number;
}

// ============= 上游代理池管理 =============

export type UpstreamProxySourceType = 'static_list' | 'remote_text_list';
export type UpstreamProxyScheme = 'http' | 'https' | 'socks5' | 'socks5h';
export type UpstreamProxySelectionStrategy = 'random' | 'round_robin';
export type UpstreamProxyHealthcheckMethod = 'GET' | 'HEAD';

export interface UpstreamProxyConfig {
  id: string;
  enabled: boolean;
  selection_strategy: UpstreamProxySelectionStrategy;
  failure_cooldown_seconds: number;
  healthcheck_url: string;
  healthcheck_timeout_ms: number;
  healthcheck_method: UpstreamProxyHealthcheckMethod;
  healthcheck_interval_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface UpdateUpstreamProxyConfigRequest {
  enabled?: boolean;
  failure_cooldown_seconds?: number;
  healthcheck_url?: string;
  healthcheck_timeout_ms?: number;
  healthcheck_method?: UpstreamProxyHealthcheckMethod;
  healthcheck_interval_seconds?: number;
}

export interface UpstreamProxyStatus {
  config_enabled: boolean;
  total_sources: number;
  total_endpoints: number;
  available_endpoints: number;
}

export interface UpstreamProxySource {
  id: string;
  name: string;
  source_type: UpstreamProxySourceType;
  enabled: boolean;
  default_scheme: UpstreamProxyScheme;
  refresh_interval_seconds: number | null;
  remote_url_masked: string | null;
  last_refresh_at: string | null;
  last_refresh_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateUpstreamProxySourceRequest {
  name: string;
  source_type: UpstreamProxySourceType;
  enabled?: boolean;
  default_scheme?: UpstreamProxyScheme;
  refresh_interval_seconds?: number;
  remote_url?: string;
  remote_headers?: Record<string, string>;
}

export interface UpdateUpstreamProxySourceRequest {
  name?: string;
  enabled?: boolean;
  default_scheme?: UpstreamProxyScheme;
  refresh_interval_seconds?: number;
  remote_url?: string;
  remote_headers?: Record<string, string>;
}

export interface UpstreamProxyEndpoint {
  id: string;
  source_id: string;
  scheme: UpstreamProxyScheme;
  host: string;
  port: number;
  username: string | null;
  enabled: boolean;
  last_ok: boolean | null;
  last_latency_ms: number | null;
  consecutive_failures: number;
  last_error: string | null;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateUpstreamProxyEndpointRequest {
  source_id: string;
  scheme: UpstreamProxyScheme;
  host: string;
  port: number;
  username?: string;
  password?: string;
  enabled?: boolean;
}

export interface UpdateUpstreamProxyEndpointRequest {
  enabled?: boolean;
}

export interface UpstreamProxyImportRequest {
  source_id: string;
  default_scheme: UpstreamProxyScheme;
  text: string;
}

export interface UpstreamProxyImportResponse {
  inserted_or_updated: number;
}

export interface UpstreamProxyTaskResponse {
  task_id: string;
}

export interface UpstreamProxySourcesResponse {
  sources: UpstreamProxySource[];
  total: number;
}

export interface UpstreamProxyEndpointsResponse {
  endpoints: UpstreamProxyEndpoint[];
  total: number;
}

// ============= Dashboard v2 用户页相关 =============

/**
 * Dashboard v2 KPI 数据
 */
export interface DashboardV2KPIData {
  time_range: string;
  total_requests: number;
  error_rate: number;
  latency_p95_ms: number;
  tokens: {
    input: number;
    output: number;
    total: number;
    estimated_requests: number;
  };
  credits_spent: number;
}

/**
 * Dashboard v2 Pulse 数据点（分钟粒度）
 */
export interface DashboardV2PulseDataPoint {
  window_start: string;
  total_requests: number;
  error_4xx_requests: number;
  error_5xx_requests: number;
  error_429_requests: number;
  error_timeout_requests: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  latency_p99_ms: number;
}

/**
 * Dashboard v2 Pulse 响应
 */
export interface DashboardV2PulseResponse {
  points: DashboardV2PulseDataPoint[];
}

/**
 * Dashboard v2 Token 数据点
 */
export interface DashboardV2TokenDataPoint {
  window_start: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_requests: number;
}

/**
 * Dashboard v2 Token 趋势响应
 */
export interface DashboardV2TokensResponse {
  time_range: string;
  bucket: string;
  points: DashboardV2TokenDataPoint[];
}

/**
 * Dashboard v2 Top Model 项
 */
export interface DashboardV2TopModelItem {
  model: string;
  requests: number;
  tokens_total: number;
}

/**
 * Dashboard v2 Top Models 响应
 */
export interface DashboardV2TopModelsResponse {
  items: DashboardV2TopModelItem[];
}

/**
 * Dashboard v2 Provider 成本项
 */
export interface DashboardV2ProviderCostItem {
  provider_id: string;
  credits_spent: number;
  transactions: number;
}

/**
 * Dashboard v2 Provider 指标点（用于卡片小图）
 */
export interface DashboardV2ProviderMetricPoint {
  window_start: string;
  qps: number;
  error_rate: number;
}

/**
 * Dashboard v2 Provider 指标项（用于用户 Provider 卡片）
 */
export interface DashboardV2ProviderMetricsItem {
  provider_id: string;
  total_requests: number;
  error_rate: number;
  latency_p95_ms: number;
  qps: number;
  points: DashboardV2ProviderMetricPoint[];
}

/**
 * Dashboard v2 Provider 指标响应（用于用户 Provider 卡片）
 */
export interface DashboardV2ProvidersMetricsResponse {
  time_range: string;
  bucket: string;
  items: DashboardV2ProviderMetricsItem[];
}

/**
 * Dashboard v2 成本结构响应
 */
export interface DashboardV2CostByProviderResponse {
  items: DashboardV2ProviderCostItem[];
}

// ============= Dashboard v2 系统页相关 =============

/**
 * Dashboard v2 系统页 KPI 数据
 * 注意：系统页没有 credits_spent 字段
 */
export interface SystemKPIData {
  time_range: string;
  total_requests: number;
  error_rate: number;
  latency_p95_ms: number;
  tokens: {
    input: number;
    output: number;
    total: number;
    estimated_requests: number;
  };
}

/**
 * Provider 状态项（系统页）
 */
export interface ProviderStatusItem {
  provider_id: string;
  operation_status: 'active' | 'inactive' | 'maintenance';
  status: 'healthy' | 'degraded' | 'unhealthy'; // 健康状态
  audit_status: 'approved' | 'pending' | 'rejected';
  last_check: string; // ISO 8601 格式
}

/**
 * Dashboard v2 系统页 Provider 状态响应
 */
export interface SystemDashboardProvidersResponse {
  items: ProviderStatusItem[];
}
