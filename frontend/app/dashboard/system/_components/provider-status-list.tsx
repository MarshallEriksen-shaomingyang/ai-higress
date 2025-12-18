"use client";

import { ProviderStatusCard } from "./provider-status-card";
import { Card, CardContent } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n-context";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ProviderStatusItem } from "@/lib/api-types";

interface ProviderStatusListProps {
  data: ProviderStatusItem[];
  isLoading: boolean;
  error?: Error;
  onRetry?: () => void;
}

/**
 * Provider 状态列表组件
 * 
 * 使用网格布局展示所有 Provider 的状态卡片
 * 响应式布局：桌面 3 列、平板 2 列、移动 1 列
 * 
 * @param data - Provider 状态数据数组
 * @param isLoading - 加载状态
 * @param error - 错误信息
 * @param onRetry - 重试回调函数
 */
export function ProviderStatusList({
  data,
  isLoading,
  error,
  onRetry,
}: ProviderStatusListProps) {
  const { t } = useI18n();

  // 加载态
  if (isLoading) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold">
          {t("dashboardV2.provider.title")}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-6">
                <div className="space-y-3">
                  <div className="h-5 bg-muted rounded w-3/4" />
                  <div className="h-4 bg-muted rounded w-1/2" />
                  <div className="h-4 bg-muted rounded w-2/3" />
                  <div className="h-4 bg-muted rounded w-1/2" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // 错误态
  if (error) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold">
          {t("dashboardV2.provider.title")}
        </h3>
        <Card className="border-destructive">
          <CardContent className="p-6">
            <div className="flex flex-col items-center justify-center space-y-4 text-center">
              <AlertCircle className="h-12 w-12 text-destructive" />
              <div className="space-y-2">
                <h4 className="text-lg font-semibold text-destructive">
                  {t("error.loadFailed")}
                </h4>
                <p className="text-sm text-muted-foreground">
                  {error.message || t("error.unknownError")}
                </p>
              </div>
              {onRetry && (
                <Button onClick={onRetry} variant="outline">
                  {t("common.retry")}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // 空数据态
  if (!data || data.length === 0) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold">
          {t("dashboardV2.provider.title")}
        </h3>
        <Card>
          <CardContent className="p-6">
            <div className="flex flex-col items-center justify-center space-y-4 text-center py-8">
              <div className="rounded-full bg-muted p-3">
                <AlertCircle className="h-8 w-8 text-muted-foreground" />
              </div>
              <div className="space-y-2">
                <h4 className="text-lg font-semibold">
                  {t("dashboardV2.provider.noData")}
                </h4>
                <p className="text-sm text-muted-foreground">
                  {t("dashboardV2.provider.noDataDescription")}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // 正常数据展示
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">
          {t("dashboardV2.provider.title")}
        </h3>
        <span className="text-sm text-muted-foreground">
          {t("dashboardV2.provider.totalCount", { count: data.length })}
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {data.map((provider) => (
          <ProviderStatusCard
            key={provider.provider_id}
            providerId={provider.provider_id}
            operationStatus={provider.operation_status}
            healthStatus={provider.status}
            auditStatus={provider.audit_status}
            lastCheck={provider.last_check}
          />
        ))}
      </div>
    </div>
  );
}
