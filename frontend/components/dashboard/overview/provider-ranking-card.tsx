"use client";

import { useMemo } from "react";
import { AlertCircle, TrendingUp } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useI18n } from "@/lib/i18n-context";
import { useCreditProviderConsumption } from "@/lib/swr/use-credits";
import type { ProviderConsumption } from "@/lib/api-types";

interface ProviderRankingCardProps {
  timeRange?: string;
  onProviderClick?: (providerId: string) => void;
  onRetry?: () => void;
}

/**
 * Provider 消耗排行榜卡片
 *
 * 职责：
 * - 显示按消耗排序的 Provider 列表
 * - 支持时间范围切换
 * - 显示消耗、请求量、成功率等指标
 * - 实现快捷链接导航
 *
 * 验证需求：2.1, 2.2, 2.3, 2.4
 * 验证属性：Property 4, 6, 7
 */
export function ProviderRankingCard({
  timeRange = "7d",
  onProviderClick,
  onRetry,
}: ProviderRankingCardProps) {
  const { t } = useI18n();
  const router = useRouter();
  const { providers, loading, error, refresh } = useCreditProviderConsumption(timeRange);

  // 排序 Provider 列表（按消耗降序）
  const sortedProviders = useMemo(() => {
    return [...providers].sort((a, b) => b.total_consumption - a.total_consumption);
  }, [providers]);

  // 计算排名和百分比
  const rankedProviders = useMemo(() => {
    return sortedProviders.map((provider, index) => ({
      ...provider,
      rank: index + 1,
    }));
  }, [sortedProviders]);

  // 格式化数字
  const formatNumber = (value: number): string => {
    return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  };

  // 格式化百分比
  const formatPercentage = (value: number): string => {
    return (value * 100).toFixed(1);
  };

  // 处理 Provider 行点击
  const handleProviderClick = (provider: ProviderConsumption) => {
    onProviderClick?.(provider.provider_id);
    // 导航到 Provider 管理页面
    router.push(`/dashboard/providers/${provider.provider_id}`);
  };

  // 处理重试
  const handleRetry = () => {
    refresh();
    onRetry?.();
  };

  // 加载状态
  if (loading && providers.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("provider_ranking.title")}</CardTitle>
          <CardDescription>{t("overview.from_last_month")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-4 w-8" data-testid="skeleton" />
                <Skeleton className="h-4 w-24" data-testid="skeleton" />
                <Skeleton className="h-4 w-20" data-testid="skeleton" />
                <Skeleton className="h-4 w-20" data-testid="skeleton" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // 错误状态
  if (error && providers.length === 0) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            {t("provider_ranking.title")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            {t("provider_ranking.error")}
          </p>
          <Button size="sm" variant="outline" onClick={handleRetry}>
            {t("consumption.retry")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  // 无数据状态
  if (providers.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("provider_ranking.title")}</CardTitle>
          <CardDescription>{t("overview.from_last_month")}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-8">
            {t("provider_ranking.no_data")}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-none shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">{t("provider_ranking.title")}</CardTitle>
          <Badge variant="outline" className="h-5 text-xs font-normal">
            {providers.length}
          </Badge>
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-3">
          {rankedProviders.slice(0, 5).map((provider) => (
            <div
              key={provider.provider_id}
              className="flex items-center gap-4 py-2 cursor-pointer hover:bg-muted/30 -mx-2 px-2 rounded transition-colors"
              onClick={() => handleProviderClick(provider)}
              data-testid={`provider-row-${provider.provider_id}`}
            >
              {/* 排名 */}
              <div className="w-6 text-center">
                <span className="text-sm font-light text-muted-foreground">
                  {provider.rank}
                </span>
              </div>

              {/* Provider 名称 */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  {provider.provider_name}
                </p>
              </div>

              {/* 消耗 */}
              <div className="text-right">
                <p className="text-sm font-light">
                  {formatNumber(provider.total_consumption)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatPercentage(provider.percentage_of_total)}%
                </p>
              </div>

              {/* 成功率 */}
              <div className="w-16 text-right">
                <span
                  className={`text-xs font-medium ${
                    provider.success_rate >= 0.95
                      ? "text-foreground"
                      : provider.success_rate >= 0.9
                        ? "text-muted-foreground"
                        : "text-destructive"
                  }`}
                >
                  {formatPercentage(provider.success_rate)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
