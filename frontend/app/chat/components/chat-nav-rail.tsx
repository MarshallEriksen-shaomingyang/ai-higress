"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, MessageSquare, Settings, User } from "lucide-react";
import type { ComponentType } from "react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
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
    isActive: (pathname) => pathname.startsWith("/chat"),
  },
  {
    href: "/system",
    icon: Settings,
    labelKey: "nav.system",
    isActive: (pathname) => pathname.startsWith("/system"),
  },
];

export function ChatNavRail() {
  const pathname = usePathname();
  const { t } = useI18n();

  return (
    <aside className="w-14 shrink-0 border-r bg-background/60 backdrop-blur supports-[backdrop-filter]:bg-background/40">
      <div className="flex h-full flex-col items-center py-3">
        <div className="flex flex-col items-center gap-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.isActive(pathname);

            return (
              <Button
                key={item.href}
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
            );
          })}
        </div>

        <Separator className="my-3 w-8" />

        <div className="mt-auto flex flex-col items-center gap-1.5">
          <AppearanceControls variant="rail" className="mb-2" />
          <Button
            asChild
            variant="ghost"
            size="icon"
            className={cn(
              "h-10 w-10 rounded-xl",
              pathname.startsWith("/profile") && "bg-accent text-accent-foreground"
            )}
          >
            <Link href="/profile" aria-label={t("nav.my_profile")}>
              <User className="h-5 w-5" />
            </Link>
          </Button>
        </div>
      </div>
    </aside>
  );
}
