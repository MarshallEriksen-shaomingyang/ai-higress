/**
 * SWR Hooks 返回类型定义
 * 此文件定义所有 SWR hooks 的标准返回类型
 */

import type { KeyedMutator } from 'swr';

/**
 * 基础 SWR Hook 返回类型
 */
export interface BaseSWRReturn<T> {
  data: T | undefined;
  error: Error | undefined;
  isLoading: boolean;
  mutate: KeyedMutator<T>;
}

/**
 * 带数据的 SWR Hook 返回类型（data 不为 undefined）
 */
export interface SWRReturnWithData<T> {
  data: T;
  error: Error | undefined;
  isLoading: boolean;
  mutate: KeyedMutator<T>;
}

/**
 * 列表类型的 SWR Hook 返回类型
 */
export interface ListSWRReturn<T> {
  items: T[];
  total?: number;
  isLoading: boolean;
  error: Error | undefined;
  mutate: KeyedMutator<T[]>;
}

/**
 * 分页列表的 SWR Hook 返回类型
 */
export interface PaginatedSWRReturn<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  isLoading: boolean;
  error: Error | undefined;
  mutate: KeyedMutator<{ items: T[]; total: number }>;
}

/**
 * 带操作方法的 SWR Hook 返回类型
 */
export interface SWRReturnWithActions<T, CreateData = any, UpdateData = any> {
  data: T | undefined;
  isLoading: boolean;
  error: Error | undefined;
  mutate: KeyedMutator<T>;
  create?: (data: CreateData) => Promise<T>;
  update?: (id: string, data: UpdateData) => Promise<T>;
  remove?: (id: string) => Promise<void>;
}

/**
 * 列表带操作方法的 SWR Hook 返回类型
 */
export interface ListSWRReturnWithActions<T, CreateData = any, UpdateData = any> {
  items: T[];
  isLoading: boolean;
  error: Error | undefined;
  mutate: KeyedMutator<T[]>;
  create: (data: CreateData) => Promise<T>;
  update: (id: string, data: UpdateData) => Promise<T>;
  remove: (id: string) => Promise<void>;
  refresh: () => Promise<void>;
}

/**
 * 提交状态类型
 */
export interface SubmitState {
  submitting: boolean;
  error: Error | null;
}

/**
 * 带提交状态的操作返回类型
 */
export interface ActionWithSubmitState<T = void> {
  execute: (...args: any[]) => Promise<T>;
  submitting: boolean;
  error: Error | null;
}

/**
 * 查询参数类型
 */
export interface QueryParams {
  page?: number;
  pageSize?: number;
  search?: string;
  filters?: Record<string, any>;
  sort?: {
    field: string;
    direction: 'asc' | 'desc';
  };
}

/**
 * 时间范围查询参数
 */
export interface TimeRangeParams {
  start_date?: string;
  end_date?: string;
  time_range?: 'today' | '7d' | '30d' | 'all';
}

/**
 * 缓存策略类型
 */
export type CacheStrategy = 'static' | 'frequent' | 'realtime';

/**
 * SWR 配置选项
 */
export interface SWRConfigOptions {
  revalidateOnFocus?: boolean;
  revalidateOnReconnect?: boolean;
  refreshInterval?: number;
  dedupingInterval?: number;
  errorRetryCount?: number;
  errorRetryInterval?: number;
}

/**
 * 获取缓存策略配置
 */
export function getCacheStrategyConfig(strategy: CacheStrategy): SWRConfigOptions {
  switch (strategy) {
    case 'static':
      return {
        revalidateOnFocus: false,
        revalidateOnReconnect: false,
        refreshInterval: 0,
        dedupingInterval: 3600000, // 1 小时
      };
    case 'frequent':
      return {
        revalidateOnFocus: false,
        revalidateOnReconnect: false,
        refreshInterval: 0,
        dedupingInterval: 5000, // 5 秒
      };
    case 'realtime':
      return {
        revalidateOnFocus: false,
        revalidateOnReconnect: true,
        refreshInterval: 5000, // 5 秒
        dedupingInterval: 1000, // 1 秒
      };
    default:
      return {};
  }
}
