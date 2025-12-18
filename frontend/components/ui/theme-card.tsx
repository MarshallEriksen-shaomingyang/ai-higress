"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
} from "./card";

type ThemeCardVariant = "default" | "glass" | "solid";

interface ThemeCardProps extends React.ComponentProps<typeof Card> {
  /**
   * 卡片变体，如果不指定则根据主题自动选择：
   * - light/dark: default (默认样式)
   * - christmas/ocean/spring: glass (玻璃拟态)
   */
  variant?: ThemeCardVariant;
  /**
   * 是否启用主题自动切换样式
   * @default true
   */
  themeAware?: boolean;
}

/**
 * 主题感知的卡片组件
 * 
 * 特性：
 * - 在 light/dark 主题下使用默认样式
 * - 在 christmas/ocean/spring 等特殊主题下自动应用玻璃拟态效果
 * - 支持手动指定 variant 覆盖自动行为
 * 
 * @example
 * ```tsx
 * // 自动根据主题切换样式
 * <ThemeCard>
 *   <CardHeader>
 *     <CardTitle>标题</CardTitle>
 *   </CardHeader>
 *   <CardContent>内容</CardContent>
 * </ThemeCard>
 * 
 * // 强制使用玻璃拟态效果
 * <ThemeCard variant="glass">
 *   <CardContent>始终使用玻璃效果</CardContent>
 * </ThemeCard>
 * ```
 */
function ThemeCard({
  className,
  variant,
  themeAware = true,
  children,
  ...props
}: ThemeCardProps) {
  const { theme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  // 根据主题自动选择变体
  const getAutoVariant = (): ThemeCardVariant => {
    if (!themeAware || !mounted) return "default";
    
    // 特殊主题使用玻璃拟态
    if (theme === "christmas" || theme === "ocean" || theme === "spring") {
      return "glass";
    }
    
    return "default";
  };

  const effectiveVariant = variant || getAutoVariant();

  // 变体样式映射
  const variantStyles: Record<ThemeCardVariant, string> = {
    default: "",
    glass: cn(
      // 玻璃拟态效果
      "backdrop-blur-md bg-card/60",
      "border-white/20",
      "shadow-lg shadow-black/5",
      // 内部光泽效果
      "before:absolute before:inset-0 before:rounded-xl",
      "before:bg-gradient-to-br before:from-white/10 before:to-transparent",
      "before:pointer-events-none",
      // 确保内容在伪元素之上
      "[&>*]:relative [&>*]:z-10"
    ),
    solid: "bg-card border-border shadow-md",
  };

  return (
    <Card
      className={cn(
        "relative overflow-hidden transition-all duration-300",
        variantStyles[effectiveVariant],
        className
      )}
      {...props}
    >
      {children}
    </Card>
  );
}

// 导出所有 Card 子组件，保持 API 一致性
export {
  ThemeCard,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
};
