"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/lib/i18n-context";
import { cn } from "@/lib/utils";

interface ProviderStatusCardProps {
  providerId: string;
  operationStatus: "active" | "inactive" | "maintenance";
  healthStatus: "healthy" | "degraded" | "unhealthy";
  auditStatus: "approved" | "pending" | "rejected";
  lastCheck: string;
}

/**
 * Provider 状态卡片组件
 * 
 * 显示单个 Provider 的运行状态、健康状态、审核状态和最后检查时间
 * 
 * @param providerId - Provider ID
 * @param operationStatus - 运行状态 (active/inactive/maintenance)
 * @param healthStatus - 健康状态 (healthy/degraded/unhealthy)
 * @param auditStatus - 审核状态 (approved/pending/rejected)
 * @param lastCheck - 最后检查时间 (ISO 8601 格式)
 */
export function ProviderStatusCard({
  providerId,
  operationStatus,
  healthStatus,
  auditStatus,
  lastCheck,
}: ProviderStatusCardProps) {
  const { t } = useI18n();

  // 运行状态颜色映射
  const operationStatusColors = {
    active: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    inactive: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
    maintenance: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  };

  // 健康状态颜色映射
  const healthStatusColors = {
    healthy: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    degraded: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
    unhealthy: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  };

  // 审核状态颜色映射
  const auditStatusColors = {
    approved: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    pending: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    rejected: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  };

  // 格式化最后检查时间
  const formatLastCheck = (isoString: string) => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 1) {
        return t("dashboardV2.provider.lastCheck.justNow");
      } else if (diffMins < 60) {
        return t("dashboardV2.provider.lastCheck.minutesAgo", { count: diffMins });
      } else if (diffHours < 24) {
        return t("dashboardV2.provider.lastCheck.hoursAgo", { count: diffHours });
      } else {
        return t("dashboardV2.provider.lastCheck.daysAgo", { count: diffDays });
      }
    } catch {
      return isoString;
    }
  };

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader>
        <CardTitle className="text-base font-medium">{providerId}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* 运行状态 */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            {t("dashboardV2.provider.operationStatus")}
          </span>
          <Badge
            variant="outline"
            className={cn(
              "border-transparent",
              operationStatusColors[operationStatus]
            )}
          >
            {t(`dashboardV2.provider.operationStatus.${operationStatus}`)}
          </Badge>
        </div>

        {/* 健康状态 */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            {t("dashboardV2.provider.healthStatus")}
          </span>
          <Badge
            variant="outline"
            className={cn(
              "border-transparent",
              healthStatusColors[healthStatus]
            )}
          >
            {t(`dashboardV2.provider.healthStatus.${healthStatus}`)}
          </Badge>
        </div>

        {/* 审核状态 */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            {t("dashboardV2.provider.auditStatus")}
          </span>
          <Badge
            variant="outline"
            className={cn(
              "border-transparent",
              auditStatusColors[auditStatus]
            )}
          >
            {t(`dashboardV2.provider.auditStatus.${auditStatus}`)}
          </Badge>
        </div>

        {/* 最后检查时间 */}
        <div className="pt-2 border-t">
          <div className="text-xs text-muted-foreground">
            {t("dashboardV2.provider.lastCheck.label")}:{" "}
            <span className="font-medium">{formatLastCheck(lastCheck)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
