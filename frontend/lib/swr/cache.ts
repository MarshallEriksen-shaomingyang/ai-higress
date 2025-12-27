"use client";

import { Cache } from 'swr';
import { useCallback } from 'react';
import { useSWRConfig, mutate } from 'swr';

// 缓存管理工具类
export class SWRCacheManager {
  private cache: Cache<any>;

  constructor(cache: Cache<any>) {
    this.cache = cache;
  }

  // 获取所有缓存键
  getKeys(): string[] {
    return Array.from(this.cache.keys());
  }

  // 获取缓存值
  getValue(key: string): any {
    return this.cache.get(key);
  }

  // 设置缓存值
  setValue(key: string, value: any): void {
    this.cache.set(key, value);
  }

  // 删除缓存
  deleteKey(key: string): boolean {
    const cacheWithHas = this.cache as Cache<any> & { has?: (key: string) => boolean };
    const existed = typeof cacheWithHas.has === 'function'
      ? cacheWithHas.has(key)
      : this.cache.get(key) !== undefined;
    this.cache.delete(key);
    return !!existed;
  }

  // 清空所有缓存
  clear(): void {
    const cacheAny = this.cache as Cache<any> & { clear?: () => void };
    if (typeof cacheAny.clear === 'function') {
      cacheAny.clear();
      return;
    }
    this.getKeys().forEach(key => {
      this.cache.delete(key);
    });
  }

  // 根据模式匹配缓存键
  getKeysByPattern(pattern: RegExp): string[] {
    return this.getKeys().filter(key => pattern.test(key));
  }

  // 批量删除匹配模式的缓存
  deleteByPattern(pattern: RegExp): number {
    const keysToDelete = this.getKeysByPattern(pattern);
    let deletedCount = 0;
    keysToDelete.forEach(key => {
      if (this.deleteKey(key)) {
        deletedCount++;
      }
    });
    return deletedCount;
  }

  // 获取缓存统计信息
  getStats(): { size: number; keys: string[] } {
    const keys = this.getKeys();
    return {
      size: keys.length,
      keys,
    };
  }
}

// Hook for SWR 缓存管理
export const useSWRCache = () => {
  const { cache } = useSWRConfig();
  const cacheManager = new SWRCacheManager(cache);

  // 刷新特定缓存
  const refreshCache = useCallback((key: string) => {
    return mutate(key);
  }, []);

  // 批量刷新缓存
  const refreshMultipleCaches = useCallback((keys: string[]) => {
    return Promise.all(keys.map(key => mutate(key)));
  }, []);

  // 根据模式刷新缓存
  const refreshCacheByPattern = useCallback((pattern: RegExp) => {
    const keys = cacheManager.getKeysByPattern(pattern);
    return refreshMultipleCaches(keys);
  }, [cacheManager, refreshMultipleCaches]);

  return {
    cacheManager,
    refreshCache,
    refreshMultipleCaches,
    refreshCacheByPattern,
  };
};

// 全局缓存预加载 Hook
export const useCachePreloader = () => {
  const { cache } = useSWRConfig();

  const preloadData = useCallback((key: string, fetcher: () => Promise<any>) => {
    if (!cache.get(key)) {
      mutate(key, fetcher, false);
    }
  }, [cache]);

  return { preloadData };
};

// 缓存复用工具 - 用于在切换会话时复用缓存
export const useCacheReuse = () => {
  const { cache } = useSWRConfig();

  /**
   * 检查缓存是否存在且有效
   */
  const isCacheValid = useCallback((key: string): boolean => {
    const cachedData = cache.get(key);
    return cachedData !== undefined && cachedData !== null;
  }, [cache]);

  /**
   * 预热缓存 - 在用户可能访问之前预加载数据
   */
  const warmupCache = useCallback((key: string, fetcher: () => Promise<any>) => {
    if (!isCacheValid(key)) {
      // 使用 mutate 预加载数据，但不触发重新验证
      mutate(key, fetcher, { revalidate: false });
    }
  }, [cache, isCacheValid]);

  /**
   * 批量预热缓存
   */
  const warmupMultipleCaches = useCallback((items: Array<{ key: string; fetcher: () => Promise<any> }>) => {
    items.forEach(({ key, fetcher }) => {
      warmupCache(key, fetcher);
    });
  }, [warmupCache]);

  return {
    isCacheValid,
    warmupCache,
    warmupMultipleCaches,
  };
};

// 缓存策略配置
export const cacheStrategies = {
  // 默认策略
  default: {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    revalidateIfStale: false,
    refreshInterval: 0,
    refreshWhenHidden: false,
    refreshWhenOffline: false,
    dedupingInterval: 5000,
  },
  // 频繁更新数据策略
  frequent: {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    revalidateIfStale: false,
    refreshInterval: 0,
    refreshWhenHidden: false,
    refreshWhenOffline: false,
    dedupingInterval: 5000,
  },
  // 静态数据策略
  static: {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    revalidateIfStale: false,
    refreshInterval: 0,
    refreshWhenHidden: false,
    refreshWhenOffline: false,
    dedupingInterval: 60000,
  },
  // 实时数据策略
  realtime: {
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    revalidateIfStale: true,
    refreshInterval: 5000, // 5秒
    refreshWhenHidden: false,
    refreshWhenOffline: false,
    dedupingInterval: 500,
  },
};

// Hook 用于应用缓存策略
export const useCacheStrategy = (strategy: keyof typeof cacheStrategies) => {
  return cacheStrategies[strategy] || cacheStrategies.default;
};
