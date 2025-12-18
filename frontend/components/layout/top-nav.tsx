"use client";

import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { useAuthStore } from "@/lib/stores/auth-store";
import { UserMenu } from "./user-menu";
import { Button } from "@/components/ui/button";
import { NotificationBell } from "@/components/dashboard/notifications/notification-bell";
import { MobileSidebar } from "./mobile-sidebar";
import { ThemeSwitcher } from "@/components/theme-switcher";

export function TopNav() {
    const [mounted, setMounted] = useState(false);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const { language, setLanguage, t } = useI18n();
    const { isAuthenticated, isLoading, openAuthDialog } = useAuthStore();

    useEffect(() => {
        setMounted(true);
    }, []);

    const handleLanguageToggle = () => {
        console.log("Language toggle clicked, current language:", language);
        const newLang = language === "en" ? "zh" : "en";
        console.log("Setting language to:", newLang);
        setLanguage(newLang);
    };

    return (
        <header className="h-16 border-b bg-card flex items-center px-4 lg:px-6">
            {/* 移动端菜单按钮 */}
            <button
                onClick={() => setMobileMenuOpen(true)}
                className="lg:hidden h-9 w-9 p-0 rounded hover:bg-muted transition-colors flex items-center justify-center mr-auto"
                aria-label="打开菜单"
            >
                <Menu className="h-5 w-5" />
            </button>

            {/* 移动端侧边栏 */}
            <MobileSidebar open={mobileMenuOpen} onOpenChange={setMobileMenuOpen} />

            <div className="flex items-center space-x-2 ml-auto">
                {/* Language Toggle */}
                {mounted && (
                    <button
                        onClick={handleLanguageToggle}
                        className="h-9 w-9 p-0 rounded hover:bg-muted transition-colors flex items-center justify-center"
                    >
                        <span className="text-sm font-medium">
                            {language === "en" ? "中" : "En"}
                        </span>
                    </button>
                )}

                {/* Theme Switcher */}
                <ThemeSwitcher />

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
