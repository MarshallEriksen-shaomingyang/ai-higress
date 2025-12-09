import { httpClient } from './client';
import type {
  GatewayConfig,
  ProviderLimits,
  UpdateGatewayConfigRequest,
  UpdateProviderLimitsRequest,
} from '@/lib/api-types';

// 系统管理相关接口
export interface GenerateSecretKeyRequest {
  length?: number;
}

export interface GenerateSecretKeyResponse {
  secret_key: string;
}

export interface InitAdminRequest {
  username: string;
  email: string;
  display_name?: string;
}

export interface InitAdminResponse {
  username: string;
  email: string;
  password: string;
  api_key: string;
}

export interface ValidateKeyRequest {
  key: string;
}

export interface ValidateKeyResponse {
  is_valid: boolean;
  message: string;
}

export interface SystemStatusResponse {
  status: string;
  message: string;
}

export type CacheSegment =
  | "models"
  | "metrics_overview"
  | "provider_models"
  | "logical_models"
  | "routing_metrics";

export interface CacheClearResponse {
  cleared_keys: number;
  patterns: Record<string, number>;
}

// 系统管理服务
export const systemService = {
  // 生成系统主密钥
  generateSecretKey: async (
    data?: GenerateSecretKeyRequest
  ): Promise<GenerateSecretKeyResponse> => {
    const response = await httpClient.post('/system/secret-key/generate', data || {});
    return response.data;
  },

  // 初始化系统管理员
  initAdmin: async (data: InitAdminRequest): Promise<InitAdminResponse> => {
    const response = await httpClient.post('/system/admin/init', data);
    return response.data;
  },

  // 轮换系统主密钥
  rotateSecretKey: async (): Promise<GenerateSecretKeyResponse> => {
    const response = await httpClient.post('/system/secret-key/rotate');
    return response.data;
  },

  // 验证密钥强度
  validateKey: async (data: ValidateKeyRequest): Promise<ValidateKeyResponse> => {
    const response = await httpClient.post('/system/key/validate', data);
    return response.data;
  },

  // 获取系统状态
  getSystemStatus: async (): Promise<SystemStatusResponse> => {
    const response = await httpClient.get('/system/status');
    return response.data;
  },

  // 清理网关相关缓存
  clearCache: async (segments?: CacheSegment[]): Promise<CacheClearResponse> => {
    const response = await httpClient.post('/system/cache/clear', {
      segments: segments ?? [],
    });
    return response.data;
  },

  // 获取中转网关基础配置
  getGatewayConfig: async (): Promise<GatewayConfig> => {
    const response = await httpClient.get('/system/gateway-config');
    return response.data;
  },

  // 更新中转网关基础配置
  updateGatewayConfig: async (
    data: UpdateGatewayConfigRequest
  ): Promise<GatewayConfig> => {
    const response = await httpClient.put('/system/gateway-config', data);
    return response.data;
  },

  // 获取 Provider 限制配置
  getProviderLimits: async (): Promise<ProviderLimits> => {
    const response = await httpClient.get('/system/provider-limits');
    return response.data;
  },

  // 更新 Provider 限制配置
  updateProviderLimits: async (
    data: UpdateProviderLimitsRequest
  ): Promise<ProviderLimits> => {
    const response = await httpClient.put('/system/provider-limits', data);
    return response.data;
  },
};

export type { ProviderLimits, UpdateProviderLimitsRequest } from '@/lib/api-types';
