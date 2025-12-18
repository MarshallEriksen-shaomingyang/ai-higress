"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n-context";
import { useAuthStore } from "@/lib/stores/auth-store";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import {
  LayoutDashboard,
  Cpu,
  Key,
  Coins,
  Network,
  Activity,
  Settings,
  Users,
  UserCircle,
  Shield,
  Package,
  Lock,
  Send,
  Bell,
  Megaphone,
  Globe,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type NavItem = {
  titleKey: string;
  href: string;
  icon: LucideIcon;
  requiresSuperuser?: boolean;
};

const navItems: NavItem[] = [
  {
    titleKey: "nav.overview",
    href: "/dashboard/overview",
    icon: LayoutDashboard,
  },
  {
    titleKey: "nav.my_providers",
    href: "/dashboard/my-providers",
    icon: Lock,
  },
  {
    titleKey: "nav.notifications",
    href: "/dashboard/notifications",
    icon: Bell,
  },
  {
    titleKey: "nav.logical_models",
    href: "/dashboard/logical-models",
    icon: Cpu,
  },
  {
    titleKey: "nav.api_keys",
    href: "/dashboard/api-keys",
    icon: Key,
  },
  {
    titleKey: "nav.credits",
    href: "/dashboard/credits",
    icon: Coins,
  },
  {
    titleKey: "nav.my_submissions",
    href: "/dashboard/my-submissions",
    icon: Send,
  },
  {
    titleKey: "nav.metrics",
    href: "/dashboard/metrics",
    icon: Activity,
  },
];

const adminItems: NavItem[] = [
  {
    titleKey: "nav.routing",
    href: "/dashboard/routing",
    icon: Network,
  },
  {
    titleKey: "nav.provider_presets",
    href: "/dashboard/provider-presets",
    icon: Package,
  },
  {
    titleKey: "nav.system_dashboard",
    href: "/dashboard/system",
    icon: Activity,
    requiresSuperuser: true,
  },
  {
    titleKey: "nav.system",
    href: "/system/admin",
    icon: Settings,
  },
  {
    titleKey: "nav.upstream_proxy",
    href: "/system/admin/upstream-proxy",
    icon: Globe,
  },
  {
    titleKey: "nav.users",
    href: "/system/users",
    icon: Users,
  },
  {
    titleKey: "nav.roles",
    href: "/system/roles",
    icon: Shield,
  },
  {
    titleKey: "nav.provider_submissions",
    href: "/system/provider-submissions",
    icon: Send,
  },
  {
    titleKey: "nav.notifications_admin",
    href: "/system/notifications",
    icon: Megaphone,
  },
];

/**
 * 带装饰的菜单项组件
 * 装饰通过 CSS 类 .christmas-menu-decor 自动控制显示/隐藏
 */
function DecoratedMenuItem({
  children,
  className,
  ...props
}: React.ComponentProps<typeof SidebarMenuItem>) {
  return (
    <div className="relative">
      {/* 圣诞装饰 - 通过 CSS 类自动控制 */}
      <div className="christmas-menu-decor absolute -top-2 left-0 right-0 z-30 overflow-visible pointer-events-none">
        <div className="relative w-full h-10">
          {/* 悬挂线 */}
          <div className="absolute top-0 left-[25%] w-px h-5 bg-gradient-to-b from-yellow-600/60 to-transparent" />
          <div className="absolute top-0 left-[50%] w-px h-7 bg-gradient-to-b from-yellow-600/60 to-transparent" />
          <div className="absolute top-0 right-[25%] w-px h-4 bg-gradient-to-b from-yellow-600/60 to-transparent" />
          
          {/* 圣诞球 */}
          <div 
            className="absolute top-5 left-[25%] w-3 h-3 rounded-full -translate-x-1/2" 
            style={{ 
              background: "radial-gradient(circle at 30% 30%, #ffd700, #ffb700)", 
              boxShadow: "0 2px 6px rgba(255, 215, 0, 0.5), inset -1px -1px 2px rgba(0,0,0,0.2)" 
            }} 
          />
          <div 
            className="absolute top-7 left-[50%] w-4 h-4 rounded-full -translate-x-1/2" 
            style={{ 
              background: "radial-gradient(circle at 30% 30%, #ff4444, #cc0000)", 
              boxShadow: "0 2px 6px rgba(255, 68, 68, 0.5), inset -1px -1px 2px rgba(0,0,0,0.2)" 
            }} 
          />
          <div 
            className="absolute top-4 right-[25%] w-3 h-3 rounded-full translate-x-1/2" 
            style={{ 
              background: "radial-gradient(circle at 30% 30%, #44ff44, #00aa00)", 
              boxShadow: "0 2px 6px rgba(68, 255, 68, 0.5), inset -1px -1px 2px rgba(0,0,0,0.2)" 
            }} 
          />
        </div>
        
        {/* 花环图片 */}
        <div className="absolute top-0 left-0 right-0 h-10">
          <img
            src="/theme/christmas/dashboard.png"
            alt="Christmas garland"
            className="absolute top-0 left-0 w-full h-auto object-contain"
            style={{
              filter: "drop-shadow(0 1px 3px rgba(0, 0, 0, 0.2))",
              opacity: 0.85,
              maxHeight: "50px",
            }}
            loading="lazy"
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
        </div>
      </div>
      
      <SidebarMenuItem className={cn(className)} {...props}>
        {children}
      </SidebarMenuItem>
    </div>
  );
}

/**
 * 自适应主题侧边栏组件
 * 通过 CSS 变量和类名自动适配所有主题
 * 装饰效果可拔插，通过 CSS 控制
 */
export function AdaptiveSidebar() {
  const pathname = usePathname();
  const { t } = useI18n();
  const currentUser = useAuthStore((state) => state.user);
  const roleCodes = currentUser?.role_codes ?? [];
  const isSuperuser = currentUser?.is_superuser === true;
  const isAdmin =
    isSuperuser ||
    roleCodes.includes("system_admin") ||
    roleCodes.includes("admin");

  // 渲染菜单项：只有激活的才显示装饰
  const renderMenuItem = (item: NavItem, isActive: boolean) => {
    const linkContent = (
      <Link
        href={item.href}
        className={cn(
          "flex items-center space-x-3 px-3 py-2.5 rounded transition-colors text-sm",
          isActive
            ? "bg-primary text-primary-foreground"
            : "text-sidebar-foreground hover:bg-sidebar-accent"
        )}
      >
        <item.icon className="w-5 h-5 flex-shrink-0" />
        <span>{t(item.titleKey)}</span>
      </Link>
    );

    // 只有激活的菜单项才使用装饰组件
    const MenuItemWrapper = isActive ? DecoratedMenuItem : SidebarMenuItem;

    return (
      <MenuItemWrapper key={item.href}>
        <SidebarMenuButton asChild isActive={isActive}>
          {linkContent}
        </SidebarMenuButton>
      </MenuItemWrapper>
    );
  };

  const visibleAdminItems = adminItems.filter((item) => {
    if (item.requiresSuperuser === true) return isSuperuser;
    return true;
  });

  return (
    <Sidebar className="hidden lg:flex w-64 border-r h-screen theme-adaptive-sidebar">
      <SidebarHeader className="p-6 border-b">
        <Link
          href="/"
          className="text-2xl font-bold tracking-tight hover:opacity-80 transition-opacity"
        >
          {t("app.title")}
        </Link>
      </SidebarHeader>

      <SidebarContent className="flex-1 overflow-y-auto py-6">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="px-3 space-y-2">
              {navItems.map((item) => renderMenuItem(item, pathname === item.href))}

              {isAdmin && (
                <>
                  <div className="pt-6 pb-2">
                    <SidebarGroupLabel className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("nav.admin")}
                    </SidebarGroupLabel>
                  </div>

                  {visibleAdminItems.map((item) =>
                    renderMenuItem(item, pathname === item.href)
                  )}
                </>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-4 border-t">
        <Link
          href="/profile"
          className="flex items-center space-x-3 px-3 py-2.5 rounded hover:bg-sidebar-accent transition-colors text-sm"
        >
          <UserCircle className="w-5 h-5 flex-shrink-0" />
          <span>{t("nav.my_profile")}</span>
        </Link>
      </SidebarFooter>
    </Sidebar>
  );
}

// 重新导出 shadcn sidebar 的所有子组件
export {
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
