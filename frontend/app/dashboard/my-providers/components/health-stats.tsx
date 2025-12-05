"use client";

import React, { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Provider } from "@/http/provider";
import { useI18n } from "@/lib/i18n-context";
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

interface HealthStatsProps {
  providers: Provider[];
  isLoading?: boolean;
}

export function HealthStats({ providers, isLoading }: HealthStatsProps) {
  const { t } = useI18n();

  const stats = useMemo(() => {
    const healthy = providers.filter((p) => p.status === "healthy").length;
    const degraded = providers.filter((p) => p.status === "degraded").length;
    const down = providers.filter((p) => p.status === "down").length;

    return {
      healthy,
      degraded,
      down,
      total: providers.length,
    };
  }, [providers]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("my_providers.health_title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="text-center space-y-2">
                <div className="h-8 bg-muted animate-pulse rounded" />
                <div className="h-4 bg-muted animate-pulse rounded" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("my_providers.health_title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4">
          {/* 运行中 */}
          <div className="text-center space-y-2">
            <div className="flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 mr-2" />
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {stats.healthy}
              </div>
            </div>
            <div className="text-sm text-muted-foreground">
              {t("my_providers.health_healthy")}
            </div>
          </div>

          {/* 降级 */}
          <div className="text-center space-y-2">
            <div className="flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-yellow-600 dark:text-yellow-400 mr-2" />
              <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                {stats.degraded}
              </div>
            </div>
            <div className="text-sm text-muted-foreground">
              {t("my_providers.health_degraded")}
            </div>
          </div>

          {/* 故障 */}
          <div className="text-center space-y-2">
            <div className="flex items-center justify-center">
              <XCircle className="w-5 h-5 text-red-600 dark:text-red-400 mr-2" />
              <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                {stats.down}
              </div>
            </div>
            <div className="text-sm text-muted-foreground">
              {t("my_providers.health_down")}
            </div>
          </div>
        </div>

        {/* 总计 */}
        <div className="mt-4 pt-4 border-t text-center">
          <span className="text-sm text-muted-foreground">
            {t("my_providers.health_total")}:{" "}
          </span>
          <span className="text-sm font-medium">{stats.total}</span>
        </div>
      </CardContent>
    </Card>
  );
}
