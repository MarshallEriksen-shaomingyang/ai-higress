"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n-context";
import { DASHBOARD_PATH, DOCS_URL } from "./home-links";

export function CTASection() {
  const { t } = useI18n();

  return (
    <section className="container mx-auto px-6 py-16 max-w-4xl">
      <Card className="bg-muted/50">
        <CardContent className="pt-12 pb-12 text-center">
          <h2 className="text-3xl font-bold mb-4">{t("home.cta_title")}</h2>
          <p className="text-muted-foreground mb-8 max-w-2xl mx-auto">
            {t("home.cta_description")}
          </p>
          <div className="flex gap-4 justify-center">
            <Link href={DASHBOARD_PATH}>
              <Button size="lg">
                {t("home.btn_view_demo")}
              </Button>
            </Link>
            <Link href={DOCS_URL} target="_blank" rel="noreferrer">
              <Button variant="outline" size="lg" className="gap-2">
                {t("home.btn_view_docs")}
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
