"use client";

import React, { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Plus, Coins } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { formatRelativeTime } from "@/lib/date-utils";
import type { CreditAccount } from "@/lib/api-types";

interface CreditBalanceCardProps {
  balance: CreditAccount | undefined;
  loading: boolean;
  onRefresh: () => void;
  onTopup?: () => void;
  showTopupButton?: boolean;
}

export function CreditBalanceCard({
  balance,
  loading,
  onRefresh,
  onTopup,
  showTopupButton = false
}: CreditBalanceCardProps) {
  const { t } = useI18n();

  // 格式化积分数字（添加千位分隔符）
  const formattedBalance = useMemo(() => {
    if (!balance) return '0';
    return balance.balance.toLocaleString();
  }, [balance]);

  // 格式化更新时间
  const lastUpdated = useMemo(() => {
    if (!balance) return '';
    try {
      return formatRelativeTime(balance.updated_at);
    } catch {
      return balance.updated_at;
    }
  }, [balance]);

  // 状态徽章
  const statusBadge = useMemo(() => {
    if (!balance) return null;
    
    if (balance.status === 'active') {
      return (
        <Badge variant="secondary" className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100">
          <span className="w-2 h-2 rounded-full bg-green-500 mr-1.5"></span>
          {t("credits.status_active")}
        </Badge>
      );
    } else {
      return (
        <Badge variant="destructive">
          <span className="w-2 h-2 rounded-full bg-red-500 mr-1.5"></span>
          {t("credits.status_suspended")}
        </Badge>
      );
    }
  }, [balance, t]);

  // 每日限额显示
  const dailyLimitText = useMemo(() => {
    if (!balance) return t("credits.unlimited");
    return balance.daily_limit 
      ? balance.daily_limit.toLocaleString() 
      : t("credits.unlimited");
  }, [balance, t]);

  if (loading && !balance) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Coins className="w-5 h-5" />
            {t("credits.balance")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Coins className="w-5 h-5" />
            {t("credits.balance")}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={onRefresh}
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
            {showTopupButton && onTopup && (
              <Button
                variant="default"
                size="sm"
                onClick={onTopup}
              >
                <Plus className="w-4 h-4 mr-1" />
                {t("credits.topup")}
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {/* 积分余额 - 大号显示 */}
          <div className="text-center py-6">
            <div className="text-5xl font-bold text-foreground mb-2">
              {formattedBalance}
            </div>
            <div className="text-sm text-muted-foreground">
              {t("credits.balance")}
            </div>
          </div>

          {/* 状态和限额信息 */}
          <div className="grid grid-cols-2 gap-4 pt-4 border-t">
            <div className="space-y-1">
              <div className="text-sm text-muted-foreground">
                {t("credits.status")}
              </div>
              <div>{statusBadge}</div>
            </div>
            <div className="space-y-1">
              <div className="text-sm text-muted-foreground">
                {t("credits.daily_limit")}
              </div>
              <div className="text-sm font-medium">
                {dailyLimitText}
              </div>
            </div>
          </div>

          {/* 最后更新时间 */}
          <div className="text-xs text-muted-foreground text-center pt-2 border-t">
            {t("credits.last_updated")}: {lastUpdated}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}