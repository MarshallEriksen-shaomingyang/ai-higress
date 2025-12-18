"use client";

import { useI18n } from "@/lib/i18n-context";

export function MyProvidersHeader() {
  const { t } = useI18n();

  return (
    <div className="space-y-1">
      <h1 className="text-3xl font-bold">{t("my_providers.title")}</h1>
      <p className="text-muted-foreground text-sm">
        {t("my_providers.subtitle")}
      </p>
    </div>
  );
}

