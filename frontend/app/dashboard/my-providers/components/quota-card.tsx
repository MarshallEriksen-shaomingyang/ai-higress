"use client";

import React from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";

interface QuotaCardProps {
  current: number;
  limit: number;
  isLoading?: boolean;
}

export function QuotaCard({ current, limit, isLoading }: QuotaCardProps) {
  const { t } = useI18n();
  
  const percentage = limit > 0 ? (current / limit) * 100 : 0;
  const remaining = Math.max(0, limit - current);
  const isNearLimit = percentage >= 80;

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("my_providers.quota_title")}</CardTitle>
          <CardDescription>
            {t("providers.loading")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="h-4 bg-muted animate-pulse rounded" />
            <div className="h-2 bg-muted animate-pulse rounded" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("my_providers.quota_title")}</CardTitle>
        <CardDescription>
          {t("my_providers.quota_used")} {current} 个，{t("my_providers.quota_remaining")} {remaining} 个
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">{t("my_providers.quota_used")}</span>
            <span className="font-medium">
              {current} / {limit}
            </span>
          </div>
          <Progress value={percentage} className="h-2" />
          {isNearLimit && (
            <Alert variant="default" className="border-yellow-500 bg-yellow-50 dark:bg-yellow-950">
              <AlertCircle className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
              <AlertDescription className="text-yellow-800 dark:text-yellow-200">
                {t("my_providers.quota_warning")}
              </AlertDescription>
            </Alert>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
