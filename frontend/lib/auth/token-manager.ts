import Cookies from 'js-cookie';

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'has_refresh_token';
const PERSISTENCE_KEY = 'auth_persistence';

type RememberOption = { remember?: boolean };

const getStoredPersistence = (): boolean | null => {
  const persisted = Cookies.get(PERSISTENCE_KEY);
  if (persisted === 'remember') return true;
  if (persisted === 'session') return false;
  return null;
};

const setPersistence = (remember: boolean) => {
  Cookies.set(PERSISTENCE_KEY, remember ? 'remember' : 'session', {
    expires: remember ? 7 : undefined,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    path: '/',
  });
};

const clearPersistence = () => {
  Cookies.remove(PERSISTENCE_KEY);
};

const resolveRemember = (remember?: boolean): boolean => {
  if (remember !== undefined) return remember;

  const stored = getStoredPersistence();
  if (stored !== null) return stored;

  // 检查 Cookie 中是否有 token（新方案）
  if (typeof window !== 'undefined') {
    if (Cookies.get(ACCESS_TOKEN_KEY)) {
      // 如果 Cookie 有过期时间，说明是 remember
      return true;
    }
  }

  // 兼容旧方案：检查 localStorage/sessionStorage
  if (typeof window !== 'undefined') {
    if (localStorage.getItem(ACCESS_TOKEN_KEY)) return true;
    if (sessionStorage.getItem(ACCESS_TOKEN_KEY)) return false;
  }

  return true;
};

export const tokenManager = {
  /**
   * 设置 Access Token
   * 新方案：存储到 Cookie 中（非 HttpOnly），支持 SSR 预取
   * 同时保留 localStorage/sessionStorage 作为 fallback（兼容性）
   */
  setAccessToken: (token: string, options?: RememberOption) => {
    const remember = resolveRemember(options?.remember);
    
    // 主方案：存储到 Cookie（非 HttpOnly，支持 SSR）
    Cookies.set(ACCESS_TOKEN_KEY, token, {
      expires: remember ? 7 : undefined, // remember: 7天，否则 session
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      path: '/',
      // 注意：不设置 httpOnly，让客户端 JS 可以读取
    });

    // Fallback：同时存储到 localStorage/sessionStorage（兼容旧代码）
    if (typeof window !== 'undefined') {
      const storage = remember ? localStorage : sessionStorage;
      storage.setItem(ACCESS_TOKEN_KEY, token);
      
      // 清理另一个存储
      const otherStorage = storage === localStorage ? sessionStorage : localStorage;
      otherStorage.removeItem(ACCESS_TOKEN_KEY);
    }

    if (options?.remember !== undefined) {
      setPersistence(options.remember);
    }
  },

  /**
   * 获取 Access Token
   * 优先从 Cookie 读取，fallback 到 localStorage/sessionStorage
   */
  getAccessToken: (): string | null => {
    // 优先从 Cookie 读取（支持 SSR）
    const tokenFromCookie = Cookies.get(ACCESS_TOKEN_KEY);
    if (tokenFromCookie) return tokenFromCookie;

    // Fallback：从 localStorage/sessionStorage 读取（兼容旧数据）
    if (typeof window !== 'undefined') {
      return localStorage.getItem(ACCESS_TOKEN_KEY) ?? sessionStorage.getItem(ACCESS_TOKEN_KEY);
    }

    return null;
  },

  /**
   * 清除 Access Token
   * 同时清除 Cookie 和 localStorage/sessionStorage
   */
  clearAccessToken: () => {
    // 清除 Cookie
    Cookies.remove(ACCESS_TOKEN_KEY, { path: '/' });

    // 清除 localStorage/sessionStorage
    if (typeof window !== 'undefined') {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      sessionStorage.removeItem(ACCESS_TOKEN_KEY);
    }
  },

  // Refresh Token - 仅存储标记，实际 Token 存 HttpOnly Cookie
  setRefreshToken: (_token: string | null | undefined, options?: RememberOption) => {
    const remember = resolveRemember(options?.remember);

    // 存储标记到 Cookie
    Cookies.set(REFRESH_TOKEN_KEY, 'true', {
      expires: remember ? 7 : undefined,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      path: '/',
    });

    // Fallback：存储到 localStorage/sessionStorage
    if (typeof window !== 'undefined') {
      const storage = remember ? localStorage : sessionStorage;
      storage.setItem(REFRESH_TOKEN_KEY, 'true');
      
      const otherStorage = storage === localStorage ? sessionStorage : localStorage;
      otherStorage.removeItem(REFRESH_TOKEN_KEY);
    }

    setPersistence(remember);
  },

  getRefreshToken: (): string | undefined => {
    // 优先从 Cookie 读取
    const tokenFromCookie = Cookies.get(REFRESH_TOKEN_KEY);
    if (tokenFromCookie) return 'true';

    // Fallback：从 localStorage/sessionStorage 读取
    if (typeof window !== 'undefined') {
      const val = localStorage.getItem(REFRESH_TOKEN_KEY) ?? sessionStorage.getItem(REFRESH_TOKEN_KEY);
      return val ? 'true' : undefined;
    }

    return undefined;
  },

  clearRefreshToken: () => {
    // 清除 Cookie
    Cookies.remove(REFRESH_TOKEN_KEY, { path: '/' });

    // 清除 localStorage/sessionStorage
    if (typeof window !== 'undefined') {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      sessionStorage.removeItem(REFRESH_TOKEN_KEY);
    }
    
    clearPersistence();
  },

  // 清除所有 token
  clearAll: () => {
    tokenManager.clearAccessToken();
    tokenManager.clearRefreshToken();
  },
};
