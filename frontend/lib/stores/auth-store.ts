import { create } from 'zustand';
import { authService, type UserInfo, type LoginRequest, type RegisterRequest } from '@/http/auth';
import { tokenManager } from '@/lib/auth/token-manager';
import { toast } from 'sonner';
import { ErrorHandler } from '@/lib/errors';

interface AuthState {
  user: UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAuthDialogOpen: boolean;
  
  // Actions
  setUser: (user: UserInfo | null) => void;
  setLoading: (loading: boolean) => void;
  openAuthDialog: () => void;
  closeAuthDialog: () => void;
  login: (credentials: LoginRequest, options?: { remember?: boolean }) => Promise<void>;
  register: (data: RegisterRequest) => Promise<UserInfo>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  isAuthDialogOpen: false,

  setUser: (user) => {
    set({
      user,
      isAuthenticated: !!user,
      isLoading: false
    });
  },

  setLoading: (loading) => {
    set({ isLoading: loading });
  },

  openAuthDialog: () => {
    set({ isAuthDialogOpen: true });
  },

  closeAuthDialog: () => {
    set({ isAuthDialogOpen: false });
  },

  login: async (credentials, options) => {
    try {
      set({ isLoading: true });
      const remember = options?.remember ?? true;
      
      // 调用登录 API
      const response = await authService.login(credentials);
      
      // 存储 tokens（根据记住登录选择存储介质）
      tokenManager.setAccessToken(response.access_token, { remember });
      tokenManager.setRefreshToken(response.refresh_token, { remember });
      
      // 获取用户信息
      const user = await authService.getCurrentUser();
      
      // 更新状态
      set({
        user,
        isAuthenticated: true,
        isLoading: false,
        isAuthDialogOpen: false  // 登录成功后关闭对话框
      });
      
      toast.success('登录成功');
    } catch (error) {
      set({ isLoading: false });
      // 使用标准化错误处理
      const standardError = ErrorHandler.normalize(error);
      const message = ErrorHandler.getUserMessage(standardError, (key) => key);
      toast.error(message);
      throw error;
    }
  },

  register: async (data) => {
    try {
      set({ isLoading: true });
      
      // 调用注册 API
      const user = await authService.register(data);

      if (!user.is_active) {
        // 人工审核模式下，账号创建成功但未激活，直接提示并结束，不自动登录
        toast.success('注册成功，账号待人工审核，请耐心等待');
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          isAuthDialogOpen: false,
        });
        return user;
      }

      // 注册成功且自动激活，自动登录
      await get().login({
        email: data.email,
        password: data.password,
      });
      toast.success('注册成功');
      return user;
    } catch (error) {
      set({ isLoading: false });
      // 使用标准化错误处理
      const standardError = ErrorHandler.normalize(error);
      const message = ErrorHandler.getUserMessage(standardError, (key) => key);
      toast.error(message);
      throw error;
    }
  },

  logout: async () => {
    try {
      // 调用登出 API
      await authService.logout();
    } catch (error) {
      console.error('Logout API error:', error);
    } finally {
      // 无论 API 是否成功，都清除本地状态
      tokenManager.clearAll();
      set({ 
        user: null, 
        isAuthenticated: false,
        isLoading: false 
      });
      toast.success('已退出登录');
    }
  },

  checkAuth: async () => {
    const accessToken = tokenManager.getAccessToken();
    const refreshToken = tokenManager.getRefreshToken();

    if (!accessToken && !refreshToken) {
      set({ 
        user: null, 
        isAuthenticated: false,
        isLoading: false 
      });
      return;
    }

    try {
      // 验证 token 并获取用户信息
      const user = await authService.getCurrentUser();
      set({ 
        user, 
        isAuthenticated: true,
        isLoading: false 
      });
    } catch (error) {
      // Token 无效，清除
      tokenManager.clearAll();
      set({ 
        user: null, 
        isAuthenticated: false,
        isLoading: false 
      });
    }
  },
}));
