"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";

interface AdaptiveCardProps extends Omit<React.ComponentProps<typeof Card>, "className" | "title"> {
  /**
   * 传给内部 Card 的 className（用于控制 Card 本身样式）
   */
  className?: string;
  /**
   * 外层包裹 div 的 className（用于布局/分组 hover 等）
   */
  wrapperClassName?: string;
  /**
   * 是否显示圣诞装饰
   * 装饰通过 CSS 类 .christmas-card-decor 自动控制显示/隐藏
   * @default true
   */
  showDecor?: boolean;
  /**
   * 卡片标题（可选）
   */
  title?: React.ReactNode;
  /**
   * 卡片描述（可选）
   */
  description?: React.ReactNode;
  /**
   * 标题右侧的操作区域（可选）
   */
  headerAction?: React.ReactNode;
}

/**
 * 自适应主题卡片组件
 * 
 * 通过 CSS 变量和类名自动适配所有主题：
 * - 玻璃拟态效果：通过 .theme-adaptive-card 类自动调整
 * - 霓虹灯效果：通过 CSS 变量控制颜色
 * - 圣诞装饰：通过 .christmas-card-decor 类控制显示
 * 
 * 添加新主题只需在 globals.css 中配置，无需修改组件代码
 * 
 * @example
 * ```tsx
 * <AdaptiveCard>
 *   <CardHeader>
 *     <CardTitle>标题</CardTitle>
 *   </CardHeader>
 *   <CardContent>内容会根据主题自动适配样式</CardContent>
 * </AdaptiveCard>
 * ```
 */
export function AdaptiveCard({
  className,
  wrapperClassName,
  showDecor = true,
  title,
  description,
  headerAction,
  children,
  ...props
}: AdaptiveCardProps) {
  const hasHeader = title || description || headerAction;

  return (
    <div className={cn("relative", wrapperClassName)}>
      <Card
        className={cn(
          "relative overflow-hidden",
          "theme-adaptive-card",
          "border-white/20",
          "transition-all duration-300",
          "hover:scale-[1.02]",
          className,
        )}
        {...props}
      >
        {/* 圣诞装饰 - 右上角（通过 CSS 类自动控制） */}
        {showDecor && (
          <div className="christmas-card-decor absolute top-0 right-0 z-30 w-48 h-32 pointer-events-none">
            <img
              src="/theme/christmas/card.png"
              alt="Christmas decoration"
              className="w-full h-full object-contain object-right-top"
              style={{
                filter: "drop-shadow(0 2px 8px rgba(0, 0, 0, 0.2))",
                opacity: 0.95,
              }}
              loading="lazy"
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
            />
          </div>
        )}

        {/* 卡片内容 */}
        <div className="relative z-20">
          {/* 可选的标题区域 */}
          {hasHeader && (
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  {title && (
                    <CardTitle className="text-base font-medium">
                      {title}
                    </CardTitle>
                  )}
                  {description && (
                    <CardDescription>{description}</CardDescription>
                  )}
                </div>
                {headerAction && (
                  <div className="flex-shrink-0 ml-4">
                    {headerAction}
                  </div>
                )}
              </div>
            </CardHeader>
          )}

          {/* 内容区域 */}
          {children}
        </div>
      </Card>
    </div>
  );
}

// 导出卡片子组件，保持 API 一致性
export {
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardAction,
  CardContent,
} from "@/components/ui/card";
