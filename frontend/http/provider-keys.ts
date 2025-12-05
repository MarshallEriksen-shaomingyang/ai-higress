import { httpClient } from './client';
import type { 
  ProviderKey, 
  CreateProviderKeyRequest, 
  UpdateProviderKeyRequest 
} from '@/lib/api-types';

/**
 * 厂商密钥管理 API 服务
 */
export const providerKeyService = {
  /**
   * 获取指定提供商的所有 API 密钥
   * @param providerId 提供商ID
   * @returns API 密钥列表
   */
  getKeys: async (providerId: string): Promise<ProviderKey[]> => {
    const response = await httpClient.get(`/providers/${providerId}/keys`);
    return response.data;
  },

  /**
   * 获取单个密钥详情
   * @param providerId 提供商ID
   * @param keyId 密钥ID
   * @returns 密钥详情
   */
  getKey: async (providerId: string, keyId: string): Promise<ProviderKey> => {
    const response = await httpClient.get(`/providers/${providerId}/keys/${keyId}`);
    return response.data;
  },

  /**
   * 创建新的厂商 API 密钥
   * @param providerId 提供商ID
   * @param data 创建请求数据
   * @returns 创建的密钥信息
   */
  createKey: async (
    providerId: string, 
    data: CreateProviderKeyRequest
  ): Promise<ProviderKey> => {
    const response = await httpClient.post(`/providers/${providerId}/keys`, data);
    return response.data;
  },

  /**
   * 更新厂商 API 密钥
   * @param providerId 提供商ID
   * @param keyId 密钥ID
   * @param data 更新请求数据
   * @returns 更新后的密钥信息
   */
  updateKey: async (
    providerId: string, 
    keyId: string, 
    data: UpdateProviderKeyRequest
  ): Promise<ProviderKey> => {
    const response = await httpClient.put(
      `/providers/${providerId}/keys/${keyId}`, 
      data
    );
    return response.data;
  },

  /**
   * 删除厂商 API 密钥
   * @param providerId 提供商ID
   * @param keyId 密钥ID
   */
  deleteKey: async (providerId: string, keyId: string): Promise<void> => {
    await httpClient.delete(`/providers/${providerId}/keys/${keyId}`);
  }
};

// 导出类型
export type {
  ProviderKey,
  CreateProviderKeyRequest,
  UpdateProviderKeyRequest
};