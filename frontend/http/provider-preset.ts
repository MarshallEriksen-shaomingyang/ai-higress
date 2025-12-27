import { httpClient } from './client';

export type SdkVendor = string;

// 提供商预设接口
export interface ProviderPreset {
  id: string;
  preset_id: string;
  display_name: string;
  description: string | null;
  provider_type: 'native' | 'aggregator';
  transport: 'http' | 'sdk';
  sdk_vendor: SdkVendor | null;
  base_url: string;
  models_path: string;
  messages_path: string | null;
  chat_completions_path: string;
  responses_path: string | null;
  images_generations_path: string | null;
  supported_api_styles: ('openai' | 'responses' | 'claude')[] | null;
  retryable_status_codes: number[] | null;
  custom_headers: Record<string, string> | null;
  static_models: any[] | null;
  created_at: string;
  updated_at: string;
}

// 创建请求
export interface CreateProviderPresetRequest {
  preset_id: string;
  display_name: string;
  description?: string | null;
  provider_type?: 'native' | 'aggregator';
  transport?: 'http' | 'sdk';
  sdk_vendor?: SdkVendor;
  base_url: string;
  models_path?: string;
  messages_path?: string | null;
  chat_completions_path?: string;
  responses_path?: string | null;
  images_generations_path?: string | null;
  supported_api_styles?: ('openai' | 'responses' | 'claude')[] | null;
  retryable_status_codes?: number[] | null;
  custom_headers?: Record<string, string> | null;
  static_models?: any[] | null;
}

// 更新请求
export interface UpdateProviderPresetRequest {
  display_name?: string | null;
  description?: string | null;
  provider_type?: 'native' | 'aggregator' | null;
  transport?: 'http' | 'sdk' | null;
  sdk_vendor?: SdkVendor | null;
  base_url?: string | null;
  models_path?: string | null;
  messages_path?: string | null;
  chat_completions_path?: string | null;
  responses_path?: string | null;
  images_generations_path?: string | null;
  supported_api_styles?: ('openai' | 'responses' | 'claude')[] | null;
  retryable_status_codes?: number[] | null;
  custom_headers?: Record<string, string> | null;
  static_models?: any[] | null;
}

// 列表响应
export interface ProviderPresetListResponse {
  items: ProviderPreset[];
  total: number;
}

export interface ProviderPresetImportError {
  preset_id: string;
  reason: string;
}

export interface ProviderPresetImportRequest {
  presets: CreateProviderPresetRequest[];
  overwrite?: boolean;
}

export interface ProviderPresetImportResult {
  created: string[];
  updated: string[];
  skipped: string[];
  failed: ProviderPresetImportError[];
}

export interface ProviderPresetExportResponse {
  presets: CreateProviderPresetRequest[];
  total: number;
}

// 提供商预设服务
export const providerPresetService = {
  // 获取预设列表（所有用户可访问）
  getProviderPresets: async (): Promise<ProviderPresetListResponse> => {
    const response = await httpClient.get('/provider-presets');
    return response.data;
  },

  // 创建预设（仅管理员）
  createProviderPreset: async (
    data: CreateProviderPresetRequest
  ): Promise<ProviderPreset> => {
    const response = await httpClient.post('/admin/provider-presets', data);
    return response.data;
  },

  // 更新预设（仅管理员）
  updateProviderPreset: async (
    presetId: string,
    data: UpdateProviderPresetRequest
  ): Promise<ProviderPreset> => {
    const response = await httpClient.put(
      `/admin/provider-presets/${presetId}`,
      data
    );
    return response.data;
  },

  // 删除预设（仅管理员）
  deleteProviderPreset: async (presetId: string): Promise<void> => {
    await httpClient.delete(`/admin/provider-presets/${presetId}`);
  },

  // 导出预设（仅管理员）
  exportProviderPresets: async (): Promise<ProviderPresetExportResponse> => {
    const response = await httpClient.get('/admin/provider-presets/export');
    return response.data;
  },

  // 导入预设（仅管理员）
  importProviderPresets: async (
    payload: ProviderPresetImportRequest
  ): Promise<ProviderPresetImportResult> => {
    const response = await httpClient.post('/admin/provider-presets/import', payload);
    return response.data;
  },
};
