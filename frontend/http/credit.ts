import { httpClient } from './client';
import type {
  CreditAccount,
  CreditTransaction,
  TopupRequest,
  TransactionQueryParams,
  CreditAutoTopupBatchRequest,
  CreditAutoTopupBatchResponse,
  CreditAutoTopupConfig,
  CreditAutoTopupConfigInput,
} from '@/lib/api-types';

/**
 * 积分与额度管理 API 服务
 */
export const creditService = {
  /**
   * 获取当前用户的积分账户信息
   * @returns 积分账户信息
   */
  getMyCredits: async (): Promise<CreditAccount> => {
    const response = await httpClient.get('/v1/credits/me');
    return response.data;
  },

  /**
   * 获取当前用户的积分流水记录
   * @param params 查询参数（分页、时间范围等）
   * @returns 积分流水记录数组
   */
  getMyTransactions: async (
    params: TransactionQueryParams = {}
  ): Promise<CreditTransaction[]> => {
    const response = await httpClient.get('/v1/credits/me/transactions', {
      params: {
        limit: params.limit || 50,
        offset: params.offset || 0,
        ...(params.start_date && { start_date: params.start_date }),
        ...(params.end_date && { end_date: params.end_date }),
      }
    });
    return response.data;
  },

  /**
   * 管理员为指定用户充值积分
   * @param userId 用户ID
   * @param data 充值请求数据
   * @returns 更新后的积分账户信息
   */
  adminTopup: async (
    userId: string,
    data: TopupRequest
  ): Promise<CreditAccount> => {
    const response = await httpClient.post(
      `/v1/credits/admin/users/${userId}/topup`,
      data
    );
    return response.data;
  },

  /**
   * 查询单个用户的自动充值配置
   */
  getUserAutoTopupConfig: async (
    userId: string
  ): Promise<CreditAutoTopupConfig | null> => {
    const response = await httpClient.get<CreditAutoTopupConfig | null>(
      `/v1/credits/admin/users/${userId}/auto-topup`
    );
    return response.data;
  },

  /**
   * 为单个用户创建或更新自动充值配置
   */
  upsertUserAutoTopupConfig: async (
    userId: string,
    config: CreditAutoTopupConfigInput
  ): Promise<CreditAutoTopupConfig> => {
    const response = await httpClient.put<CreditAutoTopupConfig>(
      `/v1/credits/admin/users/${userId}/auto-topup`,
      config
    );
    return response.data;
  },

  /**
   * 禁用单个用户的自动充值配置
   */
  disableUserAutoTopupConfig: async (userId: string): Promise<void> => {
    await httpClient.delete(`/v1/credits/admin/users/${userId}/auto-topup`);
  },

  /**
   * 批量为多个用户配置自动充值规则
   */
  batchUpsertAutoTopup: async (
    payload: CreditAutoTopupBatchRequest
  ): Promise<CreditAutoTopupBatchResponse> => {
    const response = await httpClient.post<CreditAutoTopupBatchResponse>(
      `/v1/credits/admin/auto-topup/batch`,
      payload
    );
    return response.data;
  },
};

// 导出类型
export type {
  CreditAccount,
  CreditTransaction,
  TopupRequest,
  TransactionQueryParams,
  CreditAutoTopupBatchRequest,
  CreditAutoTopupBatchResponse,
  CreditAutoTopupConfig,
  CreditAutoTopupConfigInput,
};
