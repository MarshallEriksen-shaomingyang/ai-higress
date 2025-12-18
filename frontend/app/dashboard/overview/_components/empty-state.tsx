"use client";

import { FileQuestion } from "lucide-react";
import { AdaptiveCard, CardDescription } from "@/components/cards/adaptive-card";
import { useI18n } from "@/lib/i18n-context";

interface EmptyStateProps {
  /**
   * 空状态标题
   */
  title?: string;
  /**
   * 空状态描述信息
   */
  message?: string;
  /**
   * 自定义图标
   */
  icon?: React.ReactNode;
  /**
   * 自定义类名
   */
  className?: string;
}

/**
 * 空状态组件
 * 
 * 用于显示数据为空时的占位符，避免显示空白图表
 * 
 * @example
 * ```tsx
 * <EmptyState
 *   title="暂无数据"
 *   message="当前时间范围内没有数据"
 * />
 * ```
 */
export function EmptyState({
  title,
  message,
  icon,
  className,
}: EmptyStateProps) {
  const { t } = useI18n();

  return (
    <AdaptiveCard className={className}>
      <div className="flex flex-col items-center gap-3 py-12">
        {icon || (
          <FileQuestion className="size-12 text-muted-foreground/50" />
        )}
        <div className="text-center space-y-1">
          <h3 className="text-base font-medium">
            {title || t("common.no_data")}
          </h3>
          {message && (
            <CardDescription className="text-sm">
              {message}
            </CardDescription>
          )}
        </div>
      </div>
    </AdaptiveCard>
  );
}
