"use client";

import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useI18n } from "@/lib/i18n-context";

interface ErrorStateProps {
  /**
   * 错误标题
   */
  title?: string;
  /**
   * 错误描述信息
   */
  message?: string;
  /**
   * 重试回调函数
   */
  onRetry?: () => void;
  /**
   * 是否显示重试按钮
   */
  showRetry?: boolean;
  /**
   * 自定义类名
   */
  className?: string;
}

/**
 * 错误状态组件
 * 
 * 用于显示数据加载失败时的错误提示卡片，提供重试功能
 * 
 * @example
 * ```tsx
 * <ErrorState
 *   title="加载失败"
 *   message="无法加载数据，请稍后重试"
 *   onRetry={() => mutate()}
 * />
 * ```
 */
export function ErrorState({
  title,
  message,
  onRetry,
  showRetry = true,
  className,
}: ErrorStateProps) {
  const { t } = useI18n();

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center gap-2">
          <AlertCircle className="size-5 text-destructive" />
          <CardTitle className="text-base">
            {title || t("errors.generic")}
          </CardTitle>
        </div>
        <CardDescription>
          {message || t("errors.server_error")}
        </CardDescription>
      </CardHeader>
      {showRetry && onRetry && (
        <CardContent>
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="w-full sm:w-auto"
          >
            {t("common.retry")}
          </Button>
        </CardContent>
      )}
    </Card>
  );
}
