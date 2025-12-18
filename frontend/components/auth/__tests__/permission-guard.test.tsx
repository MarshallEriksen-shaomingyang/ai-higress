import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PermissionGuard } from '../permission-guard';
import { useAuthStore } from '@/lib/stores/auth-store';
import { useRouter } from 'next/navigation';

// Mock dependencies
vi.mock('@/lib/stores/auth-store');
vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
}));
vi.mock('@/lib/i18n-context', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('PermissionGuard', () => {
  const mockRouter = {
    push: vi.fn(),
    back: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (useRouter as any).mockReturnValue(mockRouter);
  });

  it('应该在加载时显示加载状态', () => {
    (useAuthStore as any).mockReturnValue({
      user: null,
      isLoading: true,
    });

    render(
      <PermissionGuard requiredPermission="superuser">
        <div>Protected Content</div>
      </PermissionGuard>
    );

    expect(screen.getByText('common.loading')).toBeInTheDocument();
  });

  it('应该在用户是管理员时显示子组件', () => {
    (useAuthStore as any).mockReturnValue({
      user: {
        id: '1',
        email: 'admin@example.com',
        is_superuser: true,
      },
      isLoading: false,
    });

    render(
      <PermissionGuard requiredPermission="superuser">
        <div>Protected Content</div>
      </PermissionGuard>
    );

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('应该在用户不是管理员时显示 403 错误页面', () => {
    (useAuthStore as any).mockReturnValue({
      user: {
        id: '1',
        email: 'user@example.com',
        is_superuser: false,
      },
      isLoading: false,
    });

    render(
      <PermissionGuard requiredPermission="superuser">
        <div>Protected Content</div>
      </PermissionGuard>
    );

    expect(screen.getByText('error.403.heading')).toBeInTheDocument();
    expect(screen.getByText('error.403.description')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  it('应该在用户未登录时显示 403 错误页面', () => {
    (useAuthStore as any).mockReturnValue({
      user: null,
      isLoading: false,
    });

    render(
      <PermissionGuard requiredPermission="superuser">
        <div>Protected Content</div>
      </PermissionGuard>
    );

    expect(screen.getByText('error.403.heading')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });
});
