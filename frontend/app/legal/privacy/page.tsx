"use client";

import { useI18n } from "@/lib/i18n-context";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function PrivacyPolicyPage() {
  const { t } = useI18n();

  return (
    <div className="min-h-screen bg-background">
      <div className="container max-w-4xl mx-auto px-4 py-8">
        <Link
          href="/"
          className="inline-flex items-center text-muted-foreground hover:text-foreground mb-8"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          返回首页
        </Link>

        <article className="prose prose-neutral dark:prose-invert max-w-none">
          <h1 className="text-3xl font-bold mb-2">{t("legal.privacy.title")}</h1>
          <p className="text-muted-foreground mb-8">{t("legal.privacy.effective_date")}</p>

          <p className="lead">{t("legal.privacy.intro")}</p>

          <h2>{t("legal.privacy.section1.title")}</h2>
          <p>{t("legal.privacy.section1.content")}</p>

          <h2>{t("legal.privacy.section2.title")}</h2>
          <p>{t("legal.privacy.section2.content")}</p>

          <h2>{t("legal.privacy.section3.title")}</h2>
          <p>{t("legal.privacy.section3.content")}</p>

          <h2>{t("legal.privacy.section4.title")}</h2>
          <p>{t("legal.privacy.section4.content")}</p>

          <h2>{t("legal.privacy.section5.title")}</h2>
          <p>{t("legal.privacy.section5.content")}</p>

          <h2>{t("legal.privacy.section6.title")}</h2>
          <p>{t("legal.privacy.section6.content")}</p>
        </article>
      </div>
    </div>
  );
}
