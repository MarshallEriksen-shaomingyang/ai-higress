"use client";

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { tokenManager } from '@/lib/auth/token-manager';
import { ErrorHandler } from '@/lib/errors';
import { HTTP_DEFAULT_TIMEOUT_MS } from '@/config/timeouts';
import { REQUEST_TITLE_HEADER_NAME, REQUEST_TITLE_HEADER_VALUE } from '@/config/headers';

// 认证状态变更回调
let authErrorCallback: (() => void) | null = null;
let authErrorTriggered = false; // 防止重复触发认证错误回调

// 设置认证错误回调
export const setAuthErrorCallback = (callback: () => void) => {
  authErrorCallback = callback;
  authErrorTriggered = false; // 重置标志
};

// 清除认证错误回调
export const clearAuthErrorCallback = () => {
  authErrorCallback = null;
  authErrorTriggered = false;
};

// 触发认证错误（带防重复机制）
const triggerAuthError = () => {
  if (!authErrorTriggered && authErrorCallback) {
    authErrorTriggered = true;
    authErrorCallback();
    // 5秒后重置标志，允许再次触发（防止永久锁定）
    setTimeout(() => {
      authErrorTriggered = false;
    }, 5000);
  }
};

// 环境变量
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const BASE_URL = API_BASE_URL;

// 刷新 token 的状态管理
let isRefreshing = false;
let refreshTokenPromise: Promise<string> | null = null;
let failedQueue: Array<{
  resolve: (value?: any) => void;
  reject: (reason?: any) => void;
}> = [];

// 处理队列中的请求
const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  
  failedQueue = [];
};

// 刷新 token 的函数（导出供非 axios 请求复用，例如 SSE / SSR 补偿）
export const refreshAccessToken = async (): Promise<string> => {
  try {
    // 使用 axios 直接调用后端刷新接口（避免实例拦截器循环）
    const response = await axios.post<{ access_token: string; refresh_token: string | null }>(
      `${BASE_URL}/auth/refresh`,
      {},
      {
        headers: {
          'Content-Type': 'application/json',
          [REQUEST_TITLE_HEADER_NAME]: REQUEST_TITLE_HEADER_VALUE,
        },
        withCredentials: true, // 确保跨域发送 cookie
        validateStatus: () => true, // 由下方统一处理状态码
      }
    );

    if (response.status !== 200 || !response.data?.access_token) {
      const errorMessage =
        (response.data as any)?.error ||
        `Token refresh failed with status ${response.status}`;
      throw new Error(errorMessage);
    }

    const { access_token, refresh_token: new_refresh_token } = response.data;
    
    // 更新 tokens
    tokenManager.setAccessToken(access_token);
    // 更新 refresh token 标记 (即使 new_refresh_token 为 null，也会设置标记为 true)
    tokenManager.setRefreshToken(new_refresh_token);
    
    return access_token;
  } catch (error) {
    // 刷新失败，清除所有 token
    tokenManager.clearAll();
    throw error;
  }
};

