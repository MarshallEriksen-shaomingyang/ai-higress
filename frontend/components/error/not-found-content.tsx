"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n-context";
import {
  Home,
  ArrowLeft,
  LayoutDashboard,
  Plug,
  BookOpen,
  MessageCircle,
} from "lucide-react";
import Link from "next/link";

export function NotFoundContent() {
  const router = useRouter();
  const { t } = useI18n();

  const quickLinks = [
    {
      href: "/dashboard/overview",
      icon: LayoutDashboard,
      title: t("error.404.link_dashboard"),
      description: t("error.404.link_dashboard_desc"),
    },
    {
      href: "/dashboard/providers",
      icon: Plug,
      title: t("error.404.link_providers"),
      description: t("error.404.link_providers_desc"),
    },
    {
      href: "/docs",
      icon: BookOpen,
      title: t("error.404.link_docs"),
      description: t("error.404.link_docs_desc"),
    },
    {
      href: "/support",
      icon: MessageCircle,
      title: t("error.404.link_support"),
      description: t("error.404.link_support_desc"),
    },
  ];

  return (
    <div className="min-h-screen flex items-center justify-center p-4 animate-in fade-in duration-500">
      <div className="max-w-2xl w-full text-center space-y-8">
        {/* 404 数字 */}
        <h1
          className="text-7xl md:text-8xl lg:text-9xl font-bold bg-gradient-to-r from-primary to-primary/50 bg-clip-text text-transparent animate-in zoom-in duration-700"
          aria-label={t("error.404.title")}
        >
          404
        </h1>

        {/* 标题和描述 */}
        <div className="space-y-4">
          <h2 className="text-2xl md:text-3xl font-semibold">
            {t("error.404.heading")}
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-md mx-auto">
            {t("error.404.description")}
          </p>
        </div>

        {/* 操作按钮 */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Button onClick={() => router.push("/")} size="lg">
            <Home className="mr-2 h-4 w-4" />
            {t("error.404.btn_home")}
          </Button>
          <Button
            variant="outline"
            onClick={() => router.back()}
            size="lg"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t("error.404.btn_back")}
          </Button>
        </div>

        {/* 快捷链接 */}
        <div className="pt-8">
          <p className="text-sm text-muted-foreground mb-6">
            {t("error.404.suggestion")}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {quickLinks.map((link) => (
              <Link key={link.href} href={link.href}>
                <Card className="hover:shadow-lg transition-all duration-300 hover:-translate-y-1 cursor-pointer h-full">
                  <CardContent className="p-6 flex flex-col items-center text-center space-y-2">
                    <link.icon className="h-8 w-8 text-primary" />
                    <h3 className="font-semibold">{link.title}</h3>
                    <p className="text-sm text-muted-foreground">
                      {link.description}
                    </p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}