import { httpClient } from './client';
import type { 
  CreditAccount, 
  CreditTransaction, 
  TopupRequest,
  TransactionQueryParams 
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
  }
};

// 导出类型
export type {
  CreditAccount,
  CreditTransaction,
  TopupRequest,
  TransactionQueryParams
};