// 创建axios实例
const createHttpClient = (): AxiosInstance => {
  const instance = axios.create({
    baseURL: BASE_URL,
    timeout: HTTP_DEFAULT_TIMEOUT_MS,
    // 需要携带跨域 Cookie 才能拿到后端设置的 HttpOnly refresh_token
    withCredentials: true,
    headers: {
      'Content-Type': 'application/json',
      [REQUEST_TITLE_HEADER_NAME]: REQUEST_TITLE_HEADER_VALUE,
    },
  });

  // 请求拦截器
  instance.interceptors.request.use(
    async (config: InternalAxiosRequestConfig) => {
      if (typeof (config.headers as any)?.set === 'function') {
        (config.headers as any).set(REQUEST_TITLE_HEADER_NAME, REQUEST_TITLE_HEADER_VALUE);
      } else {
        (config.headers as any)[REQUEST_TITLE_HEADER_NAME] = REQUEST_TITLE_HEADER_VALUE;
      }

      // 从 tokenManager 获取 token
      let token = tokenManager.getAccessToken();
      const apiKey = typeof window !== 'undefined' 
        ? localStorage.getItem('api_key') 
        : null;
      const refreshToken = tokenManager.getRefreshToken();

      // 如果没有 access_token 但有 refresh_token，且不是刷新请求本身，先刷新
      const isRefreshRequest = config.url?.includes('/auth/refresh');
      const shouldRefreshToken = !token && !apiKey && refreshToken && !isRefreshRequest;
      if (shouldRefreshToken) {
        console.log('[Auth Debug] No access token but has refresh token, refreshing before request...');
        
        // 如果正在刷新，等待刷新完成
        if (isRefreshing && refreshTokenPromise) {
          try {
            token = await refreshTokenPromise;
          } catch (error) {
            console.log('[Auth Debug] Refresh failed in request interceptor:', error);
            // 刷新失败，继续发送请求（会收到 401）
          }
        } else if (!isRefreshing) {
          // 开始刷新
          isRefreshing = true;
          refreshTokenPromise = refreshAccessToken()
            .then(newToken => {
              console.log('[Auth Debug] Token refresh successful in request interceptor');
              processQueue(null, newToken);
              return newToken;
            })
            .catch(refreshError => {
              console.log('[Auth Debug] Token refresh failed in request interceptor:', refreshError);
              processQueue(refreshError, null);
              tokenManager.clearAll();
              if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
                triggerAuthError();
              }
              throw refreshError;
            })
            .finally(() => {
              isRefreshing = false;
              refreshTokenPromise = null;
            });
          
          try {
            token = await refreshTokenPromise;
          } catch (error) {
            console.log('[Auth Debug] Refresh failed in request interceptor:', error);
            // 刷新失败，继续发送请求（会收到 401）
          }
        }
      }

      // 添加认证信息
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      } else if (apiKey) {
        config.headers['X-API-Key'] = apiKey;
      }

      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // 响应拦截器
  instance.interceptors.response.use(
    (response: AxiosResponse) => {
      return response;
    },
    async (error: AxiosError) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

      // 401 错误的 token 刷新逻辑
      if (error.response?.status === 401) {
        console.log('[Auth Debug] 401 error detected:', {
          url: originalRequest.url,
          isRefreshRequest: originalRequest.url?.includes('/auth/refresh'),
          hasRetried: originalRequest._retry,
          isRefreshing,
          hasRefreshToken: !!tokenManager.getRefreshToken()
        });
        const isRefreshRequest = originalRequest.url?.includes('/auth/refresh');
        
        // 如果是刷新token请求失败，触发认证错误回调
        if (isRefreshRequest) {
          tokenManager.clearAll();
          if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
            triggerAuthError();
          }
          // 标准化错误后抛出，让业务层决定如何展示
          const standardError = ErrorHandler.normalize(error);
          return Promise.reject(standardError);
        }
        
        // 如果不是刷新token请求，且不是已重试的请求，尝试刷新token
        if (!originalRequest._retry) {
          // 如果正在刷新，等待刷新完成后使用新 token 重试
          if (isRefreshing && refreshTokenPromise) {
            return refreshTokenPromise.then(token => {
              if (originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${token}`;
              }
              return instance(originalRequest);
            }).catch(err => {
              return Promise.reject(err);
            });
          }

          originalRequest._retry = true;
          isRefreshing = true;

          // 创建共享的刷新 Promise
          console.log('[Auth Debug] Starting token refresh...');
          refreshTokenPromise = refreshAccessToken()
            .then(newToken => {
              console.log('[Auth Debug] Token refresh successful');
              processQueue(null, newToken);
              return newToken;
            })
            .catch(refreshError => {
              console.log('[Auth Debug] Token refresh failed:', refreshError);
              processQueue(refreshError, null);
              
              // 刷新失败，清除所有token并触发认证错误回调
              tokenManager.clearAll();
              if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
                triggerAuthError();
              }
              throw refreshError;
            })
            .finally(() => {
              isRefreshing = false;
              refreshTokenPromise = null;
            });

          // 等待刷新完成后重试原请求
          return refreshTokenPromise.then(newToken => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
            }
            return instance(originalRequest);
          });
        }
      }

      // 将错误标准化后抛出，让业务层使用 useErrorDisplay 决定如何展示
      const standardError = ErrorHandler.normalize(error);
      
      // 开发环境打印详细错误
      if (process.env.NODE_ENV === 'development') {
        console.error('[HTTP Error]', standardError);
      }

      return Promise.reject(standardError);
    }
  );

  return instance;
};

// 创建并导出axios实例
export const httpClient = createHttpClient();

// 导出类型
export type { AxiosRequestConfig, AxiosResponse, AxiosError };

// 导出默认实例
export default httpClient;
