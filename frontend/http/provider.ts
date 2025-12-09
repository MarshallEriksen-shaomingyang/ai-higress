import { httpClient } from './client';

// 提供商类型定义
export type ProviderVisibility = 'public' | 'private' | 'restricted';
export type ProviderType = 'native' | 'aggregator';
export type TransportType = 'http' | 'sdk';
export type SdkVendor = string;
export type ProviderStatus = 'healthy' | 'degraded' | 'down';

// API Key 接口
export interface ProviderApiKey {
  key: string;
  weight: number;
  max_qps: number;
  label: string;
}

// 提供商接口
export interface Provider {
  id: string;
  provider_id: string;
  name: string;
  base_url: string;
  transport: TransportType;
  provider_type: ProviderType;
  sdk_vendor: SdkVendor | null;
  visibility: ProviderVisibility;
  owner_id: string | null;
  status: ProviderStatus;
  weight: number;
  region: string | null;
  cost_input: number;
  cost_output: number;
  billing_factor: number;
  max_qps: number | null;
  retryable_status_codes: number[] | null;
  custom_headers: Record<string, string> | null;
  models_path: string;
  messages_path: string | null;
  chat_completions_path: string;
  responses_path: string | null;
  supported_api_styles: string[] | null;
  static_models: any[] | null;
  shared_user_ids?: string[] | null;
  api_keys?: ProviderApiKey[];
  created_at: string;
  updated_at: string;
}

// Provider 模型接口（来自 `/providers/{id}/models`）
// 注意：后端已经对不同厂商的模型做了一层标准化：
// - 顶层字段是统一的（model_id / provider_id / family / display_name / context_length / capabilities / pricing / metadata / meta_hash）
// - metadata 中保留了各个厂商原始的模型信息（如 OpenAI 的 id / created / owned_by 等）
export interface ModelMetadata {
  id?: string;
  object?: string;
  created?: number;
  owned_by?: string;
  // 其它厂商自定义字段
  [key: string]: any;
}

export interface Model {
  model_id: string;
  provider_id: string;
  family: string;
  display_name: string;
  context_length: number;
  // 后端返回的是 Enum 的字符串值，例如 "chat" / "embedding" 等
  capabilities: string[];
  pricing: Record<string, number> | null;
   // 可选的模型别名，用于将长版本 ID 映射为更易记的短名称
  alias?: string | null;
  metadata?: ModelMetadata | null;
  meta_hash?: string | null;
}

// 管理端：provider+model 维度的计费配置
export interface ProviderModelPricing {
  provider_id: string;
  model_id: string;
  pricing: Record<string, number> | null;
}

// provider+model 维度的别名映射配置
export interface ProviderModelAlias {
  provider_id: string;
  model_id: string;
  alias: string | null;
}

export interface ProviderSharedUsersResponse {
  provider_id: string;
  visibility: ProviderVisibility;
  shared_user_ids: string[];
}

export interface UpdateProviderSharedUsersRequest {
  user_ids: string[];
}

export interface SDKVendorsResponse {
  vendors: SdkVendor[];
  total: number;
}

// 模型列表响应
export interface ModelsResponse {
  models: Model[];
  total: number;
}

// 健康状态接口
export interface HealthStatus {
  status: ProviderStatus;
  last_check: number;
  metadata: Record<string, any>;
}

// 提供商指标接口
export interface ProviderMetrics {
  logical_model: string;
  provider_id: string;
  latency_p95_ms: number;
  latency_p99_ms: number;
  error_rate: number;
  success_qps_1m: number;
  total_requests_1m: number;
  last_updated: number;
  status: ProviderStatus;
  // 额外字段用于计算
  avg_latency_ms: number;
  success_rate: number;
  total_requests: number;
  total_failures: number;
  window_start: number;
}

// 指标响应
export interface MetricsResponse {
  metrics: ProviderMetrics[];
}

// 用户可用提供商响应
export interface UserAvailableProvidersResponse {
  private_providers: Provider[];
  shared_providers: Provider[];
  public_providers: Provider[];
  total: number;
}

// 创建私有提供商请求
export interface CreatePrivateProviderRequest {
  name: string;
  base_url: string;
  api_key: string;
  provider_type?: ProviderType;
  transport?: TransportType;
  sdk_vendor?: SdkVendor;
  weight?: number;
  region?: string;
  cost_input?: number;
  cost_output?: number;
  max_qps?: number;
  retryable_status_codes?: number[];
  custom_headers?: Record<string, string>;
  models_path?: string;
  messages_path?: string;
  chat_completions_path?: string;
  responses_path?: string;
  supported_api_styles?: string[];
  static_models?: any[];
}

// 更新私有提供商请求
export interface UpdatePrivateProviderRequest {
  name?: string;
  base_url?: string;
  provider_type?: ProviderType;
  transport?: TransportType;
  sdk_vendor?: SdkVendor;
  weight?: number;
  region?: string;
  cost_input?: number;
  cost_output?: number;
  max_qps?: number;
  retryable_status_codes?: number[];
  custom_headers?: Record<string, string>;
  models_path?: string;
  messages_path?: string;
  chat_completions_path?: string;
  responses_path?: string;
  supported_api_styles?: string[];
  static_models?: any[];
}

