"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import {
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
} from "./card";

type NeonColor = "red" | "green" | "blue" | "purple" | "orange" | "cyan" | "auto";

interface NeonCardProps extends React.ComponentProps<"div"> {
  /**
   * 霓虹灯颜色
   * - "auto": 根据主题自动选择颜色
   * - 其他: 指定固定颜色
   * @default "auto"
   */
  neonColor?: NeonColor;
  /**
   * 是否启用霓虹灯效果
   * @default true
   */
  enableNeon?: boolean;
  /**
   * 霓虹灯强度 (1-3)
   * @default 2
   */
  neonIntensity?: 1 | 2 | 3;
  /**
   * 是否显示主题装饰（右上角）
   * - "auto": 根据主题自动决定（圣诞主题显示，其他主题不显示）
   * - true: 强制显示
   * - false: 强制隐藏
   * @default "auto"
   */
  showThemeDecor?: boolean | "auto";
  /**
   * 是否启用冰川纹理效果
   * - "auto": 根据主题自动决定（圣诞主题启用，其他主题不启用）
   * - true: 强制启用
   * - false: 强制禁用
   * @default "auto"
   */
  enableFrostTexture?: boolean | "auto";
}

/**
 * 霓虹灯玻璃拟态卡片组件
 * 
 * 特性：
 * - 玻璃拟态背景（半透明 + 背景模糊）
 * - 上下边框霓虹灯效果
 * - 根据主题自动切换霓虹灯颜色
 * - 支持自定义霓虹灯颜色和强度
 * 
 * @example
 * ```tsx
 * // 自动主题色霓虹灯
 * <NeonCard>
 *   <CardContent>内容</CardContent>
 * </NeonCard>
 * 
 * // 指定红色霓虹灯
 * <NeonCard neonColor="red">
 *   <CardContent>红色霓虹灯</CardContent>
 * </NeonCard>
 * 
 * // 高强度霓虹灯
 * <NeonCard neonIntensity={3}>
 *   <CardContent>强烈发光</CardContent>
 * </NeonCard>
 * ```
 */
