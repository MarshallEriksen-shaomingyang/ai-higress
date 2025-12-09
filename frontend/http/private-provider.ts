import { httpClient } from './client';

// 静态模型接口
export interface StaticModel {
  id: string;
  name?: string;
  description?: string;
}

// API 样式类型
export type ApiStyle = 'openai' | 'responses' | 'claude';

// SDK 厂商类型
export type SdkVendor = string;

// 私有提供商接口
export interface PrivateProvider {
  id: string;
  provider_id: string;
  name: string;
  base_url: string;
  provider_type: 'native' | 'aggregator';
  transport: 'http' | 'sdk';
  sdk_vendor: SdkVendor | null;
  weight: number;
  region?: string;
  cost_input?: number;
  cost_output?: number;
  max_qps?: number;
  retryable_status_codes?: number[];
  custom_headers?: Record<string, string>;
  models_path: string;
  messages_path?: string;
  chat_completions_path: string;
  responses_path?: string;
  static_models?: StaticModel[];
  supported_api_styles?: ApiStyle[];
  status: 'healthy' | 'degraded' | 'down';
  last_check?: string;
  preset_uuid?: string;
  owner_id: string;
  visibility: 'public' | 'private' | 'restricted';
  created_at: string;
  updated_at: string;
}

// 创建私有提供商请求
export interface CreatePrivateProviderRequest {
  preset_id?: string;
  name?: string;
  base_url?: string;
  api_key?: string;
  provider_type?: 'native' | 'aggregator';
  transport?: 'http' | 'sdk';
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
  static_models?: StaticModel[];
  supported_api_styles?: ApiStyle[];
}

// 更新私有提供商请求
export interface UpdatePrivateProviderRequest {
  name?: string;
  base_url?: string;
  provider_type?: 'native' | 'aggregator';
  transport?: 'http' | 'sdk';
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
  static_models?: StaticModel[];
  supported_api_styles?: ApiStyle[];
}

// 列表响应
export interface PrivateProviderListResponse {
  items: PrivateProvider[];
  total: number;
}

// 私有提供商服务
export const privateProviderService = {
  // 获取私有提供商列表
  getPrivateProviders: async (): Promise<PrivateProviderListResponse> => {
    const response = await httpClient.get('/v1/private-providers');
    return response.data;
  },

  // 获取单个私有提供商
  getPrivateProvider: async (providerId: string): Promise<PrivateProvider> => {
    const response = await httpClient.get(`/v1/private-providers/${providerId}`);
    return response.data;
  },

  // 创建私有提供商
  createPrivateProvider: async (
    data: CreatePrivateProviderRequest
  ): Promise<PrivateProvider> => {
    const response = await httpClient.post('/v1/private-providers', data);
    return response.data;
  },

  // 更新私有提供商
  updatePrivateProvider: async (
    providerId: string,
    data: UpdatePrivateProviderRequest
  ): Promise<PrivateProvider> => {
    const response = await httpClient.put(
      `/v1/private-providers/${providerId}`,
      data
    );
    return response.data;
  },

  // 删除私有提供商
  deletePrivateProvider: async (providerId: string): Promise<void> => {
    await httpClient.delete(`/v1/private-providers/${providerId}`);
  },

  // 健康检查
  checkHealth: async (providerId: string): Promise<{ status: string }> => {
    const response = await httpClient.post(
      `/v1/private-providers/${providerId}/health`
    );
    return response.data;
  },
};
