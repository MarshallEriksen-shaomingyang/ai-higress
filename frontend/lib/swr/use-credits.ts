"use client";

import { useCallback, useMemo } from 'react';
import { useApiGet, useApiPost } from './hooks';
import { creditService } from '@/http/credit';
import { useAuthStore } from '@/lib/stores/auth-store';
import type { 
  CreditAccount, 
  CreditTransaction, 
  TopupRequest,
  TransactionQueryParams 
} from '@/lib/api-types';

/**
 * 获取当前用户的积分余额
 */
export const useCreditBalance = () => {
  const {
    data,
    error,
    loading,
    refresh
  } = useApiGet<CreditAccount>(
    '/v1/credits/me',
    { strategy: 'frequent' }
  );

  return {
    balance: data,
    loading,
    error,
    refresh
  };
};

/**
 * 获取当前用户的积分流水记录
 * @param params 查询参数（分页、时间范围等）
 */
export const useCreditTransactions = (params: TransactionQueryParams = {}) => {
  // 构建查询字符串
  const queryString = useMemo(() => {
    const searchParams = new URLSearchParams();
    
    if (params.limit) searchParams.append('limit', params.limit.toString());
    if (params.offset) searchParams.append('offset', params.offset.toString());
    if (params.start_date) searchParams.append('start_date', params.start_date);
    if (params.end_date) searchParams.append('end_date', params.end_date);
    
    return searchParams.toString();
  }, [params.limit, params.offset, params.start_date, params.end_date]);

  const {
    data,
    error,
    loading,
    refresh
  } = useApiGet<CreditTransaction[]>(
    `/v1/credits/me/transactions?${queryString}`,
    { strategy: 'frequent' }
  );

  return {
    transactions: data || [],
    loading,
    error,
    refresh
  };
};

/**
 * 管理员充值功能
 */
export const useAdminTopup = () => {
  const user = useAuthStore(state => state.user);
  const isSuperUser = user?.is_superuser === true;

  const topupMutation = useApiPost<CreditAccount, TopupRequest>('');

  const topup = useCallback(async (userId: string, data: TopupRequest) => {
    if (!isSuperUser) {
      throw new Error('需要超级管理员权限');
    }
    
    const url = `/v1/credits/admin/users/${userId}/topup`;
    return await creditService.adminTopup(userId, data);
  }, [isSuperUser]);

  return {
    topup,
    submitting: topupMutation.submitting,
    isSuperUser
  };
};