"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n-context";
import { useAuthStore } from "@/lib/stores/auth-store";
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
    MessageSquare,
    Plug,
    FlaskConical,
    ScrollText,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

// 动态加载 Sheet 组件
const Sheet = dynamic(() => import("@/components/ui/sheet").then(mod => ({ default: mod.Sheet })), { ssr: false });
const SheetContent = dynamic(() => import("@/components/ui/sheet").then(mod => ({ default: mod.SheetContent })), { ssr: false });
const SheetHeader = dynamic(() => import("@/components/ui/sheet").then(mod => ({ default: mod.SheetHeader })), { ssr: false });
const SheetTitle = dynamic(() => import("@/components/ui/sheet").then(mod => ({ default: mod.SheetTitle })), { ssr: false });

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
        titleKey: "nav.chat",
        href: "/chat",
        icon: MessageSquare,
    },
    {
        titleKey: "nav.bridge",
        href: "/dashboard/bridge",
        icon: Plug,
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
        titleKey: "nav.routing",
        href: "/dashboard/routing",
        icon: Network,
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
        titleKey: "nav.request_logs",
        href: "/dashboard/request-logs",
        icon: ScrollText,
    },
];

const adminItems: NavItem[] = [
    {
        titleKey: "nav.provider_presets",
        href: "/dashboard/provider-presets",
        icon: Package,
    },
    {
        titleKey: "nav.eval_config",
        href: "/dashboard/eval-config",
        icon: FlaskConical,
        requiresSuperuser: true,
    },
    {
        titleKey: "nav.eval_results",
        href: "/dashboard/evals",
        icon: FlaskConical,
        requiresSuperuser: true,
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

interface MobileSidebarProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function MobileSidebar({ open, onOpenChange }: MobileSidebarProps) {
    const pathname = usePathname();
    const { t } = useI18n();
    const currentUser = useAuthStore(state => state.user);
    const roleCodes = currentUser?.role_codes ?? [];
    const isSuperuser = currentUser?.is_superuser === true;
    const isAdmin =
        isSuperuser ||
        roleCodes.includes("system_admin") ||
        roleCodes.includes("admin");

    const handleLinkClick = () => {
        onOpenChange(false);
    };

    const visibleAdminItems = adminItems.filter((item) => {
        if (item.requiresSuperuser === true) return isSuperuser;
        return true;
    });

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="left" className="w-[280px] p-0">
                <SheetHeader className="p-6 border-b">
                    <SheetTitle>
                        <Link 
                            href="/" 
                            className="text-xl font-bold tracking-tight hover:opacity-80 transition-opacity"
                            onClick={handleLinkClick}
                        >
                            {t("app.title")}
                        </Link>
                    </SheetTitle>
                </SheetHeader>

                <ScrollArea className="h-[calc(100vh-80px)]">
                    <nav className="px-3 py-6 space-y-1">
                        {navItems.map((item) => (
                            <Link
                                key={item.href}
                                href={item.href}
                                onClick={handleLinkClick}
                                className={cn(
                                    "flex items-center space-x-3 px-3 py-2.5 rounded transition-colors text-sm",
                                    pathname === item.href
                                        ? "bg-primary text-primary-foreground"
                                        : "text-sidebar-foreground hover:bg-sidebar-accent"
                                )}
                            >
                                <item.icon className="w-5 h-5 flex-shrink-0" />
                                <span>{t(item.titleKey)}</span>
                            </Link>
                        ))}

                        {isAdmin && (
                            <>
                                <div className="pt-6 pb-2">
                                    <p className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                        {t("nav.admin")}
                                    </p>
                                </div>

                                {visibleAdminItems.map((item) => (
                                    <Link
                                        key={item.href}
                                        href={item.href}
                                        onClick={handleLinkClick}
                                        className={cn(
                                            "flex items-center space-x-3 px-3 py-2.5 rounded transition-colors text-sm",
                                            pathname === item.href
                                                ? "bg-primary text-primary-foreground"
                                                : "text-sidebar-foreground hover:bg-sidebar-accent"
                                        )}
                                    >
                                        <item.icon className="w-5 h-5 flex-shrink-0" />
                                        <span>{t(item.titleKey)}</span>
                                    </Link>
                                ))}
                            </>
                        )}

                        <div className="pt-6 border-t mt-6">
                            <Link
                                href="/profile"
                                onClick={handleLinkClick}
                                className="flex items-center space-x-3 px-3 py-2.5 rounded hover:bg-sidebar-accent transition-colors text-sm"
                            >
                                <UserCircle className="w-5 h-5 flex-shrink-0" />
                                <span>{t("nav.my_profile")}</span>
                            </Link>
                        </div>
                    </nav>
                </ScrollArea>
            </SheetContent>
        </Sheet>
    );
}
