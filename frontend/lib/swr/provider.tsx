"use client";

import React, { createContext, useContext } from 'react';
import { SWRConfig, SWRConfiguration } from 'swr';
import { swrFetcher } from './fetcher';

// SWR 配置接口
export interface SWRProviderConfig extends SWRConfiguration {
  fetcher?: (url: string) => Promise<any>;
}

// 默认 SWR 配置
const defaultSWRConfig: SWRProviderConfig = {
  fetcher: swrFetcher.get,
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  revalidateIfStale: false,
  dedupingInterval: 5000,
  focusThrottleInterval: 5000,
  errorRetryCount: 3,
  errorRetryInterval: 5000,
  loadingTimeout: 10000,
  refreshInterval: 0, // 默认不自动刷新
  refreshWhenHidden: false,
  refreshWhenOffline: false,
  // 缓存策略配置
  keepPreviousData: true,
  // 错误处理
  onError: (error, key) => {
    console.error(`SWR Error for key ${key}:`, error);
  },
  // 成功回调
  onSuccess: (data, key) => {
    console.debug(`SWR Success for key ${key}:`, data);
  },
  // 错误重试条件：401 错误不重试
  onErrorRetry: (error, key, _config, revalidate, { retryCount }) => {
    // 401 认证错误不重试，避免无限循环
    if (error?.status === 401 || error?.response?.status === 401) {
      console.warn(`[SWR] 401 error for ${key}, skipping retry`);
      return;
    }
    
    // 404 错误不重试
    if (error?.status === 404 || error?.response?.status === 404) {
      return;
    }
    
    // 超过最大重试次数
    if (retryCount >= 3) {
      return;
    }
    
    // 其他错误按指数退避重试
    setTimeout(() => revalidate({ retryCount }), Math.min(1000 * Math.pow(2, retryCount), 30000));
  },
};

// SWR Provider 上下文
export const SWRProviderContext = createContext<SWRConfiguration>(defaultSWRConfig);

// SWR Provider 组件
interface SWRProviderProps {
  children: React.ReactNode;
  config?: SWRProviderConfig;
  fallback?: Record<string, any>; // 支持服务端预取数据
}

export const SWRProvider: React.FC<SWRProviderProps> = ({ 
  children, 
  config = {},
  fallback = {}
}) => {
  // 合并默认配置和自定义配置
  const mergedConfig = {
    ...defaultSWRConfig,
    ...config,
    // 确保始终有 fetcher
    fetcher: config.fetcher || defaultSWRConfig.fetcher,
    // 合并 fallback 数据
    fallback: {
      ...config.fallback,
      ...fallback,
    },
  };

  return (
    <SWRProviderContext.Provider value={mergedConfig}>
      <SWRConfig value={mergedConfig}>
        {children}
      </SWRConfig>
    </SWRProviderContext.Provider>
  );
};

// Hook 来获取 SWR 配置
export const useSWRConfig = () => {
  const context = useContext(SWRProviderContext);
  if (!context) {
    throw new Error('useSWRConfig must be used within a SWRProvider');
  }
  return context;
};

// 针对不同请求类型的特定 fetcher
export const createSWRHook = (method: keyof typeof swrFetcher) => {
  return (url: string, params?: any) => {
    if (method === 'getWithParams' && params) {
      return swrFetcher[method](url, params);
    }
    return swrFetcher[method as 'get'](url);
  };
};

// 预定义的 fetcher hooks
export const useGet = createSWRHook('get');
export const useGetWithParams = createSWRHook('getWithParams');
export const usePost = createSWRHook('post');
export const usePut = createSWRHook('put');
export const useDelete = createSWRHook('delete');
export const usePatch = createSWRHook('patch');
