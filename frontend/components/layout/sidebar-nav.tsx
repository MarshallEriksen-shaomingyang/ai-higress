"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n-context";
import {
    LayoutDashboard,
    Server,
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
    Lock
} from "lucide-react";

const navItems = [
    {
        titleKey: "nav.overview",
        href: "/dashboard/overview",
        icon: LayoutDashboard,
    },
    {
        titleKey: "nav.providers",
        href: "/dashboard/providers",
        icon: Server,
    },
    {
        titleKey: "nav.my_providers",
        href: "/dashboard/my-providers",
        icon: Lock,
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
        titleKey: "nav.metrics",
        href: "/dashboard/metrics",
        icon: Activity,
    },
];

const adminItems = [
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
        titleKey: "nav.system",
        href: "/system/admin",
        icon: Settings,
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
];

export function SidebarNav() {
    const pathname = usePathname();
    const { t } = useI18n();

    return (
        <div className="w-64 border-r bg-sidebar h-screen flex flex-col">
            <div className="p-6 border-b">
                <h1 className="text-2xl font-bold tracking-tight">{t("app.title")}</h1>
            </div>

            <div className="flex-1 overflow-y-auto py-6">
                <nav className="px-3 space-y-1">
                    {navItems.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
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

                    <div className="pt-6 pb-2">
                        <p className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                            {t("nav.admin")}
                        </p>
                    </div>

                    {adminItems.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
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
                </nav>
            </div>

            <div className="p-4 border-t">
                <Link
                    href="/profile"
                    className="flex items-center space-x-3 px-3 py-2.5 rounded hover:bg-sidebar-accent transition-colors text-sm"
                >
                    <UserCircle className="w-5 h-5 flex-shrink-0" />
                    <span>{t("nav.my_profile")}</span>
                </Link>
            </div>
        </div>
    );
}
