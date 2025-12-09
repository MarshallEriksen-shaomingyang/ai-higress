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
