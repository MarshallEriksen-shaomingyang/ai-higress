import { httpClient } from './client';

// 提供商类型定义
export type ProviderVisibility = 'public' | 'private' | 'restricted';
export type ProviderType = 'native' | 'aggregator';
export type TransportType = 'http' | 'sdk';
export type SdkVendor = 'openai' | 'google' | 'claude';
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
  api_keys?: ProviderApiKey[];
  created_at: string;
  updated_at: string;
}

// 模型接口
export interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
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
    visibility?: 'all' | 'private' | 'public'
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
};