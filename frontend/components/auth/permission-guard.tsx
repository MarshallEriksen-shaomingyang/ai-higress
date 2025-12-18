"use client";

import { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/stores/auth-store";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n-context";
import { ShieldAlert, Home, ArrowLeft } from "lucide-react";

interface PermissionGuardProps {
  children: ReactNode;
  requiredPermission: "superuser";
}

/**
 * PermissionGuard 组件用于检查用户权限
 * 如果用户没有所需权限，显示 403 错误页面
 * 
 * @example
 * ```tsx
 * <PermissionGuard requiredPermission="superuser">
 *   <AdminContent />
 * </PermissionGuard>
 * ```
 */
export function PermissionGuard({ children, requiredPermission }: PermissionGuardProps) {
  const router = useRouter();
  const { t } = useI18n();
  const { user, isLoading } = useAuthStore();

  // 加载中状态
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">
          {t("common.loading")}
        </div>
      </div>
    );
  }

  // 检查权限
  const hasPermission = () => {
    if (!user) return false;
    
    switch (requiredPermission) {
      case "superuser":
        return user.is_superuser === true;
      default:
        return false;
    }
  };

  // 如果没有权限，显示 403 错误页面
  if (!hasPermission()) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 animate-in fade-in duration-500">
        <div className="max-w-xl w-full text-center space-y-8">
          {/* 警告图标 */}
          <div className="flex justify-center">
            <ShieldAlert className="h-20 w-20 md:h-24 md:w-24 lg:h-32 lg:w-32 text-destructive animate-pulse" />
          </div>

          {/* 标题和描述 */}
          <div className="space-y-4">
            <h1 className="text-3xl md:text-4xl font-bold">
              {t("error.403.heading")}
            </h1>
            <p className="text-muted-foreground text-base md:text-lg max-w-md mx-auto">
              {t("error.403.description")}
            </p>
          </div>

          {/* 权限信息卡片 */}
          <Card>
            <CardContent className="p-6 space-y-3">
              <div className="text-sm font-medium">
                {t("error.403.required_permission")}
              </div>
              <code className="text-xs bg-muted p-3 rounded block font-mono">
                {requiredPermission === "superuser" ? t("error.403.permission_superuser") : requiredPermission}
              </code>
              <p className="text-xs text-muted-foreground">
                {t("error.403.contact_admin")}
              </p>
            </CardContent>
          </Card>

          {/* 操作按钮 */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button onClick={() => router.back()} size="lg" variant="outline">
              <ArrowLeft className="mr-2 h-4 w-4" />
              {t("error.403.btn_back")}
            </Button>
            <Button onClick={() => router.push("/")} size="lg">
              <Home className="mr-2 h-4 w-4" />
              {t("error.403.btn_home")}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // 有权限，渲染子组件
  return <>{children}</>;
}
