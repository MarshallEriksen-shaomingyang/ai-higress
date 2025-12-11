"use client";

import { useI18n } from "@/lib/i18n-context";

/**
 * 页面头部组件（客户端组件）
 * 负责显示国际化的标题和描述
 */
export function PageHeader() {
  const { t } = useI18n();

  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-light tracking-tight">{t("overview.title")}</h1>
      <p className="text-sm text-muted-foreground">{t("overview.subtitle")}</p>
    </div>
  );
}