function NeonCard({
  className,
  neonColor = "auto",
  enableNeon = true,
  neonIntensity = 2,
  showThemeDecor = "auto",
  enableFrostTexture = "auto",
  children,
  ...props
}: NeonCardProps) {
  const { theme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  // 根据主题自动选择霓虹灯颜色
  const getAutoNeonColor = (): NeonColor => {
    if (!mounted) return "blue";
    
    switch (theme) {
      case "christmas":
        return "red";
      case "dark":
        return "purple";
      default:
        return "blue";
    }
  };

  const effectiveColor = neonColor === "auto" ? getAutoNeonColor() : neonColor;

  // 判断是否显示主题装饰（圣诞主题自动显示）
  const shouldShowDecor = React.useMemo(() => {
    if (showThemeDecor === true) return true;
    if (showThemeDecor === false) return false;
    // auto 模式：只在圣诞主题显示
    return mounted && theme === "christmas";
  }, [showThemeDecor, mounted, theme]);

  // 判断是否启用冰川纹理（圣诞主题自动启用）
  const shouldEnableFrost = React.useMemo(() => {
    if (enableFrostTexture === true) return true;
    if (enableFrostTexture === false) return false;
    // auto 模式：只在圣诞主题启用
    return mounted && theme === "christmas";
  }, [enableFrostTexture, mounted, theme]);

  // 霓虹灯颜色配置 - 只用于边框
  const neonColors: Record<Exclude<NeonColor, "auto">, {
    border: string;
    shadow: string;
    glowColor: string; // 用于 boxShadow 的 RGB 值
  }> = {
    red: {
      border: "from-transparent via-red-400 to-transparent",
      shadow: "shadow-red-500/70",
      glowColor: "255, 60, 60",
    },
    green: {
      border: "from-transparent via-green-400 to-transparent",
      shadow: "shadow-green-500/70",
      glowColor: "50, 255, 100",
    },
    blue: {
      border: "from-transparent via-blue-400 to-transparent",
      shadow: "shadow-blue-500/70",
      glowColor: "60, 150, 255",
    },
    purple: {
      border: "from-transparent via-purple-400 to-transparent",
      shadow: "shadow-purple-500/70",
      glowColor: "180, 100, 255",
    },
    orange: {
      border: "from-transparent via-orange-400 to-transparent",
      shadow: "shadow-orange-500/70",
      glowColor: "255, 150, 50",
    },
    cyan: {
      border: "from-transparent via-cyan-400 to-transparent",
      shadow: "shadow-cyan-500/70",
      glowColor: "50, 230, 255",
    },
  };

  const colorConfig = neonColors[effectiveColor as Exclude<NeonColor, "auto">];

  // 霓虹灯强度配置
  const intensityConfig = {
    1: {
      borderHeight: "h-[2px]",
      shadowSize: "shadow-sm",
      blur: "blur-[2px]",
    },
    2: {
      borderHeight: "h-[3px]",
      shadowSize: "shadow-md",
      blur: "blur-[4px]",
    },
    3: {
      borderHeight: "h-[4px]",
      shadowSize: "shadow-lg",
      blur: "blur-[6px]",
    },
  };

  const intensity = intensityConfig[neonIntensity];

  return (
    <div
      className={cn(
        "relative rounded-2xl overflow-hidden",
        "border border-white/20",
        enableNeon && intensity.shadowSize,
        enableNeon && colorConfig.shadow,
        "transition-all duration-300",
        "hover:scale-[1.02]",
        className
      )}
      style={{
        backdropFilter: "blur(16px) saturate(150%)",
        WebkitBackdropFilter: "blur(16px) saturate(150%)",
        background: "rgba(255, 255, 255, 0.12)",
        boxShadow: enableNeon ? `0 8px 32px 0 ${colorConfig.shadow}` : undefined,
      } as React.CSSProperties}
      {...props}
    >
      {/* 顶部霓虹流光 - 中间亮两边淡（激光效果） */}
      {enableNeon && (
        <div className="absolute top-0 left-0 right-0 z-10 flex justify-center">
          <div
            className={cn(
              "w-[70%] h-[2px]",
              "bg-gradient-to-r",
              colorConfig.border,
            )}
            style={{
              filter: `blur(${neonIntensity}px)`,
              boxShadow: `0 0 ${neonIntensity * 8}px rgba(${colorConfig.glowColor}, 0.9), 0 0 ${neonIntensity * 15}px rgba(${colorConfig.glowColor}, 0.6)`,
              opacity: 0.85,
            }}
          />
        </div>
      )}

      {/* 底部霓虹流光 - 中间亮两边淡（激光效果） */}
      {enableNeon && (
        <div className="absolute bottom-0 left-0 right-0 z-10 flex justify-center">
          <div
            className={cn(
              "w-[70%] h-[2px]",
              "bg-gradient-to-r",
              colorConfig.border,
            )}
            style={{
              filter: `blur(${neonIntensity}px)`,
              boxShadow: `0 0 ${neonIntensity * 8}px rgba(${colorConfig.glowColor}, 0.9), 0 0 ${neonIntensity * 15}px rgba(${colorConfig.glowColor}, 0.6)`,
              opacity: 0.85,
            }}
          />
        </div>
      )}

      {/* 冰冻噪点纹理层 - 边缘冰霜效果（Frost Texture） */}
      <div
        className="absolute inset-0 pointer-events-none opacity-40"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")`,
          backgroundSize: "200px 200px",
          mixBlendMode: "overlay",
          WebkitMaskImage: "radial-gradient(circle at center, transparent 30%, black 100%)",
          maskImage: "radial-gradient(circle at center, transparent 30%, black 100%)",
        }}
      />

      {/* 冰川纹理效果组 - 仅在圣诞主题或手动启用时显示 */}
      {shouldEnableFrost && (
        <>
          {/* 冰霜纹理层 - 雪花质感 */}
          <div
            className="absolute inset-0 pointer-events-none opacity-30"
            style={{
              backgroundImage: `
                radial-gradient(circle at 20% 30%, rgba(255, 255, 255, 0.8) 0%, transparent 2%),
                radial-gradient(circle at 60% 70%, rgba(255, 255, 255, 0.6) 0%, transparent 1.5%),
                radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.7) 0%, transparent 1.8%),
                radial-gradient(circle at 30% 80%, rgba(255, 255, 255, 0.5) 0%, transparent 1.2%),
                radial-gradient(circle at 90% 60%, rgba(255, 255, 255, 0.6) 0%, transparent 1.5%),
                radial-gradient(circle at 15% 50%, rgba(255, 255, 255, 0.4) 0%, transparent 1%),
                radial-gradient(circle at 70% 40%, rgba(255, 255, 255, 0.5) 0%, transparent 1.3%),
                radial-gradient(circle at 40% 15%, rgba(255, 255, 255, 0.7) 0%, transparent 1.6%)
              `,
              backgroundSize: "100% 100%",
              mixBlendMode: "overlay",
            }}
          />

          {/* 边框冰晶增强层 - 四周边缘冰霜效果 */}
          <div
            className="absolute inset-0 pointer-events-none opacity-60"
            style={{
              background: `
                linear-gradient(to right, rgba(255, 255, 255, 0.4) 0%, transparent 8%),
                linear-gradient(to left, rgba(255, 255, 255, 0.4) 0%, transparent 8%),
                linear-gradient(to bottom, rgba(255, 255, 255, 0.3) 0%, transparent 8%),
                linear-gradient(to top, rgba(255, 255, 255, 0.3) 0%, transparent 8%)
              `,
              mixBlendMode: "overlay",
            }}
          />

          {/* 边框冰裂纹理 - 细微裂纹效果 */}
          <div
            className="absolute inset-0 pointer-events-none opacity-30"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg width='100' height='100' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0,50 Q25,45 50,50 T100,50' stroke='white' stroke-width='0.5' fill='none' opacity='0.3'/%3E%3Cpath d='M50,0 Q45,25 50,50 T50,100' stroke='white' stroke-width='0.5' fill='none' opacity='0.3'/%3E%3Cpath d='M20,20 L30,35 M70,70 L80,85 M15,80 L25,90' stroke='white' stroke-width='0.3' opacity='0.2'/%3E%3C/svg%3E")`,
              backgroundSize: "150px 150px",
              backgroundPosition: "0 0, 75px 75px",
              mixBlendMode: "overlay",
            }}
          />
        </>
      )}

      {/* 冰块质感遮罩层 - 磨砂玻璃效果 */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: "linear-gradient(135deg, rgba(255, 255, 255, 0.25) 0%, rgba(255, 255, 255, 0.08) 50%, rgba(255, 255, 255, 0.15) 100%)",
          mixBlendMode: "overlay",
        }}
      />
      
      {/* 顶部高光 - 增强冰块质感 */}
      <div
        className="absolute top-0 left-0 right-0 h-1/3 pointer-events-none"
        style={{
          background: "linear-gradient(180deg, rgba(255, 255, 255, 0.2) 0%, transparent 100%)",
        }}
      />

      {/* 左上角高光 - 光线反射效果（增强） */}
      <div
        className="absolute top-0 left-0 w-48 h-48 pointer-events-none"
        style={{
          background: "radial-gradient(circle at top left, rgba(255, 255, 255, 0.7) 0%, rgba(255, 255, 255, 0.4) 25%, transparent 55%)",
          filter: "blur(10px)",
        }}
      />

      {/* 右上角冰晶高光 */}
      <div
        className="absolute top-0 right-0 w-40 h-40 pointer-events-none opacity-50"
        style={{
          background: "radial-gradient(circle at top right, rgba(255, 255, 255, 0.6) 0%, rgba(255, 255, 255, 0.3) 30%, transparent 60%)",
          filter: "blur(8px)",
        }}
      />

      {/* 四个角落的冰晶纹理 - 仅在圣诞主题或手动启用时显示 */}
      {shouldEnableFrost && (
        <>
          {/* 右下角冰霜纹理 - 增强角落质感 */}
          <div
            className="absolute bottom-0 right-0 w-40 h-40 pointer-events-none opacity-50"
            style={{
              backgroundImage: `
                radial-gradient(circle at 85% 85%, rgba(255, 255, 255, 1) 0%, transparent 4%),
                radial-gradient(circle at 92% 75%, rgba(255, 255, 255, 0.8) 0%, transparent 2.5%),
                radial-gradient(circle at 75% 92%, rgba(255, 255, 255, 0.9) 0%, transparent 3%),
                radial-gradient(circle at 88% 88%, rgba(255, 255, 255, 0.7) 0%, transparent 2%)
              `,
              filter: "blur(0.8px)",
            }}
          />

          {/* 左下角冰霜纹理（增强） */}
          <div
            className="absolute bottom-0 left-0 w-40 h-40 pointer-events-none opacity-50"
            style={{
              backgroundImage: `
                radial-gradient(circle at 15% 85%, rgba(255, 255, 255, 1) 0%, transparent 4%),
                radial-gradient(circle at 8% 75%, rgba(255, 255, 255, 0.8) 0%, transparent 2.5%),
                radial-gradient(circle at 25% 92%, rgba(255, 255, 255, 0.9) 0%, transparent 3%),
                radial-gradient(circle at 12% 88%, rgba(255, 255, 255, 0.7) 0%, transparent 2%)
              `,
              filter: "blur(0.8px)",
            }}
          />

          {/* 左上角冰晶纹理 */}
          <div
            className="absolute top-0 left-0 w-40 h-40 pointer-events-none opacity-45"
            style={{
              backgroundImage: `
                radial-gradient(circle at 15% 15%, rgba(255, 255, 255, 1) 0%, transparent 4%),
                radial-gradient(circle at 8% 25%, rgba(255, 255, 255, 0.8) 0%, transparent 2.5%),
                radial-gradient(circle at 25% 8%, rgba(255, 255, 255, 0.9) 0%, transparent 3%)
              `,
              filter: "blur(0.8px)",
            }}
          />

          {/* 右上角冰晶纹理 */}
          <div
            className="absolute top-0 right-0 w-40 h-40 pointer-events-none opacity-45"
            style={{
              backgroundImage: `
                radial-gradient(circle at 85% 15%, rgba(255, 255, 255, 1) 0%, transparent 4%),
                radial-gradient(circle at 92% 25%, rgba(255, 255, 255, 0.8) 0%, transparent 2.5%),
                radial-gradient(circle at 75% 8%, rgba(255, 255, 255, 0.9) 0%, transparent 3%)
              `,
              filter: "blur(0.8px)",
            }}
          />
        </>
      )}

      {/* 主题装饰 - 右上角（根据主题自动显示） */}
      {shouldShowDecor && (
        <div className="absolute top-0 right-0 z-30 w-48 h-32 pointer-events-none">
          <img
            src="/theme/chrismas/card.png"
            alt="Theme decoration"
            className="w-full h-full object-contain object-right-top"
            style={{
              filter: "drop-shadow(0 2px 8px rgba(0, 0, 0, 0.2))",
              opacity: 0.95,
            }}
            loading="lazy"
            onError={(e) => {
              console.error("Failed to load theme decoration");
              e.currentTarget.style.display = "none";
            }}
          />
        </div>
      )}

      {/* 主题装饰 - 左侧冰霜（根据主题自动显示） */}
      {shouldShowDecor && (
        <div className="absolute top-0 left-0 bottom-0 z-30 w-48 pointer-events-none overflow-visible">
          <img
            src="/theme/chrismas/frost-left.png"
            alt="Frost decoration"
            className="absolute top-0 left-0 h-full w-auto object-contain object-left-top"
            style={{
              filter: "drop-shadow(0 2px 8px rgba(0, 0, 0, 0.2))",
              opacity: 0.9,
            }}
            loading="lazy"
            onError={(e) => {
              console.error("Failed to load frost decoration");
              e.currentTarget.style.display = "none";
            }}
          />
        </div>
      )}

      {/* 卡片内容 */}
      <div className="relative z-20 p-6">
        {children}
      </div>
    </div>
  );
}

// 导出所有 Card 子组件，保持 API 一致性
export {
  NeonCard,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
};
