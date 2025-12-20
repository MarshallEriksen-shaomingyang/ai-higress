"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, MessageSquare, Settings } from "lucide-react";
import type { ComponentType } from "react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { AppearanceControls } from "@/components/layout/appearance-controls";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n-context";

type NavItem = {
  href: string;
  icon: ComponentType<{ className?: string }>;
  labelKey: string;
  isActive: (pathname: string) => boolean;
};

const navItems: NavItem[] = [
  {
    href: "/dashboard",
    icon: LayoutDashboard,
    labelKey: "nav.overview",
    isActive: (pathname) => pathname.startsWith("/dashboard"),
  },
  {
    href: "/chat",
    icon: MessageSquare,
    labelKey: "nav.chat",
    isActive: (pathname) =>
      pathname.startsWith("/chat") && !pathname.startsWith("/chat/settings"),
  },
  {
    href: "/chat/settings",
    icon: Settings,
    labelKey: "chat.settings.title",
    isActive: (pathname) => pathname.startsWith("/chat/settings"),
  },
];

export function ChatNavRail({ variant = "desktop" }: { variant?: "desktop" | "mobile" }) {
  const pathname = usePathname();
  const { t } = useI18n();

  // 移动端变体 - 水平布局，只显示图标
  if (variant === "mobile") {
    return (
      <div className="flex items-center gap-1">
        {navItems.slice(0, 2).map((item) => {
          const Icon = item.icon;
          const active = item.isActive(pathname);

          return (
            <Button
              key={item.href}
              asChild
              variant="ghost"
              size="icon"
              className={cn(
                "h-9 w-9",
                active && "bg-accent text-accent-foreground"
              )}
            >
              <Link href={item.href} aria-label={t(item.labelKey)}>
                <Icon className="h-4 w-4" />
              </Link>
            </Button>
          );
        })}
      </div>
    );
  }

  // 桌面端变体 - 垂直布局
  return (
    <aside className="w-14 shrink-0 border-r bg-background/60 backdrop-blur supports-[backdrop-filter]:bg-background/40">
      <div className="flex h-full flex-col items-center py-3">
        {/* 顶部导航按钮组 - 3个按钮纵向排列 */}
        <div className="flex flex-col items-center gap-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.isActive(pathname);

            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>
                  <Button
                    asChild
                    variant="ghost"
                    size="icon"
                    className={cn(
                      "h-10 w-10 rounded-xl",
                      active && "bg-accent text-accent-foreground"
                    )}
                  >
                    <Link href={item.href} aria-label={t(item.labelKey)}>
                      <Icon className="h-5 w-5" />
                    </Link>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  {t(item.labelKey)}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>

        {/* 弹性空间 - 将底部按钮推到最下方 */}
        <div className="flex-1" />

        {/* 底部按钮组 - 3个按钮纵向排列 */}
        <div className="flex flex-col items-center gap-1.5">
          <AppearanceControls variant="rail" />
        </div>
      </div>
    </aside>
  );
}
