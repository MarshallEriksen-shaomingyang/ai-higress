"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { DASHBOARD_PATH } from "./home-links";

export function HeroSection() {
  const { t } = useI18n();

  return (
    <section className="container mx-auto px-6 pt-20 pb-16 max-w-6xl">
      <div className="text-center space-y-6">
        <h1 className="text-5xl md:text-6xl font-bold tracking-tight">
          {t("app.title")}
        </h1>
        <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto">
          {t("home.tagline")}
        </p>
        <p className="text-base md:text-lg text-muted-foreground max-w-2xl mx-auto">
          {t("home.description")}
        </p>
        <div className="flex gap-4 justify-center pt-4">
          <Link href={DASHBOARD_PATH}>
            <Button size="lg" className="gap-2">
              {t("home.btn_enter_console")}
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
          <Link href="/login">
            <Button variant="outline" size="lg">
              {t("home.btn_get_started")}
            </Button>
          </Link>
        </div>
      </div>
    </section>
  );
}
