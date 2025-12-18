"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { NeonCard } from "./neon-card";
import { ThemeCard } from "./theme-card";
import type { ComponentProps } from "react";

/**
 * 自适应主题卡片组件
 * 
 * 根据当前主题自动切换卡片样式：
 * - 圣诞主题：使用 NeonCard（冰川玻璃拟态 + 霓虹灯 + 装饰）
 * - 其他主题：使用 ThemeCard（原有主题卡片样式）
 * 
 * 这种设计便于后续扩展更多主题特定的卡片样式
 * 
 * @example
 * ```tsx
 * <AdaptiveCard>
 *   <CardContent>内容会根据主题自动适配样式</CardContent>
 * </AdaptiveCard>
 * ```
 */
export function AdaptiveCard({
  children,
  ...props
}: ComponentProps<typeof NeonCard>) {
  const { theme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  // 服务端渲染或未挂载时，使用 ThemeCard 作为默认
  if (!mounted) {
    return <ThemeCard {...props}>{children}</ThemeCard>;
  }

  // 根据主题选择对应的卡片组件
  switch (theme) {
    case "christmas":
      // 圣诞主题：使用冰川玻璃拟态卡片
      return <NeonCard {...props}>{children}</NeonCard>;
    
    // 未来可以扩展更多主题特定的卡片
    // case "ocean":
    //   return <OceanCard {...props}>{children}</OceanCard>;
    // case "spring":
    //   return <SpringCard {...props}>{children}</SpringCard>;
    
    default:
      // 其他主题：使用标准主题卡片
      return <ThemeCard {...props}>{children}</ThemeCard>;
  }
}

// 导出卡片子组件，保持 API 一致性
export {
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
} from "./card";
