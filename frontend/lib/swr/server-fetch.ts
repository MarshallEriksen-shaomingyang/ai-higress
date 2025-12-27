import { cookies } from 'next/headers';
import { REQUEST_TITLE_HEADER_NAME, REQUEST_TITLE_HEADER_VALUE } from '@/config/headers';

async function refreshServerAccessToken(
  apiUrl: string,
  refreshToken: string
): Promise<string | null> {
  try {
    const refreshUrl = new URL('/auth/refresh', apiUrl);
    const refreshRes = await fetch(refreshUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [REQUEST_TITLE_HEADER_NAME]: REQUEST_TITLE_HEADER_VALUE,
        // 关键：SSR 请求不会自动携带浏览器 Cookie，需手动透传 refresh_token
        Cookie: `refresh_token=${refreshToken}`,
        'Cache-Control': 'no-store',
      },
      cache: 'no-store',
    });

    if (!refreshRes.ok) return null;
    const contentType = refreshRes.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) return null;

    const payload = (await refreshRes.json()) as { access_token?: string };
    return payload.access_token ?? null;
  } catch {
    return null;
  }
}

/**
 * 服务端数据获取工具
 * 用于在 Next.js 服务端组件中预取数据，避免客户端初始加载闪烁
 * 
 * Token 存储方案：
 * - access_token 存储在 Cookie 中（非 HttpOnly）
 * - 服务端可以通过 cookies() 读取
 * - 客户端可以通过 js-cookie 读取
 */
export async function serverFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T | null> {
  let hasRetriedAfterRefresh = false;
  try {
    // Next.js 16（React 19）中 cookies() 返回 Promise，需要 await 获取 CookieStore
    const cookieStore = await cookies();
    const token = cookieStore.get('access_token')?.value;
    const refreshToken = cookieStore.get('refresh_token')?.value;
    
    // 与前端 httpClient 保持一致：优先使用 NEXT_PUBLIC_API_BASE_URL
    // 兼容旧变量名 NEXT_PUBLIC_API_URL
    const apiUrl =
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      'http://localhost:8000';

    const normalizedHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
      [REQUEST_TITLE_HEADER_NAME]: REQUEST_TITLE_HEADER_VALUE,
    };
    if (options?.headers instanceof Headers) {
      options.headers.forEach((value, key) => {
        normalizedHeaders[key] = value;
      });
    } else if (options?.headers && typeof options.headers === 'object') {
      Object.entries(options.headers).forEach(([key, value]) => {
        if (typeof value === 'undefined') return;
        normalizedHeaders[key] = Array.isArray(value) ? value.join(', ') : String(value);
      });
    }
    if (token) {
      normalizedHeaders['Authorization'] = `Bearer ${token}`;
    }
    // 与 fetch 的 no-store 行为保持一致，避免使用缓存
    normalizedHeaders['Cache-Control'] = 'no-store';
    normalizedHeaders[REQUEST_TITLE_HEADER_NAME] = REQUEST_TITLE_HEADER_VALUE;

    const url = new URL(endpoint, apiUrl);
    const method = options?.method ?? 'GET';

    const { headers: _ignoredHeaders, body: rawBody, method: _ignoredMethod, signal: _ignoredSignal, ...rest } =
      options ?? {};
    const hasBody = typeof rawBody !== 'undefined';
    const isBodyAllowed = method !== 'GET' && method !== 'HEAD';
    const body = hasBody && isBodyAllowed ? rawBody : undefined;

    const doFetch = (headers: Record<string, string>) =>
      fetch(url, {
        ...rest,
        method,
        headers,
        cache: 'no-store',
        signal: options?.signal ?? undefined,
        body,
      });

    let res = await doFetch(normalizedHeaders);

    if (res.status === 401) {
      // SSR 场景没有 axios 拦截器；如果能拿到 refresh_token，则尝试刷新并重试一次。
      if (!hasRetriedAfterRefresh && refreshToken) {
        hasRetriedAfterRefresh = true;
        const newToken = await refreshServerAccessToken(apiUrl, refreshToken);
        if (newToken) {
          const retryHeaders = { ...normalizedHeaders, Authorization: `Bearer ${newToken}` };
          res = await doFetch(retryHeaders);
        }
      }

      if (res.status === 401) {
        console.log(`[serverFetch] 401 Unauthorized: ${endpoint} (token may be expired)`);
        return null;
      }
    }
    if (!res.ok) {
      console.error(`[serverFetch] Failed: ${endpoint}`, res.status);
      return null;
    }

    if (res.status === 204) return null;

    const contentType = res.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      console.error(`[serverFetch] Unexpected content-type: ${endpoint}`, contentType);
      return null;
    }

    try {
      return (await res.json()) as T;
    } catch (parseError) {
      console.error(`[serverFetch] Failed to parse JSON: ${endpoint}`, parseError);
      return null;
    }
  } catch (error) {
    console.error(`[serverFetch] Error: ${endpoint}`, error);
    return null;
  }
}