// 提供商服务
export const providerService = {
  /**
   * 获取用户可用的提供商列表（私有 + 公共）
   */
  getUserAvailableProviders: async (
    userId: string,
    visibility?: 'all' | 'private' | 'public' | 'shared'
  ): Promise<UserAvailableProvidersResponse> => {
    const params = visibility ? { visibility } : {};
    const response = await httpClient.get(`/users/${userId}/providers`, { params });
    return response.data;
  },

  /**
   * 获取用户的私有提供商列表
   */
  getUserPrivateProviders: async (userId: string): Promise<Provider[]> => {
    const response = await httpClient.get(`/users/${userId}/private-providers`);
    return response.data;
  },

  /**
   * 创建私有提供商
   */
  createPrivateProvider: async (
    userId: string,
    data: CreatePrivateProviderRequest
  ): Promise<Provider> => {
    const response = await httpClient.post(
      `/users/${userId}/private-providers`,
      data
    );
    return response.data;
  },

  /**
   * 更新私有提供商
   */
  updatePrivateProvider: async (
    userId: string,
    providerId: string,
    data: UpdatePrivateProviderRequest
  ): Promise<Provider> => {
    const response = await httpClient.put(
      `/users/${userId}/private-providers/${providerId}`,
      data
    );
    return response.data;
  },

  /**
   * 删除私有提供商
   */
  deletePrivateProvider: async (
    userId: string,
    providerId: string
  ): Promise<void> => {
    await httpClient.delete(`/users/${userId}/private-providers/${providerId}`);
  },

  /**
   * 获取指定提供商信息
   */
  getProvider: async (providerId: string): Promise<Provider> => {
    const response = await httpClient.get(`/providers/${providerId}`);
    return response.data;
  },

  /**
   * 获取提供商模型列表
   */
  getProviderModels: async (providerId: string): Promise<ModelsResponse> => {
    const response = await httpClient.get(`/providers/${providerId}/models`);
    return response.data;
  },

  /**
   * 检查提供商健康状态
   */
  checkProviderHealth: async (providerId: string): Promise<HealthStatus> => {
    const response = await httpClient.get(`/providers/${providerId}/health`);
    return response.data;
  },

  /**
   * 获取提供商路由指标（实时快照）
   */
  getProviderMetrics: async (
    providerId: string,
    logicalModel?: string
  ): Promise<MetricsResponse> => {
    const params = logicalModel ? { logical_model: logicalModel } : {};
    const response = await httpClient.get(`/providers/${providerId}/metrics`, { params });
    return response.data;
  },

  /**
   * 获取指定 provider+model 的别名映射配置
   */
  getProviderModelAlias: async (
    providerId: string,
    modelId: string
  ): Promise<ProviderModelAlias> => {
    const response = await httpClient.get(
      `/providers/${providerId}/models/${encodeURIComponent(modelId)}/mapping`
    );
    return response.data;
  },

  /**
   * 更新指定 provider+model 的别名映射配置
   */
  updateProviderModelAlias: async (
    providerId: string,
    modelId: string,
    data: { alias?: string | null }
  ): Promise<ProviderModelAlias> => {
    const response = await httpClient.put(
      `/providers/${providerId}/models/${encodeURIComponent(modelId)}/mapping`,
      data
    );
    return response.data;
  },

  /**
   * 获取指定 provider+model 的计费配置（管理员接口）
   */
  getProviderModelPricing: async (
    providerId: string,
    modelId: string
  ): Promise<ProviderModelPricing> => {
    const response = await httpClient.get(
      `/admin/providers/${providerId}/models/${encodeURIComponent(modelId)}/pricing`
    );
    return response.data;
  },

  /**
   * 查询或更新私有 Provider 的授权用户列表
   */
  getProviderSharedUsers: async (
    userId: string,
    providerId: string
  ): Promise<ProviderSharedUsersResponse> => {
    const response = await httpClient.get(
      `/users/${userId}/private-providers/${providerId}/shared-users`
    );
    return response.data;
  },

  updateProviderSharedUsers: async (
    userId: string,
    providerId: string,
    data: UpdateProviderSharedUsersRequest
  ): Promise<ProviderSharedUsersResponse> => {
    const response = await httpClient.put(
      `/users/${userId}/private-providers/${providerId}/shared-users`,
      data
    );
    return response.data;
  },

  /**
   * 更新指定 provider+model 的计费配置（管理员接口）
   */
  updateProviderModelPricing: async (
    providerId: string,
    modelId: string,
    data: { input?: number; output?: number } | null
  ): Promise<ProviderModelPricing> => {
    const response = await httpClient.put(
      `/admin/providers/${providerId}/models/${encodeURIComponent(modelId)}/pricing`,
      data
    );
    return response.data;
  },

  /**
   * 获取已注册的 SDK 厂商列表
   */
  getSdkVendors: async (): Promise<SDKVendorsResponse> => {
    const response = await httpClient.get('/providers/sdk-vendors');
    return response.data;
  },
};
