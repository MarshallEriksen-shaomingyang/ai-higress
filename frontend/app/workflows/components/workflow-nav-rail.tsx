/**
 * Workflow Nav Rail - 工作流导航栏
 * 类似 ChatNavRail 的独立导航
 */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Workflow, FileText } from "lucide-react";
import type { ComponentType } from "react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { AppearanceControls } from "@/components/layout/appearance-controls";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  icon: ComponentType<{ className?: string }>;
  label: string;
  isActive: (pathname: string) => boolean;
};

const navItems: NavItem[] = [
  {
    href: "/dashboard",
    icon: LayoutDashboard,
    label: "控制台",
    isActive: (pathname) => pathname.startsWith("/dashboard"),
  },
  {
    href: "/workflows",
    icon: Workflow,
    label: "工作流",
    isActive: (pathname) =>
      pathname === "/workflows" || (pathname.startsWith("/workflows") && !pathname.includes("/composer") && !pathname.includes("/monitor")),
  },
  {
    href: "/workflows/composer",
    icon: FileText,
    label: "编排器",
    isActive: (pathname) => pathname.startsWith("/workflows/composer"),
  },
];

export function WorkflowNavRail({ variant = "desktop" }: { variant?: "desktop" | "mobile" }) {
  const pathname = usePathname();

  // 移动端变体 - 水平布局
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
              <Link href={item.href} aria-label={item.label}>
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
    <nav className="flex flex-col h-full w-16 border-r border-border bg-card/50 backdrop-blur-sm">
      <div className="flex flex-col items-center gap-4 p-3 flex-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = item.isActive(pathname);

          return (
            <Tooltip key={item.href}>
              <TooltipTrigger asChild>
                <Button
                  asChild
                  variant={active ? "default" : "ghost"}
                  size="icon"
                  className={cn(
                    "h-10 w-10 rounded-lg transition-all",
                    active && "shadow-md"
                  )}
                >
                  <Link href={item.href}>
                    <Icon className="h-5 w-5" />
                    <span className="sr-only">{item.label}</span>
                  </Link>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={10}>
                {item.label}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>

      {/* 底部外观控制 */}
      <div className="p-3 border-t border-border">
        <AppearanceControls />
      </div>
    </nav>
  );
}
