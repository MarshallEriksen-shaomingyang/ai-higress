"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import {
  Card,
} from "@/components/ui/card";

interface AdaptiveCardProps extends React.ComponentProps<typeof Card> {
  /**
   * 是否显示圣诞装饰
   * 装饰通过 CSS 类 .christmas-card-decor 自动控制显示/隐藏
   * @default true
   */
  showDecor?: boolean;
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
  showDecor = true,
  children,
  ...props
}: AdaptiveCardProps) {
  return (
    <div className={cn("relative", className)}>
      <Card
        className={cn(
          "relative overflow-hidden",
          "theme-adaptive-card",
          "border-white/20",
          "transition-all duration-300",
          "hover:scale-[1.02]",
        )}
        {...props}
      >
        {/* 圣诞装饰 - 右上角（通过 CSS 类自动控制） */}
        {showDecor && (
          <div className="christmas-card-decor absolute top-0 right-0 z-30 w-48 h-32 pointer-events-none">
            <img
              src="/theme/chrismas/card.png"
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
  CardAction,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
