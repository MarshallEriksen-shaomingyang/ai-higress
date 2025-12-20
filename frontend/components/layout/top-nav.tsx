"use client";

import { useState } from "react";
import { Menu, PanelLeft } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { useAuthStore } from "@/lib/stores/auth-store";
import { useSidebarStore } from "@/lib/stores/sidebar-store";
import { UserMenu } from "./user-menu";
import { Button } from "@/components/ui/button";
import { NotificationBell } from "@/components/dashboard/notifications/notification-bell";
import { MobileSidebar } from "./mobile-sidebar";
import { AppearanceControls } from "@/components/layout/appearance-controls";

export function TopNav() {
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const { t } = useI18n();
    const { isAuthenticated, isLoading, openAuthDialog } = useAuthStore();
    const toggleSidebar = useSidebarStore((state) => state.toggleSidebar);

    return (
        <header className="h-16 border-b bg-card flex items-center px-4 lg:px-6">
            {/* 移动端菜单按钮 */}
            <Button
                variant="ghost"
                size="icon"
                onClick={() => setMobileMenuOpen(true)}
                className="lg:hidden h-9 w-9"
                aria-label={t("common.open_menu")}
            >
                <Menu className="h-5 w-5" />
            </Button>

            {/* 桌面端侧边栏切换按钮 */}
            <Button
                variant="ghost"
                size="icon"
                onClick={toggleSidebar}
                className="hidden lg:flex h-9 w-9"
                aria-label={t("common.toggle_sidebar")}
            >
                <PanelLeft className="h-5 w-5" />
            </Button>

            {/* 移动端侧边栏 */}
            <MobileSidebar open={mobileMenuOpen} onOpenChange={setMobileMenuOpen} />

            <div className="flex items-center space-x-2 ml-auto">
                <AppearanceControls variant="topnav" />

                {/* Notification Bell */}
                {!isLoading && isAuthenticated && (
                    <NotificationBell />
                )}

                {/* User Profile or Login Button */}
                <div className="flex items-center pl-4 border-l">
                    {!isLoading && (
                        isAuthenticated ? (
                            <UserMenu />
                        ) : (
                            <Button
                                variant="default"
                                size="sm"
                                onClick={openAuthDialog}
                            >
                                {t("auth.login_button")}
                            </Button>
                        )
                    )}
                </div>
            </div>
        </header>
    );
}
