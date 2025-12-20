import { cookies } from 'next/headers';

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
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get('access_token')?.value;
    
    // 与前端 httpClient 保持一致：优先使用 NEXT_PUBLIC_API_BASE_URL
    // 兼容旧变量名 NEXT_PUBLIC_API_URL
    const apiUrl =
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      'http://localhost:8000';
    const url = `${apiUrl}${endpoint}`;
    
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...options?.headers,
      },
      cache: 'no-store', // 默认不缓存，确保数据新鲜
    });
    
    if (!res.ok) {
      if (res.status === 401) {
        console.log(`[serverFetch] 401 Unauthorized: ${endpoint} (token may be expired)`);
      } else {
        console.error(`[serverFetch] Failed: ${endpoint}`, res.status);
      }
      return null;
    }
    
    return res.json();
  } catch (error) {
    console.error(`[serverFetch] Error: ${endpoint}`, error);
    return null;
  }
}
